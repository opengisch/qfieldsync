# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
                             -------------------
        begin                : 2020-08-19
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


from typing import List
import shutil
from pathlib import Path

from qgis.PyQt.QtCore import pyqtSignal, QObject
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.core import QgsProject
from qgis.utils import iface

from qfieldsync.core.project import ProjectConfiguration
from qfieldsync.core.preferences import Preferences
from qfieldsync.core.cloud_api import CloudNetworkAccessManager, CloudException
from qfieldsync.core.cloud_project import CloudProject, ProjectFile
from qfieldsync.core.offline_converter import OfflineConverter
from qfieldsync.utils.exceptions import NoProjectFoundError
from qfieldsync.utils.file_utils import get_project_in_folder, import_file_checksum, copy_images
from qfieldsync.utils.qgis_utils import open_project, import_checksums_of_project


class CloudTransferrer(QObject):
    # TODO show progress of individual files
    progress = pyqtSignal(float)
    error = pyqtSignal(str)
    abort = pyqtSignal()
    finished = pyqtSignal()
    upload_progress = pyqtSignal(float)
    download_progress = pyqtSignal(float)
    upload_finished = pyqtSignal()
    download_finished = pyqtSignal()


    def __init__(self, network_manager: CloudNetworkAccessManager, cloud_project: CloudProject) -> None:
        super(CloudTransferrer, self).__init__(parent=None)

        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self._files_to_upload = {}
        self._files_to_download = {}
        self.upload_files_finished = 0
        self.upload_bytes_total_files_only = 0
        self.download_files_finished = 0
        self.download_bytes_total_files_only = 0
        self.is_aborted = False
        self.is_started = False
        self.is_finished = False
        self.is_upload_active = False
        self.is_download_active = False
        self.replies = []
        self.temp_dir = Path(QgsProject.instance().homePath()).joinpath('.qfieldsync')

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

        self.temp_dir.mkdir()
        self.temp_dir.joinpath('backup').mkdir()
        self.temp_dir.joinpath('upload').mkdir()
        self.temp_dir.joinpath('download').mkdir()
        self.temp_dir.joinpath('export').mkdir()

        for project_file in self.cloud_project.get_files():
            project_file.export_dir = self.temp_dir.joinpath('export')

        # TODO find a better way to obtain the offline editing
        self.offline_editing = self.network_manager.offline_editing

        self.upload_finished.connect(self._on_upload_finished)
        self.download_finished.connect(self._on_download_finished)

        self.import_qfield_project()


    def __del__(self) -> None:
        for project_file in self.cloud_project.get_files():
            project_file.export_dir = None


    def convert(self) -> OfflineConverter:
        offline_convertor = OfflineConverter(
            QgsProject.instance(), 
            str(self.temp_dir.joinpath('export')), 
            iface.mapCanvas().extent(),
            self.offline_editing)

        offline_convertor.convert()

        self.cloud_project._refresh_files()

        return offline_convertor


    def sync(self, files_to_upload: List[ProjectFile], files_to_download: List[ProjectFile]) -> None:
        assert not self.is_started
        
        self.is_started = True

        # prepare the files to be uploaded, copy them in a temporary destination
        for project_file in files_to_upload:
            assert project_file.local_path

            filename = project_file.name

            temp_filename = self.temp_dir.joinpath('upload', filename)
            temp_filename.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(project_file.local_path, temp_filename)

            self.upload_bytes_total_files_only += project_file.local_size
            self._files_to_upload[filename] = {
                'project_file': project_file,
                'bytes_total': project_file.local_size,
                'bytes_transferred': 0,
                'temp_filename': temp_filename,
            }
        
        # prepare the files to be downloaded, download them in a temporary destination
        for project_file in files_to_download:
            filename = project_file.name

            temp_filename = self.temp_dir.joinpath('download', filename)
            temp_filename.parent.mkdir(parents=True, exist_ok=True)

            self.download_bytes_total_files_only += project_file.size
            self._files_to_download[filename] = {
                'project_file': project_file,
                'bytes_total': project_file.size,
                'bytes_transferred': 0,
                'temp_filename': temp_filename,
            }

        self._make_backup()
        self._upload()


    def _upload(self) -> None:
        assert not self.is_upload_active, 'Upload in progress'
        assert not self.is_download_active, 'Download in progress'

        self.is_upload_active = True

        # nothing to upload
        if len(self._files_to_upload) == 0:
            self.upload_progress.emit(1)
            self.upload_finished.emit()
            # NOTE check _on_upload_finished
            return

        assert self.cloud_project.local_dir

        for filename in self._files_to_upload:
            temp_filename = self._files_to_upload[filename]['temp_filename']

            reply = self.network_manager.cloud_upload_files('files/' + self.cloud_project.id + '/' + filename, filenames=[str(temp_filename)])
            reply.uploadProgress.connect(lambda s, t: self._on_upload_file_progress(reply, s, t, filename=filename))
            reply.finished.connect(lambda: self._on_upload_file_finished(reply, filename=filename))

            self.replies.append(reply)


    def _download(self) -> None:
        assert not self.is_upload_active, 'Upload in progress'
        assert not self.is_download_active, 'Download in progress'

        self.is_download_active = True

        # nothing to download
        if len(self._files_to_download) == 0:
            self.download_progress.emit(1)
            self.download_finished.emit()
            return

        for filename in self._files_to_download:
            temp_filename = self._files_to_download[filename]['temp_filename']

            reply = self.network_manager.get_file(self.cloud_project.id + '/' + str(filename) + '/', str(temp_filename))
            reply.downloadProgress.connect(lambda r, t: self._on_download_file_progress(reply, r, t, filename=filename))
            reply.finished.connect(lambda: self._on_download_file_finished(reply, filename=filename, temp_filename=temp_filename))

            self.replies.append(reply)


    def _on_upload_file_progress(self, reply: QNetworkReply, bytes_sent: int, bytes_total: int, filename: str) -> None:
        # there are always at least a few bytes to send, so ignore this situation
        if bytes_total == 0:
            return

        self._files_to_upload[filename]['bytes_transferred'] = bytes_sent
        self._files_to_upload[filename]['bytes_total'] = bytes_total

        bytes_sent_sum = sum([self._files_to_upload[filename]['bytes_transferred'] for filename in self._files_to_upload])
        bytes_total_sum = max(sum([self._files_to_upload[filename]['bytes_total'] for filename in self._files_to_upload]), self.upload_bytes_total_files_only)

        fraction = min(bytes_sent_sum / bytes_total_sum, 1) if self.upload_bytes_total_files_only > 0 else 1

        self.upload_progress.emit(fraction)


    def _on_upload_file_finished(self, reply: QNetworkReply, filename: str) -> None:
        try:
            CloudNetworkAccessManager.handle_response(reply, False)
        except CloudException as err:
            self.error.emit(self.tr('Uploading file "{}" failed: {}'.format(filename, str(err))))
            self.abort_requests()
            return

        self.upload_files_finished += 1

        if self.upload_files_finished == len(self._files_to_upload):
            self.upload_progress.emit(1)
            self.upload_finished.emit()
            # NOTE check _on_upload_finished
            return


    def _on_download_file_progress(self, reply: QNetworkReply, bytes_received: int, bytes_total: int, filename: str = '') -> None:
        self._files_to_download[filename]['bytes_transferred'] = bytes_received
        self._files_to_download[filename]['bytes_total'] = bytes_total

        bytes_received_sum = sum([self._files_to_download[filename]['bytes_transferred'] for filename in self._files_to_download])
        bytes_total_sum = max(sum([self._files_to_download[filename]['bytes_total'] for filename in self._files_to_download]), self.download_bytes_total_files_only)

        fraction = min(bytes_received_sum / bytes_total_sum, 1) if self.download_bytes_total_files_only > 0 else 1

        self.download_progress.emit(fraction)


    def _on_download_file_finished(self, reply: QNetworkReply, filename: str = '', temp_filename: str = '') -> None:
        try:
            CloudNetworkAccessManager.handle_response(reply, False)
        except CloudException as err:
            self.error.emit(self.tr('Downloading file "{}" failed: {}'.format(filename, str(err))))
            self.abort_requests()
            return

        self.download_files_finished += 1

        if not Path(temp_filename).exists():
            self.error.emit(self.tr('Downloaded file "{}" not found!'.format(temp_filename)))
            self.abort_requests()
            return

        if self.download_files_finished == len(self._files_to_download):
            self._temp_dir2main_dir('download')
            self.download_progress.emit(1)
            self.download_finished.emit()
            return

    def _on_upload_finished(self) -> None:
        self.is_upload_active = False
        self._download()


    def _on_download_finished(self) -> None:
        self.is_download_active = False
        self.is_finished = True
        self.finished.emit()


    def abort_requests(self) -> None:
        if self.is_aborted:
            return

        self.is_aborted = True

        for reply in self.replies:
            if not reply.isFinished():
                reply.abort()

        self.abort.emit()


    def _make_backup(self) -> None:
        for project_file in [
            *list(map(lambda f: f['project_file'], self._files_to_upload.values())),
            *list(map(lambda f: f['project_file'], self._files_to_download.values())),
        ]:
            if project_file.local_path and project_file.local_path.exists():
                dest = self.temp_dir.joinpath('backup', project_file.path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copyfile(project_file.local_path, dest)


    def _temp_dir2main_dir(self, subdir: str) -> None:
        subdir_path = self.temp_dir.joinpath(subdir)

        assert subdir_path.exists()

        for filename in subdir_path.glob('**/*'):
            if filename.is_dir():
                filename.mkdir(parents=True, exist_ok=True)
                continue

            relative_filename = str(Path(filename).relative_to(subdir_path))

            shutil.copyfile(filename, self._files_to_download[relative_filename]['project_file'].local_path)


    def import_qfield_project(self):
        import_dir = str(self.temp_dir.joinpath('download'))

        try:
            current_import_file_checksum = import_file_checksum(import_dir)
            imported_files_checksums = import_checksums_of_project(import_dir)

            if (imported_files_checksums and current_import_file_checksum and current_import_file_checksum in imported_files_checksums):
                raise NoProjectFoundError(self.tr('Data from this file are already synchronized with the original project.'))

            fallback_project_path = '/home/suricactus/Documents/GIS_Projects/kzl_benches/kzl_benches.qgs'
            open_project(get_project_in_folder(import_dir))

            self.offline_editing.synchronize()

            original_project_path = ProjectConfiguration(QgsProject.instance()).original_project_path
            if original_project_path:
                # TODO import the DCIM folder
                # copy_images(os.path.join(import_dir, 'DCIM'),os.path.join(os.path.dirname(original_project_path), 'DCIM'))

                if open_project(original_project_path):
                    # save the data_file_checksum to the project and save it
                    imported_files_checksums.append(import_file_checksum(import_dir))
                    ProjectConfiguration(QgsProject.instance()).imported_files_checksums = imported_files_checksums
                    QgsProject.instance().write()
                    iface.messageBar().pushInfo('QFieldSync', self.tr('Opened original project {}'.format(original_project_path)))
                else:
                    iface.messageBar().pushInfo('QFieldSync', self.tr('The data has been synchronized successfully but the original project ({}) could not be opened'.format(original_project_path)))
            else:
                if open_project(fallback_project_path):
                    iface.messageBar().pushInfo('QFieldSync', self.tr('No original project path found, opened the previous project file at "{}"'.format(fallback_project_path)))
                else:
                    iface.messageBar().pushInfo('QFieldSync', self.tr('No original project path found'))

        except NoProjectFoundError as e:
            iface.messageBar().pushWarning('QFieldSync', str(e))
