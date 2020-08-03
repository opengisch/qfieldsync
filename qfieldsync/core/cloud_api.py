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

from typing import Any, Callable, Dict, IO, List, Union
import requests
import functools
import json
import shutil
import urllib.parse
from pathlib import Path

from qfieldsync.core import project

from PyQt5.QtCore import QTemporaryDir
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal,
    QUrl,
    QUrlQuery,
    QFile,
)
from qgis.PyQt.QtNetwork import (
    QNetworkRequest,
    QNetworkReply,
    QHttpMultiPart,
    QHttpPart,
)
from qgis.core import QgsNetworkAccessManager



BASE_URL = 'http://dev.qfield.cloud/api/v1/'

# store the current token
token = None


class QFieldCloudNetworkManager(QgsNetworkAccessManager):


    def __init__(self, parent=None):
        """Constructor.
        """
        super(QFieldCloudNetworkManager, self).__init__(parent=parent)
        self.url = BASE_URL
        self._token = ''


    @staticmethod
    def error_reason(reply: QNetworkReply) -> str:
        return reply.errorString()

    @staticmethod
    def read_json(func) -> Callable:
        @functools.wraps(func)
        def wrapper(self, reply: QNetworkReply, *args, **kwargs):
            payload = {}
            payload_str = ''

            try:
                payload_str = str(reply.readAll().data(), encoding='utf-8')
                payload = json.loads(payload_str)
            except Exception as error:
                print('Error while parsing JSON response:\n' + str(error) + '\n' + payload_str)
                payload = None

            return func(self, reply, payload, *args, **kwargs)
        
        return wrapper

    @staticmethod
    def reply_wrapper(func) -> Callable:
        @functools.wraps(func)
        def closure(self, reply: QNetworkReply, **outerKwargs):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(self, reply, *args, **{**kwargs, **outerKwargs})
            return wrapper

        return closure


    def login(self, username: str, password: str) -> QNetworkReply:
        """Login to QFieldCloud"""
        
        return self.cloud_post('auth/login/', {
            'username': username,
            'password': password,
        })


    def logout(self) -> QNetworkReply:
        """Logout to QFieldCloud"""

        return self.cloud_post('auth/logout/')


    def get_projects(self):
        """Get QFieldCloud projects"""

        return self.cloud_get('projects/')


    def create_project(self, name: str, owner: str, description: str, private: bool) -> QNetworkReply:
        """Create a new QFieldCloud project"""

        return self.cloud_post('projects/', {
            'name': name,
            'owner': owner,
            'description': description,
            'private': private,
        })


    def update_project(self, project_id: str, name: str, owner: str, description: str, private: bool) -> QNetworkReply:
        """Update an existing QFieldCloud project"""

        return self.cloud_put(['projects', project_id], {
            'name': name,
            'owner': owner,
            'description': description,
            'private': private,
        })

    def delete_project(self, project_id: str) -> QNetworkReply:
        """Delete an existing QFieldCloud project"""

        return self.cloud_delete(['projects', project_id])


    def get_files(self, project_id: str, client: str = "qgis") -> QNetworkReply:
        """"Get project files and their versions"""

        return self.cloud_get(['files', project_id], {"client": client})

    def get_file(self, filename: str, local_filename: str) -> QNetworkReply:
        """"Download file"""

        return self.cloud_get('files/' + filename, local_filename=local_filename)


    def set_token(self, token: str) -> None:
        """Sets QFieldCloud authentication token to be used by all the following requests. Set to `None` to disable token authentication."""
        self._token = token


    def cloud_get(self, uri: Union[str, List[str]], params: Dict[str, Any] = {}, local_filename: str = None) -> QNetworkReply:
        """Issues a GET HTTP request"""
        url = QUrl(self.url + self._prepare_uri(uri))
        query = QUrlQuery()

        assert isinstance(params, dict)

        for param, value in params.items():
            query.addQueryItem(param, str(value))

        url.setQuery(query)

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')

        if self._token:
            request.setRawHeader(b'Authorization', 'Token {}'.format(self._token).encode('utf-8'))

        reply = self.get(request)
        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        if local_filename is not None:
            file = open(local_filename, 'wb')
            reply.finished.connect(lambda: self._on_cloud_get_download_finished(reply, file=file))

        return reply


    def _on_cloud_get_download_finished(self, reply: QNetworkReply, file: IO) -> None:
        assert file.write(reply.readAll()) != -1, 'Error while writing to file "{}"'.format(file.name)
        file.close()


    def cloud_post(self, uri: Union[str, List[str]], payload: Dict = None) -> QNetworkReply:
        url = QUrl(self.url + self._prepare_uri(uri))

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')

        if self._token:
            request.setRawHeader(b'Authorization', 'Token {}'.format(self._token).encode('utf-8'))

        payload_bytes = b'' if payload is None else json.dumps(payload).encode('utf-8')
        reply = self.post(request, payload_bytes)
        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        return reply


    def cloud_put(self, uri: Union[str, List[str]], payload: Dict = None) -> QNetworkReply:
        url = QUrl(self.url + self._prepare_uri(uri))

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')

        if self._token:
            request.setRawHeader(b'Authorization', 'Token {}'.format(self._token).encode('utf-8'))

        payload_bytes = b'' if payload is None else json.dumps(payload).encode('utf-8')
        reply = self.put(request, payload_bytes)
        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        return reply


    def cloud_delete(self, uri: Union[str, List[str]]) -> QNetworkReply:
        url = QUrl(self.url + self._prepare_uri(uri))

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')

        if self._token:
            request.setRawHeader(b'Authorization', 'Token {}'.format(self._token).encode('utf-8'))

        reply = self.deleteResource(request)
        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)

        return reply


    def cloud_upload_files(self, uri: Union[str, List[str]], filenames: List[str], payload: Dict = None) -> QNetworkReply:
        url = QUrl(self.url + self._prepare_uri(uri))

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)

        if self._token:
            request.setRawHeader(b'Authorization', 'Token {}'.format(self._token).encode('utf-8'))

        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)
        multi_part.setParent(self)

        # most of the time there is no other payload
        if payload is not None:
            json_part = QHttpPart()

            json_part.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')
            json_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name=\"json\"')
            json_part.setBody(json.dumps(payload).encode('utf-8'))
            
            multi_part.append(json_part)

        # now attach each file
        for filename in filenames:
            # this might be optimized by usung QFile and QHttpPart.setBodyDevice, but didn't work on the first
            filedata = open(filename, 'rb').read()

            file_part = QHttpPart()
            file_part.setBody(filedata)
            file_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"file\"; filename=\"{}\"".format(filename))

            multi_part.append(file_part)

        reply = self.post(request, multi_part)
        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))
        reply.setParent(self)
        multi_part.setParent(reply)

        return reply


    def _prepare_uri(self, uri: Union[str, List[str]]):
        encoded_uri = uri
        if not isinstance(uri, str):
            encoded_parts = []
            
            for part in uri:
                encoded_parts.append(urllib.parse.quote(part))

            encoded_uri = '/'.join(encoded_parts)

        if encoded_uri[-1] != '/':
            encoded_uri += '/'
        
        return encoded_uri



def set_token(new_token):
    global token
    token = new_token


def get_error_reason(response):
    try:
        resp = response.json()
        return resp['detail']
    except:
        return 'Unknown reason'


def login(username, password):

    url = BASE_URL + 'auth/login/'
    data = {
        "username": username,
        "password": password,
    }

    response = requests.post(
        url,
        data=data,
    )



    response.raise_for_status()
    resp = response.json()
    set_token(resp['token'])

    return resp


def logout():
    """Login to QFieldCloud and print the token"""

    url = BASE_URL + 'auth/logout/'

    headers = {'Authorization': 'token {}'.format(token)}
    response = requests.post(
        url,
        headers=headers,
    )

    response.raise_for_status()
    set_token(None)

    return response.json()


def create_project(name, owner, description, private=True):
    """Create a new QFieldCloud project"""

    url = BASE_URL + 'projects/'
    data = {
        "name": name,
        "owner": owner,
        "description": description,
        "private": private
    }

    headers = {'Authorization': 'token {}'.format(token)}

    response = requests.post(
        url,
        data=data,
        headers=headers,
    )

    response.raise_for_status()

    return response.json()


class ProjectTransferrer(QObject):
    # TODO show progress of individual files
    progress = pyqtSignal(float)
    error = pyqtSignal(str)
    abort = pyqtSignal()
    finished = pyqtSignal()


    def __init__(self, network_manager, cloud_project):
        super(ProjectTransferrer, self).__init__(parent=None)

        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self._files_to_transfer = {}
        self.files_finished = 0
        self.files_total = 0
        self.bytes_total_files_only = 0
        self.is_aborted = False
        self.is_finished = False
        self.is_active = False
        self.replies = []
        self.temp_dir = QTemporaryDir('qfieldcloud_project')


    def download(self) -> None:
        if self.is_active:
            self.error.emit(self.tr('Already in progress'))
            return

        if self.is_finished:
            self.error.emit(self.tr('Already in finished'))
            return

        self.is_active = True
        reply = self.network_manager.get_files(self.cloud_project.id)
        reply.finished.connect(self.on_get_files_finished(reply))


    def upload(self, upload_all: bool) -> None:
        if self.is_active:
            self.error.emit(self.tr('Already in progress'))
            return

        if self.is_finished:
            self.error.emit(self.tr('Already in finished'))
            return

        self.is_active = True
        
        assert self.cloud_project.local_dir is not None

        for file in Path(self.cloud_project.local_dir).glob('**/*.*'):
            relative_filename = str(file.relative_to(self.cloud_project.local_dir))
            temp_file = Path(self.temp_dir.path() + '/' + relative_filename)

            shutil.copyfile(file, temp_file)

            self._files_to_transfer[relative_filename] = {
                'bytes_total': file.stat().st_size,
                'bytes_sent': 0,
            }
            self.files_total += 1
            self.bytes_total_files_only += file.stat().st_size

            reply = self.network_manager.cloud_upload_files('files/' + self.cloud_project.id + '/' + relative_filename, filenames=[str(temp_file)])
            reply.uploadProgress.connect(self.on_upload_file_progress(reply, filename=relative_filename)) # types: ignore
            reply.finished.connect(self.on_upload_file_finished(reply, filename=relative_filename))

            self.replies.append(reply)

        if self.files_total == 0:
            self.finished.emit()


    @QFieldCloudNetworkManager.reply_wrapper
    def on_upload_file_progress(self, reply: QNetworkReply, bytes_sent: int, bytes_total: int, filename: str):
        # there is always at least a few bytes to send, so ignore this situation
        if bytes_total == 0:
            return

        self._files_to_transfer[filename]['bytes_sent'] = bytes_sent
        self._files_to_transfer[filename]['bytes_total'] = bytes_total

        bytes_sent_sum = sum([self._files_to_transfer[filename]['bytes_sent'] for filename in self._files_to_transfer])
        bytes_total_sum = max(sum([self._files_to_transfer[filename]['bytes_total'] for filename in self._files_to_transfer]), self.bytes_total_files_only)

        if self.bytes_total_files_only > 0:
            self.progress.emit(min(bytes_sent_sum / bytes_total_sum, 1))
        else:
            self.progress.emit(1)


    @QFieldCloudNetworkManager.reply_wrapper
    def on_upload_file_finished(self, reply: QNetworkReply, filename: str):
        if reply.error() != QNetworkReply.NoError:
            self.error.emit(self.tr('Uploading file "{}" failed: {}'.format(filename, QFieldCloudNetworkManager.error_reason(reply))))
            self.abort_requests()
            return

        self.files_finished += 1

        if self.files_finished == self.files_total:
            self.finished.emit()


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def on_get_files_finished(self, reply: QNetworkReply, payload: Dict) -> None:
        if reply.error() != QNetworkReply.NoError or payload is None:
            self.error.emit(self.tr('Obtaining project files list failed: {}'.format(QFieldCloudNetworkManager.error_reason(reply))))
            self.abort_requests()
            return

        self.cloud_project.files = payload

        for file_obj in self.cloud_project.files:
            filename = file_obj['name']
            self.bytes_total_files_only += file_obj['size']

            self._files_to_transfer[filename] = {
                'bytes_total': file_obj['size'],
                'bytes_received': 0,
            }

            temp_destination = Path(self.temp_dir.path() + '/' + filename)
            temp_destination.parent.mkdir(parents=True, exist_ok=True)

            reply = self.network_manager.get_file(self.cloud_project.id + '/' + str(filename) + '/', str(temp_destination))
            reply.downloadProgress.connect(self.on_download_file_progress(reply, filename=filename))
            reply.finished.connect(self.on_download_file_finished(reply, filename=filename))

            self.replies.append(reply)


    @QFieldCloudNetworkManager.reply_wrapper
    def on_download_file_progress(self, reply: QNetworkReply, bytes_received: int, bytes_total: int, filename: str = '') -> None:
        self._files_to_transfer[filename]['bytes_received'] = bytes_received
        self._files_to_transfer[filename]['bytes_total'] = bytes_total

        bytes_received_sum = sum([self._files_to_transfer[filename]['bytes_received'] for filename in self._files_to_transfer])
        bytes_total_sum = max(sum([self._files_to_transfer[filename]['bytes_total'] for filename in self._files_to_transfer]), self.bytes_total_files_only)

        if self.bytes_total_files_only > 0:
            self.progress.emit(min(bytes_received_sum / bytes_total_sum, 1))
        else:
            self.progress.emit(1)


    @QFieldCloudNetworkManager.reply_wrapper
    def on_download_file_finished(self, reply: QNetworkReply, filename: str = ''):
        if reply.error() != QNetworkReply.NoError:
            self.error.emit(self.tr('Downloading file "{}" failed: {}'.format(filename, QFieldCloudNetworkManager.error_reason(reply))))
            self.abort_requests()
            return

        if self.files_finished == self.files_total:
            self.finished.emit()
            return

        if not Path(filename).exists():
            self.error.emit(self.tr('Downloaded file "{}" not found!'.format(filename)))
            self.abort_requests()
            return

        self.files_finished += 1


    def abort_requests(self):
        if self.is_aborted:
            return

        self.is_aborted = True

        for reply in self.replies:
            reply.abort()

        self.abort.emit()

