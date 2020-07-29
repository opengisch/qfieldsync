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


import os
from typing import Any, Callable, Dict, List, Union
import requests
import functools
import json
import mimetypes
import urllib.parse
from glob import glob
from pathlib import Path

from qfieldsync.core import project

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


    def set_token(self, token: str) -> None:
        self._token = token


    def cloud_get(self, uri: Union[str, List[str]], params: Dict[str, Any] = {}) -> QNetworkReply:
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

        return reply


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

        return reply


    def cloud_upload_files(self, uri: Union[str, List[str]], filenames: Union[str, List[str]], payload: Dict = None) -> QNetworkReply:
        url = QUrl(self.url + self._prepare_uri(uri))

        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
        request.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')

        if self._token:
            request.setRawHeader(b'Authorization', 'Token {}'.format(self._token).encode('utf-8'))

        multi_part = QHttpMultiPart(QHttpMultiPart.FormDataType)

        # most of the time there is no other payload
        if payload is not None:
            json_part = QHttpPart()

            json_part.setHeader(QNetworkRequest.ContentTypeHeader, 'application/json')
            json_part.setHeader(QNetworkRequest.ContentDispositionHeader, 'form-data; name=\"text\"')
            json_part.setBody(json.dumps(payload).encode('utf-8'))
            
            multi_part.append(json_part)

        # now attach each file
        for filename in filenames:
            file_part = QHttpPart()
            file = QFile(filename, multi_part)

            # file_part.setHeader(QNetworkRequest.ContentTypeHeader, mimetypes.guess_type(filename ).encode('utf-8') ;
            file_part.setHeader(QNetworkRequest.ContentDispositionHeader, "form-data; name=\"file\"; filename=\"{}\"".format(filename))
            file_part.setBodyDevice(file)

            multi_part.append(file_part)

        reply = self.post(request, multi_part)
        reply.sslErrors.connect(lambda sslErrors: reply.ignoreSslErrors(sslErrors))

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

    print(data, response, headers, response.text)

    response.raise_for_status()

    return response.json()


class ProjectUploader(QObject):
    progress_uploaded = pyqtSignal(int, int, str)


    def __init__(self, project_id, local_dir, is_new_project=False):
        super(ProjectUploader, self).__init__(parent=None)

        self.project_id = project_id
        self.local_dir = local_dir
        self.is_new_project = is_new_project


    def upload(self):
        file_names = glob(os.path.join(self.local_dir, '**'), recursive=True)

        # upload the QGIS project file at the end
        file_names.sort(key=lambda s: Path(s).suffix in ('.qgs', '.qgz') )

        # do not upload the project file, if it is already there
        if not self.is_new_project:
            file_names = file_names[:-2]

        file_paths = [Path(f) for f in file_names if Path(f).is_file()]
        total_size = sum([p.stat().st_size for p in file_paths])
        total_transferred = 0

        for local_path in file_paths:
            remote_path = local_path.relative_to(self.local_dir)

            url = BASE_URL + 'files/' + self.project_id + '/' + str(remote_path) + '/'
            headers = {
                'Authorization': 'token {}'.format(token),
            }

            with open(local_path, 'rb')  as local_file:
                files = {'file': local_file}

                self.progress_uploaded.emit(total_transferred, total_size, str(local_path))

                response = requests.post(
                    url,  
                    headers=headers,
                    files=files,
                    stream=True
                )
                response.raise_for_status()

                total_transferred += local_path.stat().st_size

                if total_transferred == total_size:
                    self.progress_uploaded.emit(total_transferred, total_size, "Done!")




class ProjectFileTransfer(QObject):
    progress_uploaded = pyqtSignal(int, int, str)


    def __init__(self, network_manager, project_id, local_dir, is_new_project=False):
        super(ProjectFileTransfer, self).__init__(parent=None)

        self.network_manager = network_manager
        self.project_id = project_id
        self.local_dir = local_dir
        self.is_new_project = is_new_project


    def upload(self):
        file_names = glob(os.path.join(self.local_dir, '**'), recursive=True)

        # upload the QGIS project file at the end
        file_names.sort(key=lambda s: Path(s).suffix in ('.qgs', '.qgz') )

        # do not upload the project file, if it is already there
        if not self.is_new_project:
            file_names = file_names[:-2]

        file_paths = [Path(f) for f in file_names if Path(f).is_file()]
        total_size = sum([p.stat().st_size for p in file_paths])
        total_transferred = 0

        for local_path in file_paths:
            remote_path = local_path.relative_to(self.local_dir)

            url = BASE_URL + 'files/' + self.project_id + '/' + str(remote_path) + '/'
            headers = {
                'Authorization': 'token {}'.format(token),
            }

            with open(local_path, 'rb')  as local_file:
                files = {'file': local_file}

                self.progress_uploaded.emit(total_transferred, total_size, str(local_path))

                response = requests.post(
                    url,  
                    headers=headers,
                    files=files,
                    stream=True
                )
                response.raise_for_status()

                total_transferred += local_path.stat().st_size

                if total_transferred == total_size:
                    self.progress_uploaded.emit(total_transferred, total_size, "Done!")

