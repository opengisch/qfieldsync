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

from qfieldsync.core.cloud_project import CloudProject
from typing import Any, Callable, Dict, IO, List, Union
import functools
import json
import shutil
import urllib.parse
from enum import IntFlag
from pathlib import Path

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal,
    QUrl,
    QUrlQuery,
)
from qgis.PyQt.QtNetwork import (
    QNetworkRequest,
    QNetworkReply,
    QHttpMultiPart,
    QHttpPart,
)
from qgis.core import QgsNetworkAccessManager, QgsProject

from qfieldsync.core.preferences import Preferences


class QFieldCloudNetworkManager(QgsNetworkAccessManager):
    
    token_changed = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor.
        """
        super(QFieldCloudNetworkManager, self).__init__(parent=parent)
        self.url = 'http://dev.qfield.cloud/api/v1/'
        self._token = ''
        self.projects_cache = CloudProjectsCache(self, self)


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


    def get_user(self, token: str) -> QNetworkReply:
        """Gets current user and if token is still valid"""
        return self.cloud_get('auth/user/', {
            'token': token
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
        if self._token == token:
            return

        self._token = token

        self.token_changed.emit()


    def has_token(self) -> bool:
        return self._token is not None and len(self._token) > 0


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


class ProjectTransferType(IntFlag):
    Upload = 1
    Download = 2
    Sync = 3


class ProjectTransferrer(QObject):
    # TODO show progress of individual files
    progress = pyqtSignal(ProjectTransferType, float)
    error = pyqtSignal(str)
    abort = pyqtSignal()
    finished = pyqtSignal()
    upload_progress = pyqtSignal(float)
    download_progress = pyqtSignal(float)
    upload_finished = pyqtSignal()
    download_finished = pyqtSignal()


    def __init__(self, network_manager: QFieldCloudNetworkManager, cloud_project: CloudProject, transfer_type: ProjectTransferType) -> None:
        super(ProjectTransferrer, self).__init__(parent=None)

        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self._files_to_upload = {}
        self._files_to_download = {}
        self.upload_files_finished = 0
        self.upload_files_total = 0
        self.upload_bytes_total_files_only = 0
        self.download_files_finished = 0
        self.download_files_total = 0
        self.download_bytes_total_files_only = 0
        self.is_aborted = False
        self.is_finished = False
        self.is_upload_active = False
        self.is_download_active = False
        self.replies = []
        self.temp_dir = Path(QgsProject.instance().homePath()).joinpath('.qfieldsync')
        self.type = transfer_type

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

        self.temp_dir.joinpath('backup').mkdir(parents=True, exist_ok=True)
        self.temp_dir.joinpath('upload').mkdir(parents=True, exist_ok=True)
        self.temp_dir.joinpath('download').mkdir(parents=True, exist_ok=True)


    def sync(self) -> None:
        self._make_backup()

        if self.type == ProjectTransferType.Upload:
            self.upload()
        elif self.type == ProjectTransferType.Download:
            self.download()
        elif self.type == ProjectTransferType.Sync:
            self.upload()
            self.upload_finished.connect(lambda: self.download())
        else:
            assert 0


    def download(self) -> None:
        if self.is_download_active:
            self.error.emit(self.tr('Already in progress'))
            return

        if self.is_finished:
            self.error.emit(self.tr('Already in finished'))
            return

        self.is_download_active = True
        reply = self.network_manager.get_files(self.cloud_project.id)
        reply.finished.connect(self.on_get_files_finished(reply)) # pylint: disable=no-value-for-parameter


    def upload(self, upload_all: bool = True) -> None:
        if self.is_upload_active:
            self.error.emit(self.tr('Already in progress'))
            return

        if self.is_finished:
            self.error.emit(self.tr('Already in finished'))
            return

        self.is_upload_active = True
        
        assert self.cloud_project.local_dir

        filenames = self.cloud_project.local_files if upload_all else self.cloud_project.local_only_files
        project_path = QgsProject.instance().homePath()

        for filename in filenames:
            path = Path(project_path).joinpath(filename)
            temp_file = self.temp_dir.joinpath('upload', filename)
            file_size = path.stat().st_size

            temp_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, temp_file)

            self._files_to_upload[filename] = {
                'bytes_total': file_size,
                'bytes_sent': 0,
            }
            self.upload_files_total += 1
            self.upload_bytes_total_files_only += file_size

            reply = self.network_manager.cloud_upload_files('files/' + self.cloud_project.id + '/' + filename, filenames=[str(temp_file)])
            reply.uploadProgress.connect(self.on_upload_file_progress(reply, filename=filename)) # pylint: disable=no-value-for-parameter
            reply.finished.connect(self.on_upload_file_finished(reply, filename=filename))

            self.replies.append(reply)

        if self.upload_files_total == 0:
            self.upload_finished.emit()

            if self.type == ProjectTransferType.Upload:
                self.finished.emit()


    @QFieldCloudNetworkManager.reply_wrapper
    def on_upload_file_progress(self, reply: QNetworkReply, bytes_sent: int, bytes_total: int, filename: str):
        # there is always at least a few bytes to send, so ignore this situation
        if bytes_total == 0:
            return

        self._files_to_upload[filename]['bytes_sent'] = bytes_sent
        self._files_to_upload[filename]['bytes_total'] = bytes_total

        bytes_sent_sum = sum([self._files_to_upload[filename]['bytes_sent'] for filename in self._files_to_upload])
        bytes_total_sum = max(sum([self._files_to_upload[filename]['bytes_total'] for filename in self._files_to_upload]), self.upload_bytes_total_files_only)

        fraction = min(bytes_sent_sum / bytes_total_sum, 1) if self.upload_bytes_total_files_only > 0 else 1

        self.upload_progress.emit(fraction)
        self.progress.emit(ProjectTransferType.Upload, fraction)


    @QFieldCloudNetworkManager.reply_wrapper
    def on_upload_file_finished(self, reply: QNetworkReply, filename: str):
        if reply.error() != QNetworkReply.NoError:
            self.error.emit(self.tr('Uploading file "{}" failed: {}'.format(filename, QFieldCloudNetworkManager.error_reason(reply))))
            self.abort_requests()
            return

        self.upload_files_finished += 1

        if self.upload_files_finished == self.upload_files_total:
            self.upload_finished.emit()

            if self.type == ProjectTransferType.Upload:
                self.finished.emit()


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def on_get_files_finished(self, reply: QNetworkReply, payload: Dict) -> None:
        if reply.error() != QNetworkReply.NoError or payload is None:
            self.error.emit(self.tr('Obtaining project files list failed: {}'.format(QFieldCloudNetworkManager.error_reason(reply))))
            self.abort_requests()
            return

        self.cloud_project.cloud_files = payload

        for file_obj in self.cloud_project.cloud_files:
            filename = file_obj['name']
            self.download_bytes_total_files_only += file_obj['size']

            self._files_to_download[filename] = {
                'bytes_total': file_obj['size'],
                'bytes_received': 0,
            }

            temp_destination = Path(self.temp_dir.joinpath('download', filename))
            temp_destination.parent.mkdir(parents=True, exist_ok=True)

            reply = self.network_manager.get_file(self.cloud_project.id + '/' + str(filename) + '/', str(temp_destination))
            reply.downloadProgress.connect(self.on_download_file_progress(reply, filename=filename)) # pylint: disable=no-value-for-parameter
            reply.finished.connect(self.on_download_file_finished(reply, filename=filename))

            self.download_files_total += 1
            self.replies.append(reply)


    @QFieldCloudNetworkManager.reply_wrapper
    def on_download_file_progress(self, reply: QNetworkReply, bytes_received: int, bytes_total: int, filename: str = '') -> None:
        self._files_to_download[filename]['bytes_received'] = bytes_received
        self._files_to_download[filename]['bytes_total'] = bytes_total

        bytes_received_sum = sum([self._files_to_download[filename]['bytes_received'] for filename in self._files_to_download])
        bytes_total_sum = max(sum([self._files_to_download[filename]['bytes_total'] for filename in self._files_to_download]), self.download_bytes_total_files_only)

        fraction = min(bytes_received_sum / bytes_total_sum, 1) if self.download_bytes_total_files_only > 0 else 1

        self.download_progress.emit(fraction)
        self.progress.emit(ProjectTransferType.Download, fraction)



    @QFieldCloudNetworkManager.reply_wrapper
    def on_download_file_finished(self, reply: QNetworkReply, filename: str = ''):
        if reply.error() != QNetworkReply.NoError:
            self.error.emit(self.tr('Downloading file "{}" failed: {}'.format(filename, QFieldCloudNetworkManager.error_reason(reply))))
            self.abort_requests()
            return

        if self.download_files_finished == self.download_files_total:
            self.download_progress.emit(1)
            self.progress.emit(ProjectTransferType.Download, 1)
            self.download_finished.emit()
            self.finished.emit()
            return

        if not Path(filename).exists():
            self.error.emit(self.tr('Downloaded file "{}" not found!'.format(filename)))
            self.abort_requests()
            return

        self.download_files_finished += 1


    def abort_requests(self):
        if self.is_aborted:
            return

        self.is_aborted = True

        for reply in self.replies:
            if not reply.isFinished():
                reply.abort()

        self.abort.emit()


    def _make_backup(self):
        pass


    def rollback_backup(self):
        pass

# TODO do i really need a singleton?
class QObjectSingleton(type(QObject)):
    _instances = {}

    def __call__(self, *args, **kwargs):
        if self not in self._instances:
            self._instances[self] = super(QObjectSingleton, self).__call__(*args, **kwargs)
            
        return self._instances[self]

class CloudProjectsCache(QObject, metaclass=QObjectSingleton):

    projects_started = pyqtSignal()
    projects_updated = pyqtSignal()
    projects_error = pyqtSignal(str)
    project_files_started = pyqtSignal(str)
    project_files_updated = pyqtSignal(str)
    project_files_error = pyqtSignal(str, str)

    def __init__(self, network_manager: QFieldCloudNetworkManager, parent=None):
        super(CloudProjectsCache, self).__init__(parent)

        self.preferences = Preferences()
        self.network_manager = network_manager
        self._error_reason = ''
        self._projects = None
        self._projects_reply = None

        self.network_manager.token_changed.connect(self._on_token_changed)

        if self.network_manager.has_token():
            self.refresh()


    @property
    def projects(self):
        return self._projects


    @property
    def error_reason(self):
        return self._error_reason


    @property
    def currently_open_project(self):
        project_dir = QgsProject.instance().homePath()

        for project_id, local_dir in self.preferences.value('qfieldCloudProjectLocalDirs').items():
            if local_dir != project_dir:
                continue
            
            cloud_project = self.find_project(project_id)

            if cloud_project is not None:
                return cloud_project


    def refresh(self):
        if self._projects_reply:
            self._projects_reply.abort()

        self.projects_started.emit()
        self._projects_reply = self.network_manager.get_projects()
        self._projects_reply.finished.connect(self._on_get_projects_reply_finished(self._projects_reply)) # pylint: disable=no-value-for-parameter

        return self._projects_reply


    def get_project_files(self, project_id):
        assert project_id

        self.project_files_started.emit(project_id)
        reply = self.network_manager.get_files(project_id)
        reply.finished.connect(self._on_get_project_files_reply_finished(reply, project_id=project_id)) # pylint: disable=no-value-for-parameter
        return reply


    def find_project(self, project_id):
        if not self._projects or not project_id:
            return

        for project in self._projects:
            if project.id == project_id:
                return project


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def _on_get_projects_reply_finished(self, reply, payload):
        self._projects_reply = None

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projects_error.emit(QFieldCloudNetworkManager.error_reason(reply))
            return

        self._projects = []

        for project_data in payload:
            self._projects.append(CloudProject(project_data))

        self.projects_updated.emit()


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def _on_get_project_files_reply_finished(self, reply, payload, project_id=None):
        assert project_id

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.project_files_error.emit(project_id, QFieldCloudNetworkManager.error_reason(reply))
            return

        cloud_project = self.find_project(project_id)

        if not cloud_project:
            return

        cloud_project.cloud_files = payload

        self.project_files_updated.emit(project_id)


    def _on_token_changed(self):
        self._projects = None
        self.projects_updated.emit()

        if self.network_manager.has_token():
            self.refresh()
