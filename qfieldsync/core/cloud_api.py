# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
                             -------------------
        begin                : 2020-07-13
        git sha              : $Format:%H$
        copyright            : (C) 2020 by OPENGIS.ch
        email                : info@opengis.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import json
import re
import tempfile
import urllib.parse
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import requests
from PyQt5.QtNetwork import QSslPreSharedKeyAuthenticator
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsAuthMethodConfig,
    QgsNetworkAccessManager,
    QgsProject,
)
from qgis.PyQt.QtCore import (
    QByteArray,
    QFileSystemWatcher,
    QObject,
    QUrl,
    QUrlQuery,
    pyqtSignal,
)
from qgis.PyQt.QtNetwork import (
    QHttpMultiPart,
    QHttpPart,
    QNetworkReply,
    QNetworkRequest,
)

from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.core.preferences import Preferences
from qfieldsync.utils.qt_utils import strip_html


class CloudException(Exception):
    def __init__(self, reply, exception: Optional[Exception] = None):
        super(CloudException, self).__init__(exception)
        self.reply = reply
        self.parent = exception
        self.httpCode = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)


class disable_nam_timeout:
    """By default QGIS has 60 seconds timeout, which is too short for uploading huge files"""

    def __init__(self, nam: QgsNetworkAccessManager) -> None:
        self.nam = nam

    def __enter__(self):
        self.timeout = self.nam.timeout()
        if Qgis.QGIS_VERSION_INT >= 31800:
            self.nam.setTimeout(0)
        else:
            # Set it to ridiculously big timeout of 24h.
            self.nam.setTimeout(60 * 60 * 24)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.nam.setTimeout(self.timeout)


def from_reply(reply: QNetworkReply) -> Optional[CloudException]:
    if reply.error() == QNetworkReply.NoError:
        return None

    message = ""
    try:
        payload = reply.readAll().data()
        # workaround to https://github.com/qgis/QGIS/issues/49687
        content_length = reply.header(QNetworkRequest.ContentLengthHeader)
        payload = payload[:content_length].decode()

        try:
            resp = json.loads(payload)
            if resp.get("code"):
                message = f'[{resp["code"]}] {resp["message"]}'
            else:
                message = resp["detail"]
        except Exception:
            if payload:
                message = payload[:500]

                if len(payload) > 500:
                    message += "…"
    except Exception:
        pass

    if not message:
        status_str = ""

        http_status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if http_status is not None:
            status_str += f"HTTP-{http_status}/"

        status_str += f"QT-{reply.error()}"
        message = f"[{status_str}] {reply.errorString()}"

    return CloudException(reply, Exception(message))


class CloudAuthMethod(Enum):
    NONE = 0
    CREDENTIALS = 1
    SSO = 2


def build_oauth2_auth_config(
    auth_data: dict[str, Any],
    related_uri: str,
    config_name: str = "qfieldcloud_sso",
    should_persist_token: bool = True,
) -> QgsAuthMethodConfig:
    """Builds a QgsAuthMethodConfig from a method provided by QFieldCloud's auth capabilities.

    Args:
        auth_data: dict describing an auth method.
        related_uri: URI of the generated auth config.
        config_name: name of the generated auth config. Defaults to "qfieldcloud_sso".
        should_persist_token: if the token should be persistent. Defaults to True.

    Returns:
        QgsAuthMethodConfig: QGIS auth config for the provided method.
    """
    auth_config_dict = {
        "method": "oauth2",
        "accessMethod": 0,
        "grantFlow": auth_data.get("grant_flow"),
        "configType": 1,
        "clientId": auth_data.get("client_id"),
        "extraTokens": auth_data.get("extra_tokens"),
        "requestUrl": auth_data.get("request_url"),
        "tokenUrl": auth_data.get("token_url"),
        "redirectHost": auth_data.get("redirect_host"),
        "redirectPort": auth_data.get("redirect_port"),
        "redirectUrl": auth_data.get("redirect_url"),
        "persistToken": should_persist_token,
        "pkceEnabled": auth_data.get("pkce_enabled"),
        "refreshTokenUrl": auth_data.get("refresh_token_url"),
        "requestTimeout": 30,
        "version": 1,
        "scope": auth_data.get("scope"),
    }

    auth_config_str = json.dumps(auth_config_dict)

    auth_config = QgsAuthMethodConfig()
    auth_config.setMethod("OAuth2")
    auth_config.setVersion(1)
    auth_config.setName(config_name)
    auth_config.setUri(related_uri)
    auth_config.setConfig("oauth2config", auth_config_str)
    auth_config.setConfig("qfieldcloud_sso_id", auth_data["id"])

    return auth_config


class CloudNetworkAccessManager(QObject):
    token_changed = pyqtSignal()
    login_finished = pyqtSignal()
    logout_success = pyqtSignal()
    logout_failed = pyqtSignal(str)
    avatar_success = pyqtSignal()

    auth_method: CloudAuthMethod = CloudAuthMethod.NONE
    auth_config: Optional[QgsAuthMethodConfig] = None
    current_username: Optional[str] = None

    def __init__(self, parent=None) -> None:
        """Constructor."""
        super(CloudNetworkAccessManager, self).__init__(parent=parent)

        self.preferences = Preferences()
        self.url = ""
        self._token = ""
        self.user_details: Dict[str, str] = {}
        self.projects_cache = CloudProjectsCache(self, self)
        self.is_login_active = False

        url = self.preferences.value("qfieldCloudServerUrl")

        # we should always use the QgsNetworkAccessManager instance, otherwise ssl handling is impossible
        self._nam = QgsNetworkAccessManager.instance()

        self.auth_method = CloudAuthMethod(
            self.preferences.value("qfieldCloudAuthMethod")
        )
        pref_auth_config_id = self.preferences.value("qfieldCloudAuthcfg")
        if pref_auth_config_id:
            auth_config = QgsAuthMethodConfig()
            _success, config = QgsApplication.authManager().loadAuthenticationConfig(
                pref_auth_config_id, auth_config, full=True
            )
            self.auth_config = config

        # use the default URL
        self.set_url(url)

    def handle_response(
        self, reply: QNetworkReply, should_parse_json: bool = True
    ) -> Optional[Union[List, Dict]]:
        payload_str = ""

        error = from_reply(reply)
        if error:
            if error.httpCode == 401 and not self.is_login_active:
                self.set_token("", True)
                self.auth_method = CloudAuthMethod.NONE
                self.auth_config = None
                self.logout_success.emit()
            raise error

        if not should_parse_json:
            return None

        try:
            payload_str = str(reply.readAll().data(), encoding="utf-8")
            return json.loads(payload_str)
        except Exception as error:
            raise CloudException(reply, error) from error

    def json_object(self, reply: QNetworkReply) -> Dict[str, Any]:
        payload = self.handle_response(reply, True)

        assert isinstance(payload, dict)

        return payload

    def json_array(self, reply: QNetworkReply) -> List[Any]:
        payload = self.handle_response(reply, True)

        assert isinstance(payload, list)

        return payload

    @staticmethod
    def server_urls() -> List[str]:
        return [
            "https://app.qfield.cloud/",
            "https://dev.qfield.cloud/",
            "https://localhost:8002/",
        ]

    def get_username(self) -> Optional[str]:
        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            return self.auth().config("username")
        elif self.auth_method == CloudAuthMethod.SSO:
            return self.current_username
        return None

    def auth(self) -> QgsAuthMethodConfig:
        auth_manager = QgsApplication.authManager()

        if not auth_manager.masterPasswordHashInDatabase():
            return QgsAuthMethodConfig()

        authcfg = self.preferences.value("qfieldCloudAuthcfg")

        if not authcfg or authcfg == "":
            return QgsAuthMethodConfig()

        cfg = QgsAuthMethodConfig()
        auth_manager.loadAuthenticationConfig(authcfg, cfg, True)

        return cfg

    def set_auth(self, url, **kwargs: str) -> None:
        if self.auth_method != CloudAuthMethod.CREDENTIALS:
            return

        if self.url != url:
            self.set_url(url)

        authcfg = self.preferences.value("qfieldCloudAuthcfg")
        cfg = QgsAuthMethodConfig()
        auth_manager = QgsApplication.authManager()
        auth_manager.setMasterPassword()
        auth_manager.loadAuthenticationConfig(authcfg, cfg, True)

        if cfg.id():
            cfg.setUri(url)

            for key, value in kwargs.items():
                cfg.setConfig(key, str(value))

            auth_manager.updateAuthenticationConfig(cfg)
        else:
            cfg.setMethod("Basic")
            cfg.setName("qfieldcloud")
            cfg.setUri(url)

            for key, value in kwargs.items():
                cfg.setConfig(key, value)

            auth_manager.storeAuthenticationConfig(cfg)
            self.preferences.set_value("qfieldCloudAuthcfg", cfg.id())

    def auth_provider_id(self) -> str:
        """
        Returns the provider ID, required for sso auth to QFieldCloud.
        Should be stored in the QgsAuthMethodConfig with the "qfieldcloud_sso_id" key.
        """
        auth_method = self.auth()
        if not auth_method:
            return ""
        return auth_method.config("qfieldcloud_sso_id", "")

    def set_auth_method(self, method: CloudAuthMethod) -> None:
        self.auth_method = method
        self.preferences.set_value("qfieldCloudAuthMethod", method.value)

    def set_sso_auth_config(self, auth_config: QgsAuthMethodConfig) -> None:
        self.auth_config = auth_config
        QgsApplication.authManager().storeAuthenticationConfig(
            auth_config, overwrite=True
        )
        self.preferences.set_value("qfieldCloudAuthcfg", auth_config.id())

    def set_url(self, server_url: str) -> None:
        if not server_url:
            server_url = CloudNetworkAccessManager.server_urls()[0]

        # Assume the URL has a scheme or at least starts with leading //.
        p = urlparse(server_url)

        # QFieldSync will automatically append `/api/v1` to the path, so prevent double append like `/api/v1/api/v1`.
        if p.path.startswith("/api/v1"):
            self.url = f"{p.scheme or 'https'}://{p.netloc}/"
        else:
            self.url = f"{p.scheme or 'https'}://{p.netloc}{p.path}"

        self.preferences.set_value("qfieldCloudServerUrl", server_url)

    @property
    def server_url(self):
        url = self.url + "/api/v1/"
        url = re.sub(r"(\/+api\/+v1)+", "/api/v1/", url)

        return re.sub(r"([^:]/)(/)+", r"\1", url)

    def get_auth_capabilities(self) -> QNetworkReply:
        """Get authentication capabilities from a server"""
        reply = self.cloud_get("auth/providers/")
        return reply

    def auto_login_attempt(self):
        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            cfg = self.auth()

            server_url = cfg.uri() or self.url
            username = cfg.config("username")
            password = cfg.config("password")

            if all([username, password]):
                self.set_url(server_url)
            self.login_with_credentials(username, password)

        elif self.auth_method == CloudAuthMethod.SSO:
            self.login_with_sso()

    def login_with_credentials(
        self, username: str, password: str
    ) -> Optional[QNetworkReply]:
        """Login to QFieldCloud with classic login/password method"""
        # don't login multiple times
        if self.is_login_active:
            return None

        self.is_login_active = True

        reply = self.cloud_post(
            "auth/login/",
            {
                "username": username,
                "password": password,
            },
        )
        reply.finished.connect(lambda: self._on_login_with_credentials_finished(reply))

        return reply

    def login_with_sso(self) -> Optional[QNetworkReply]:
        """
        Login to QFieldCloud with social provider (e.g. Google).
        This basically sends a GET user info request to QFC.
        Which means the OAuth2 QgsAuthMethodConfig will trigger auth in the browser, if required.
        """
        return self._get_cloud_user_info()

    def _get_cloud_user_info(self) -> Optional[QNetworkReply]:
        """Get current user info with a request.
        This is typically called as a first request

        Returns:
            Optional[QNetworkReply]: QNetworkReply from the QFieldCloud server.
        """

        reply = self.cloud_get("auth/user/")
        reply.finished.connect(lambda: self._on_get_user_info_finished(reply))

        return reply

    def get_user(self, token: str) -> QNetworkReply:
        """Gets current user and if token is still valid"""
        return self.cloud_get("auth/user/", {"token": token})

    def logout(self) -> Optional[QNetworkReply]:
        """Logout from QFieldCloud"""

        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            reply = self.cloud_post("auth/logout/")
            reply.finished.connect(lambda: self._on_logout_finished(reply))
        elif self.auth_method == CloudAuthMethod.SSO:
            authcfg = self.preferences.value("qfieldCloudAuthcfg")
            auth_manager = QgsApplication.authManager()
            auth_manager.clearCachedConfig(authcfg)
            auth_manager.removeAuthenticationConfig(authcfg)
            self.auth_method = CloudAuthMethod.NONE
            self.preferences.set_value("qfieldCloudAuthcfg", "")
            self.auth_config = None
            self.current_username = None
            self.preferences.set_value("qfieldCloudAuthMethod", self.auth_method.value)
            self._clear_cloud_cookies(QUrl(self.url))
            self.logout_success.emit()
            return None

        return reply

    def get_basic_reply(self, resource_url: str) -> QNetworkReply:
        request = QNetworkRequest(QUrl(resource_url))
        return QgsNetworkAccessManager.instance().get(request)

    def get_projects(self, should_include_public: bool = False) -> QNetworkReply:
        """Get QFieldCloud projects"""
        params = {"include-public": "1"} if should_include_public else {}
        return self.cloud_get("projects", params)

    def get_projects_not_async(self, should_include_public: bool = False) -> List[Dict]:
        """Get QFieldCloud projects synchronously"""
        headers = {"Authorization": "token {}".format(self._token)}
        params = {"include-public": "1"} if should_include_public else {}

        response = requests.get(
            self._prepare_uri("projects").toString(),
            headers=headers,
            params=params,
        )
        response.raise_for_status()

        return response.json()

    def create_project(
        self, name: str, owner: str, description: str, private: bool
    ) -> QNetworkReply:
        """Create a new QFieldCloud project"""

        return self.cloud_post(
            "projects/",
            {
                "name": name,
                "owner": owner,
                "description": description,
                "private": private,
            },
        )

    def update_project(
        self, project_id: str, name: str, description: str
    ) -> QNetworkReply:
        """Update an existing QFieldCloud project"""

        return self.cloud_patch(
            ["projects", project_id],
            {
                "name": name,
                "description": description,
            },
        )

    def delete_project(self, project_id: str) -> QNetworkReply:
        """Delete an existing QFieldCloud project"""

        return self.cloud_delete(["projects", project_id])

    def get_user_organizations(self, username: str) -> QNetworkReply:
        """Gets the available projects for the owner dropdown menu"""

        return self.cloud_get(["users", username, "organizations"])

    def get_files(self, project_id: str, client: str = "qgis") -> QNetworkReply:
        """Get project files and their versions"""

        return self.cloud_get(
            ["files", project_id],
            {
                "client": client,
                "skip_metadata": 1,
            },
        )

    def get_file(self, url: QUrl, local_filename: str) -> QNetworkReply:
        """Download file from external URL"""

        return self.cloud_get(url, local_filename=local_filename)

    def delete_file(self, filename: str) -> QNetworkReply:
        return self.cloud_delete("files/" + filename)

    def set_token(self, token: str, update_auth: bool = False) -> None:
        """Sets QFieldCloud authentication token to be used by all the following requests. Set to empty string to disable token authentication."""
        if update_auth and self.auth_method == CloudAuthMethod.CREDENTIALS:
            self.set_auth(self.url, token=token)

        if self._token == token:
            return

        self._token = token

        self.token_changed.emit()

    def is_authenticated(self) -> bool:
        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            return self.has_token()
        if self.auth_method == CloudAuthMethod.SSO:
            # If there is no username, it means a request to get it
            # must be done before being considered authenticated.
            return self.auth_config and self.current_username
        return False

    def has_token(self) -> bool:
        return self._token is not None and len(self._token) > 0

    def _set_request_auth(self, request: QNetworkRequest) -> None:
        """Sets the correct authentication for a request, depending on the current auth method used.

        Args:
            request (QNetworkRequest): request to update.
        """
        if self.auth_method == CloudAuthMethod.CREDENTIALS and self._token:
            request.setRawHeader(
                b"Authorization", "Token {}".format(self._token).encode("utf-8")
            )
        elif self.auth_method == CloudAuthMethod.SSO and self.auth_config is not None:
            QgsApplication.authManager().updateNetworkRequest(
                request, self.auth_config.id()
            )
            self._add_csrf_cookies_to_request(request.url(), request)
            self._add_provider_id_header_to_request(request)

    def cloud_get(
        self,
        uri: Union[str, List[str], QUrl],
        params: Dict[str, Any] = {},
        local_filename: str = None,
    ) -> QNetworkReply:
        """Issues a GET HTTP request"""
        url = self._prepare_uri(uri)

        query = QUrlQuery(url.query())

        self._clear_cloud_cookies(url)

        assert isinstance(params, dict)

        for param, value in params.items():
            if value is None:
                continue

            query.addQueryItem(param, str(value))

        url.setQuery(query)

        request = QNetworkRequest(url)
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.NoLessSafeRedirectPolicy,
        )
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        self._set_request_auth(request)

        with disable_nam_timeout(self._nam):
            reply = self._nam.get(request)

        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        if local_filename is not None:
            reply.finished.connect(
                lambda: self._on_cloud_get_download_finished(
                    reply, local_filename=local_filename
                )
            )

        return reply

    def get(self, url: QUrl, local_filename: str = None) -> QNetworkReply:
        request = QNetworkRequest(url)
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.UserVerifiedRedirectPolicy,
        )

        with disable_nam_timeout(self._nam):
            reply = self._nam.get(request)

        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        if local_filename is not None:
            reply.finished.connect(
                lambda: self._on_cloud_get_download_finished(
                    reply, local_filename=local_filename
                )
            )

        return reply

    def _on_cloud_get_download_finished(
        self, reply: QNetworkReply, local_filename: str
    ) -> None:
        http_code = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if http_code is not None and http_code >= 301 and http_code <= 308:
            # redirects should not be saved as files, just ignore them
            return

        with open(local_filename, "wb") as file:
            assert (
                file.write(reply.readAll()) != -1
            ), 'Error while writing to file "{}"'.format(local_filename)

    def cloud_post(
        self, uri: Union[str, List[str]], payload: Dict = None
    ) -> QNetworkReply:
        url = self._prepare_uri(uri)

        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            self._clear_cloud_cookies(url)

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        self._set_request_auth(request)

        payload_bytes = b"" if payload is None else json.dumps(payload).encode("utf-8")

        with disable_nam_timeout(self._nam):
            reply = self._nam.post(request, payload_bytes)

        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        return reply

    def cloud_put(
        self, uri: Union[str, List[str]], payload: Dict = None
    ) -> QNetworkReply:
        url = self._prepare_uri(uri)

        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            self._clear_cloud_cookies(url)

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        self._set_request_auth(request)

        payload_bytes = b"" if payload is None else json.dumps(payload).encode("utf-8")

        with disable_nam_timeout(self._nam):
            reply = self._nam.put(request, payload_bytes)

        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        return reply

    def cloud_patch(
        self, uri: Union[str, List[str]], payload: Dict = None
    ) -> QNetworkReply:
        url = self._prepare_uri(uri)

        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            self._clear_cloud_cookies(url)

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        self._set_request_auth(request)

        payload_bytes = b"" if payload is None else json.dumps(payload).encode("utf-8")

        with disable_nam_timeout(self._nam):
            reply = self._nam.sendCustomRequest(request, b"PATCH", payload_bytes)

        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        return reply

    def cloud_delete(self, uri: Union[str, List[str]]) -> QNetworkReply:
        url = self._prepare_uri(uri)

        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            self._clear_cloud_cookies(url)

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")

        self._set_request_auth(request)

        with disable_nam_timeout(self._nam):
            reply = self._nam.deleteResource(request)

        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        return reply

    def cloud_upload_files(
        self, uri: Union[str, List[str]], filenames: List[str], payload: Dict = None
    ) -> QNetworkReply:
        url = self._prepare_uri(uri)

        if self.auth_method == CloudAuthMethod.CREDENTIALS:
            self._clear_cloud_cookies(url)

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)

        self._set_request_auth(request)

        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)
        multi_part.setParent(self)
        multi_part.setBoundary(
            b"boundary_.oOo.QFieldRoxAndYouKnowItDXMtCoIPQV84CAX3rDyv83393"
        )

        # most of the time there is no other payload
        if payload is not None:
            json_part = QHttpPart()

            json_part.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
            json_part.setHeader(
                QNetworkRequest.ContentDispositionHeader, 'form-data; name="json"'
            )
            json_part.setBody(json.dumps(payload).encode("utf-8"))

            multi_part.append(json_part)

        # now attach each file
        for filename in filenames:
            # this might be optimized by usung QFile and QHttpPart.setBodyDevice, but didn't work on the first
            with open(filename, "rb") as file:
                file_part = QHttpPart()
                file_part.setBody(file.read())
                file_part.setHeader(
                    QNetworkRequest.ContentDispositionHeader,
                    'form-data; name="file"; filename="{}"'.format(filename),
                )

                multi_part.append(file_part)

        with disable_nam_timeout(self._nam):
            reply = self._nam.post(request, multi_part)

        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)
        multi_part.setParent(reply)

        return reply

    def _prepare_uri(self, uri: Union[str, List[str], QUrl]) -> QUrl:
        if isinstance(uri, QUrl):
            return uri

        if isinstance(uri, str):
            encoded_uri = uri
        else:
            encoded_parts = []

            for part in uri:
                encoded_parts.append(urllib.parse.quote(part))

            encoded_uri = "/".join(encoded_parts)

        if encoded_uri[-1] != "/":
            encoded_uri += "/"

        return QUrl(self.server_url + encoded_uri)

    def _on_logout_finished(self, reply: QNetworkReply) -> None:
        try:
            self.json_object(reply)
            self.set_token("", True)
            authcfg = self.preferences.value("qfieldCloudAuthcfg")
            auth_manager = QgsApplication.authManager()
            auth_manager.clearCachedConfig(authcfg)
            auth_manager.removeAuthenticationConfig(authcfg)
            self.auth_method = CloudAuthMethod.NONE
            self.preferences.set_value("qfieldCloudAuthcfg", "")
            self.auth_config = None
            self.preferences.set_value("qfieldCloudAuthMethod", self.auth_method.value)
            self.logout_success.emit()
        except CloudException as err:
            self.logout_failed.emit(str(err))
            return

    def _on_login_with_credentials_finished(self, reply: QNetworkReply) -> None:
        self.is_login_active = False

        try:
            payload = self.json_object(reply)
        except CloudException as err:
            self._login_error = err
            self.login_finished.emit()
            self.preferences.set_value("qfieldCloudRememberMe", False)
            return

        self.user_details = {
            "username": payload["username"],
            "avatar_url": payload["avatar_url"],
        }
        if payload["avatar_url"]:
            suffix = payload["avatar_url"].rsplit(".")[-1]
            avatar_filename = tempfile.mktemp(suffix=f".{suffix}")
            reply = self.get_file(
                QUrl(payload["avatar_url"]),
                avatar_filename,
            )
            reply.finished.connect(
                lambda: self._on_avatar_download_finished(reply, avatar_filename)
            )
        self.set_auth(self.url, username=payload["username"])
        self.set_token(
            payload["token"], self.preferences.value("qfieldCloudRememberMe")
        )
        self.login_finished.emit()

    def _on_get_user_info_finished(self, reply: QNetworkReply) -> None:
        try:
            payload = self.json_object(reply)
        except CloudException as err:
            self._login_error = err
            self.login_finished.emit()
            self.preferences.set_value("qfieldCloudRememberMe", False)
            return

        self.user_details = {
            "username": payload["username"],
            "avatar_url": payload["avatar_url"],
        }
        if payload["avatar_url"]:
            suffix = payload["avatar_url"].rsplit(".")[-1]
            avatar_filename = tempfile.mktemp(suffix=f".{suffix}")
            reply = self.get_file(
                QUrl(payload["avatar_url"]),
                avatar_filename,
            )
            reply.finished.connect(
                lambda: self._on_avatar_download_finished(reply, avatar_filename)
            )
        self.current_username = payload["username"]
        self.login_finished.emit()

    def _on_avatar_download_finished(self, reply: QNetworkReply, filename: str) -> None:
        error = from_reply(reply)

        if not error:
            self.user_details["avatar_filename"] = filename
            self.avatar_success.emit()

    def get_last_login_error(self) -> str:
        if self.has_token():
            return ""

        suggest_forgotten_password = True
        error_str = ""

        if self._login_error:
            reply = self._login_error.reply

            if (
                reply.error() == QNetworkReply.HostNotFoundError
                # network unreachable goes here
                or reply.error() == QNetworkReply.UnknownNetworkError
            ):
                error_str = self.tr(
                    "Failed to connect to {}. Check your internet connection.".format(
                        self.url
                    )
                )
                suggest_forgotten_password = False
            else:
                http_code = self._login_error.httpCode

                if http_code and http_code >= 500:
                    error_str = self.tr("Server error {}").format(http_code)
                elif http_code is None or (http_code >= 400 and http_code < 500):
                    error_str = str(self._login_error)

        error_str = strip_html(error_str).strip()

        if not error_str:
            error_str = self.tr("Sign in failed.")

        if suggest_forgotten_password:
            error_str += ' <a href="{}accounts/password/reset/">{}?</a>'.format(
                self.url, self.tr("Forgot password")
            )

        return error_str

    def _clear_cloud_cookies(self, url: QUrl) -> None:
        """When the CSRF_TOKEN cookie is present and the plugin is reloaded, the token has expired"""
        for cookie in self._nam.cookieJar().cookiesForUrl(url):
            self._nam.cookieJar().deleteCookie(cookie)

    def _add_csrf_cookies_to_request(self, url: QUrl, request: QNetworkRequest) -> None:
        """
        Adds CSRF cookie to a network request.
        Required for some QFieldCloud requests, like POST/PUT/PATCH/DELETE.
        """
        cookie_jar = self._nam.cookieJar()
        cookies = cookie_jar.cookiesForUrl(url)

        csrftoken_cookie = next(
            (cookie for cookie in cookies if cookie.name() == b"csrftoken"), None
        )

        if csrftoken_cookie:
            request.setRawHeader(b"X-CSRFToken", csrftoken_cookie.value())
            request.setRawHeader(b"Referer", url.toEncoded())

    def _add_provider_id_header_to_request(self, request: QNetworkRequest) -> None:
        """Adds the current provider id to a request, if any. Sometimes required by QFC middleware."""
        provider_id = self.auth_provider_id()

        if provider_id and len(provider_id) > 0:
            request.setRawHeader(b"X-QFC-IDP-ID", QByteArray(provider_id.encode()))


class CloudReply:
    finished = pyqtSignal()
    sslErrors = pyqtSignal()
    projects_error = pyqtSignal(str)
    downloadProgress = pyqtSignal(int, int)
    encrypted = pyqtSignal()
    errorOccurred = pyqtSignal(QNetworkReply.NetworkError)
    finished = pyqtSignal()
    metaDataChanged = pyqtSignal()
    preSharedKeyAuthenticationRequired = pyqtSignal(QSslPreSharedKeyAuthenticator)
    redirectAllowed = pyqtSignal()
    redirected = pyqtSignal(QUrl)
    sslErrors = pyqtSignal(list)
    uploadProgress = pyqtSignal(int, int)

    def __init__(self, reply: QNetworkReply):
        self.rawReply = QNetworkReply
        # self.redi


class CloudProjectsCache(QObject):
    projects_started = pyqtSignal()
    projects_updated = pyqtSignal()
    projects_error = pyqtSignal(str)
    project_files_started = pyqtSignal(str)
    project_files_updated = pyqtSignal(str)
    project_files_error = pyqtSignal(str, str)

    def __init__(self, network_manager: CloudNetworkAccessManager, parent=None) -> None:
        super(CloudProjectsCache, self).__init__(parent)

        self.preferences = Preferences()
        self.network_manager = network_manager
        self._error_reason = ""
        self._projects: Optional[List[CloudProject]] = None
        self._projects_reply: Optional[QNetworkReply] = None
        self._fs_watcher = QFileSystemWatcher()
        self._fs_watcher.directoryChanged.connect(self._on_directory_changed)

        self.network_manager.token_changed.connect(self._on_token_changed)
        self.projects_updated.connect(self._on_projects_updated)

        if self.network_manager.is_authenticated():
            self.refresh()

    @property
    def projects(self) -> Optional[List[CloudProject]]:
        return self._projects

    @property
    def error_reason(self) -> str:
        return self._error_reason

    @property
    def is_currently_open_project_cloud_local(self) -> bool:
        """Checks whether the currently opened QGIS project is a configured cloud project.

        NOTE there is a difference with `currently_opened_project()`, as this method does not
        depend on downloaded project list.

        Returns:
            bool: opened QGIS project is configured cloud project
        """
        project_dir = QgsProject.instance().homePath()
        project_ids = [p.id for p in self.projects] if self.projects else []

        for project_id, local_dir in self.preferences.value(
            "qfieldCloudProjectLocalDirs"
        ).items():
            if project_ids and project_id not in project_ids:
                continue

            if local_dir and Path(local_dir) == Path(project_dir):
                return True

        return False

    @property
    def currently_open_project(self) -> Optional[CloudProject]:
        """Returns the associated `CloudProject` instance of the currently opened QGIS project.
        If the cloud project list is not present, or the current project has no
        associated cloud project, return `None`.

        Returns:
            Optional[CloudProject]: associated cloud project
        """
        project_dir = QgsProject.instance().homePath()

        if not self.projects:
            return

        for project_id, local_dir in self.preferences.value(
            "qfieldCloudProjectLocalDirs"
        ).items():
            if not local_dir or Path(local_dir) != Path(project_dir):
                continue

            cloud_project = self.find_project(project_id)

            if cloud_project is not None:
                return cloud_project

    def get_unique_name(self, name: str) -> Optional[str]:
        if not self.projects:
            return None

        names = [p.name for p in self.projects]
        if name not in names:
            return name

        i = 1
        while True:
            new_name = f"{name}_{i}"

            if new_name not in names:
                return new_name

            i += 1

    def refresh(self) -> QNetworkReply:
        # TODO this abort appears sometimes in the UI, think how to hide it?
        if self._projects_reply:
            self._projects_reply.abort()

        self.projects_started.emit()
        self._projects_reply = self.network_manager.get_projects()
        self._projects_reply.finished.connect(
            lambda: self._on_get_projects_reply_finished(self._projects_reply)
        )

        return self._projects_reply

    def refresh_not_async(self) -> None:
        """Projects are requested in synchronous manner.
        The function name is cumbersome to discourage it's potential user.
        Better use `refresh()`
        """
        self.projects_started.emit()

        payload = self.network_manager.get_projects_not_async()

        self._projects = []

        for project_data in payload:
            self._projects.append(CloudProject(project_data))

        self.projects_updated.emit()

    def get_project_files(self, project_id: str) -> QNetworkReply:
        assert project_id

        self.project_files_started.emit(project_id)
        reply = self.network_manager.get_files(project_id)
        reply.finished.connect(
            lambda: self._on_get_project_files_reply_finished(
                reply, project_id=project_id
            )
        )
        return reply

    def find_project(self, project_id: str) -> Optional[CloudProject]:
        if not self._projects or not project_id:
            return

        for project in self._projects:
            if project.id == project_id:
                return project

    def refresh_filesystem_watchers(self, _dirpath: str = "") -> None:
        # TODO in theory we can update only the _dirpath. There are gothas with links etc, better keep it KISS for now
        if self._fs_watcher.directories():
            self._fs_watcher.removePaths(self._fs_watcher.directories())

        if self._projects:
            for project in self._projects:
                if not project.local_dir:
                    continue

                project_dirpath = Path(project.local_dir)
                for project_child_dirpath in project_dirpath.glob("**/"):
                    project_child_dirname = str(project_child_dirpath)

                    # ignore QFieldSync caches
                    if project_child_dirname.startswith(
                        str(project_dirpath.joinpath(".qfieldsync"))
                    ):
                        continue

                    self._fs_watcher.addPath(project_child_dirname)

                self._fs_watcher.addPath(project.local_dir)

    def _on_get_projects_reply_finished(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.OperationCanceledError:
            return

        self._projects_reply = None

        try:
            payload = self.network_manager.json_array(reply)
        except Exception as err:
            self.projects_error.emit(str(err))
            return

        self._projects = []

        for project_data in payload:
            cloud_project = CloudProject(project_data)

            self._projects.append(cloud_project)

        self.projects_updated.emit()

    def _on_get_project_files_reply_finished(
        self, reply: QNetworkReply, project_id: str = None
    ) -> None:
        assert project_id

        cloud_project = self.find_project(project_id)

        if not cloud_project:
            return

        try:
            payload = self.network_manager.json_array(reply)
        except Exception as err:
            payload = None
            self.project_files_error.emit(project_id, str(err))

        cloud_project.update_data({"cloud_files": payload})

        self.project_files_updated.emit(project_id)

    def _on_token_changed(self) -> None:
        self._projects = None
        self.projects_updated.emit()

        if self.network_manager.has_token():
            self.refresh()

    def _on_projects_updated(self) -> None:
        self.refresh_filesystem_watchers()

    def _on_directory_changed(self, dirpath: str) -> None:
        if not self._projects:
            return

        self.refresh_filesystem_watchers(dirpath)

        for project in self._projects:
            if dirpath == project.local_dir:
                project.refresh_files()
