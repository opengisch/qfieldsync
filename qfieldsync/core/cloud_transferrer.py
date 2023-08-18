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


import shutil
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from libqfieldsync.utils.file_utils import copy_multifile
from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtNetwork import QNetworkReply

from qfieldsync.core.cloud_api import CloudNetworkAccessManager
from qfieldsync.core.cloud_project import CloudProject, ProjectFile, ProjectFileCheckout


class CloudTransferrer(QObject):
    # TODO show progress of individual files
    progress = pyqtSignal(float)
    error = pyqtSignal(str, Exception)
    abort = pyqtSignal()
    finished = pyqtSignal()
    upload_progress = pyqtSignal(float)
    download_progress = pyqtSignal(float)
    upload_finished = pyqtSignal()
    download_finished = pyqtSignal()
    delete_finished = pyqtSignal()

    def __init__(
        self, network_manager: CloudNetworkAccessManager, cloud_project: CloudProject
    ) -> None:
        super(CloudTransferrer, self).__init__(parent=None)
        assert cloud_project.local_dir

        self.network_manager = network_manager
        self.cloud_project = cloud_project
        # NOTE these `_files_to_(upload|download|delete)` uses POSIX path as keys, so beware on M$
        self._files_to_upload = {}
        self._files_to_download: Dict[str, ProjectFile] = {}
        self._files_to_delete = {}
        self.total_upload_bytes = 0
        self.total_download_bytes = 0
        self.delete_files_finished = 0
        self.is_aborted = False
        self.is_started = False
        self.is_finished = False
        self.is_upload_active = False
        self.is_download_active = False
        self.is_delete_active = False
        self.is_project_list_update_active = False
        self.replies = []
        self.temp_dir = Path(cloud_project.local_dir).joinpath(".qfieldsync")
        self.error_message = None
        self.throttled_uploader = None
        self.throttled_downloader = None
        self.throttled_deleter = None
        self.transfers_model = None

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

        self.temp_dir.mkdir()
        self.temp_dir.joinpath("backup").mkdir()
        self.temp_dir.joinpath(FileTransfer.Type.UPLOAD.value).mkdir()
        self.temp_dir.joinpath(FileTransfer.Type.DOWNLOAD.value).mkdir()

        self.upload_finished.connect(self._on_upload_finished)
        self.delete_finished.connect(self._on_delete_finished)
        self.download_finished.connect(self._on_download_finished)

        self.network_manager.logout_success.connect(self._on_logout_success)

    def sync(
        self,
        files_to_upload: List[ProjectFile],
        files_to_download: List[ProjectFile],
        files_to_delete: List[ProjectFile],
    ) -> None:
        assert not self.is_started

        self.is_started = True

        # .qgs/.qgz files should be uploaded the last, since they trigger a new job
        files_to_upload_sorted = [
            f
            for f in sorted(
                files_to_upload,
                key=lambda f: f.path.suffix in (".qgs", ".qgz"),
            )
        ]
        # prepare the files to be uploaded, copy them in a temporary destination
        for project_file in files_to_upload_sorted:
            assert project_file.local_path

            project_file.flush()

            temp_filename = self.temp_dir.joinpath(
                FileTransfer.Type.UPLOAD.value, project_file.name
            )
            temp_filename.parent.mkdir(parents=True, exist_ok=True)
            copy_multifile(project_file.local_path, temp_filename)

            self.total_upload_bytes += project_file.local_size or 0
            self._files_to_upload[str(project_file.path.as_posix())] = project_file

        # prepare the files to be delete, both locally and remotely
        for project_file in files_to_delete:
            self._files_to_delete[str(project_file.path.as_posix())] = project_file

        # prepare the files to be downloaded, download them in a temporary destination
        for project_file in files_to_download:
            temp_filename = self.temp_dir.joinpath(
                FileTransfer.Type.DOWNLOAD.value, project_file.name
            )
            temp_filename.parent.mkdir(parents=True, exist_ok=True)

            self.total_download_bytes += project_file.size or 0
            self._files_to_download[str(project_file.path.as_posix())] = project_file

        self.throttled_uploader = ThrottledFileTransferrer(
            self.network_manager,
            self.cloud_project,
            # note the .qgs/.qgz files are sorted in the end
            list(self._files_to_upload.values()),
            FileTransfer.Type.UPLOAD,
        )
        self.throttled_deleter = ThrottledFileTransferrer(
            self.network_manager,
            self.cloud_project,
            list(self._files_to_delete.values()),
            FileTransfer.Type.DELETE,
        )
        self.throttled_downloader = ThrottledFileTransferrer(
            self.network_manager,
            self.cloud_project,
            list(self._files_to_download.values()),
            FileTransfer.Type.DOWNLOAD,
        )
        self.transfers_model = TransferFileLogsModel(
            [
                self.throttled_uploader,
                self.throttled_deleter,
                self.throttled_downloader,
            ]
        )

        self._make_backup()
        self._upload()

    def _upload(self) -> None:
        assert not self.is_upload_active, "Upload in progress"
        assert not self.is_delete_active, "Delete in progress"
        assert not self.is_download_active, "Download in progress"
        assert self.cloud_project.local_dir

        self.is_upload_active = True

        # nothing to upload
        if len(self._files_to_upload) == 0:
            self.upload_progress.emit(1)
            self.upload_finished.emit()
            # NOTE check _on_upload_finished
            return

        self.throttled_uploader.error.connect(self._on_throttled_upload_error)
        self.throttled_uploader.progress.connect(self._on_throttled_upload_progress)
        self.throttled_uploader.finished.connect(self._on_throttled_upload_finished)
        self.throttled_uploader.transfer()

    def _on_throttled_upload_progress(
        self, filename: str, bytes_transferred: int, _bytes_total: int
    ) -> None:
        fraction = min(bytes_transferred / max(self.total_upload_bytes, 1), 1)
        self.upload_progress.emit(fraction)

    def _on_throttled_upload_error(self, filename: str, error: str) -> None:
        self.throttled_uploader.abort()

    def _on_throttled_upload_finished(self) -> None:
        self.upload_progress.emit(1)
        self.upload_finished.emit()
        return

    def _delete(self) -> None:
        assert not self.is_upload_active, "Upload in progress"
        assert not self.is_delete_active, "Delete in progress"
        assert not self.is_download_active, "Download in progress"

        self.is_delete_active = True

        # nothing to delete
        if len(self._files_to_delete) == 0:
            self.delete_finished.emit()
            # NOTE check _on_delete_finished
            return

        self.throttled_deleter.error.connect(self._on_throttled_delete_error)
        self.throttled_deleter.finished.connect(self._on_throttled_delete_finished)
        self.throttled_deleter.transfer()

        # in case all the files to delete were local only
        if self.delete_files_finished == len(self._files_to_delete):
            self.delete_finished.emit()

    def _on_throttled_delete_error(self, filename: str, error: str) -> None:
        self.throttled_deleter.abort()

    def _on_throttled_delete_finished(self) -> None:
        if self.delete_files_finished == len(self._files_to_delete):
            self.delete_finished.emit()

    def _download(self) -> None:
        assert not self.is_upload_active, "Upload in progress"
        assert not self.is_delete_active, "Delete in progress"
        assert not self.is_download_active, "Download in progress"

        self.is_download_active = True

        # nothing to download
        if len(self._files_to_download) == 0:
            self.download_progress.emit(1)
            self.download_finished.emit()
            return

        self.throttled_downloader.error.connect(self._on_throttled_download_error)
        self.throttled_downloader.progress.connect(self._on_throttled_download_progress)
        self.throttled_downloader.finished.connect(self._on_throttled_download_finished)
        self.throttled_downloader.transfer()

    def _on_throttled_download_progress(
        self, filename: str, bytes_transferred: int, _bytes_total: int
    ) -> None:
        fraction = min(bytes_transferred / max(self.total_download_bytes, 1), 1)
        self.download_progress.emit(fraction)

    def _on_throttled_download_error(self, filename: str, error: str) -> None:
        self.throttled_downloader.abort()

    def _on_throttled_download_finished(self) -> None:
        self.download_progress.emit(1)
        self.download_finished.emit()
        return

    def _on_upload_finished(self) -> None:
        self.is_upload_active = False
        self._update_project_files_list()
        self._delete()

    def _on_delete_finished(self) -> None:
        self.is_delete_active = False
        self._download()

    def _on_download_finished(self) -> None:
        if not self.import_qfield_project():
            QgsMessageLog.logMessage(
                self.tr("Failed to copy project files to the project directory!"),
                "QFieldSync",
                Qgis.Critical,
            )

        self.is_download_active = False
        self.is_finished = True

        if not self.is_project_list_update_active:
            self.finished.emit()

    def _update_project_files_list(self) -> None:
        self.is_project_list_update_active = True

        reply = self.network_manager.projects_cache.get_project_files(
            self.cloud_project.id
        )
        reply.finished.connect(lambda: self._on_update_project_files_list_finished())

    def _on_update_project_files_list_finished(self) -> None:
        self.is_project_list_update_active = False

        if not self.is_download_active:
            if self.error_message:
                return

            self.finished.emit()

    def abort_requests(self) -> None:
        if self.is_aborted:
            return

        self.is_aborted = True

        for transferrer in [
            self.throttled_uploader,
            self.throttled_downloader,
            self.throttled_deleter,
        ]:
            # it might be deleted
            if transferrer:
                transferrer.abort()

        self.abort.emit()

    def _make_backup(self) -> None:
        for project_file in [
            *list(map(lambda f: f, self._files_to_upload.values())),
            *list(map(lambda f: f, self._files_to_download.values())),
        ]:
            if project_file.local_path and project_file.local_path.exists():
                dest = self.temp_dir.joinpath("backup", project_file.path)
                dest.parent.mkdir(parents=True, exist_ok=True)

                copy_multifile(project_file.local_path, dest)

    def _temp_dir2main_dir(self, subdir: str) -> None:
        subdir_path = self.temp_dir.joinpath(subdir)

        if not subdir_path.exists():
            raise Exception(
                self.tr('Directory "{}" does not exist').format(subdir_path)
            )

        for filename in subdir_path.glob("**/*"):
            if filename.is_dir():
                filename.mkdir(parents=True, exist_ok=True)
                continue

            source_filename = str(filename.relative_to(subdir_path).as_posix())
            dest_filename = str(self._files_to_download[source_filename].local_path)

            dest_path = Path(dest_filename)
            if not dest_path.parent.exists():
                dest_path.parent.mkdir(parents=True)

            if source_filename.endswith((".gpkg-shm", ".gpkg-wal")):
                for suffix in ("-shm", "-wal"):
                    source_path = Path(str(self.local_path) + suffix)
                    dest_path = Path(str(dest_filename) + suffix)

                    if source_path.exists():
                        shutil.copyfile(source_path, dest_path)
                    else:
                        dest_path.unlink()

            shutil.copyfile(filename, dest_filename)

    def import_qfield_project(self) -> bool:
        try:
            self._temp_dir2main_dir(
                str(self.temp_dir.joinpath(FileTransfer.Type.DOWNLOAD.value))
            )
            return True
        except Exception as err:
            self.error_message = self.tr(
                "Failed to copy temporary downloaded files to your project directory, restore the project state before the synchronization: {}. Trying to rollback changes..."
            ).format(str(err))
            self.error.emit(
                self.error_message,
                err,
            )
            try:
                self._temp_dir2main_dir(str(self.temp_dir.joinpath("backup")))
            except Exception as errInner:
                self.error_message = self.tr(
                    'Failed to restore the backup. You project might be corrupted! Please check ".qfieldsync/backup" directory and try to copy the files back manually.'
                )
                self.error.emit(
                    self.error_message,
                    errInner,
                )

        return False

    def _on_logout_success(self) -> None:
        self.abort_requests()


class FileTransfer(QObject):

    progress = pyqtSignal(int, int)
    finished = pyqtSignal()

    class Type(Enum):
        DOWNLOAD = "download"
        UPLOAD = "upload"
        DELETE = "delete"

    def __init__(
        self,
        network_manager: CloudNetworkAccessManager,
        cloud_project: CloudProject,
        type: Type,
        file: ProjectFile,
        destination: Path,
        version: str = None,
    ) -> None:
        super(QObject, self).__init__()

        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self.replies: List[QNetworkReply] = []
        self.redirects: List[QUrl] = []
        self.file = file
        self.filename = file.name
        # filesystem filename
        self.fs_filename = destination
        self.fs_filename.parent.mkdir(parents=True, exist_ok=True)
        self.error: Optional[Exception] = None
        self.bytes_transferred = 0
        self.bytes_total = 0
        self.is_aborted = False
        self.is_local_delete = False
        self.is_local_delete_finished = False
        self.type = type
        self.version = version

        if self.file.checkout == ProjectFileCheckout.Local or (
            self.file.checkout & ProjectFileCheckout.Cloud
            and self.file.checkout & ProjectFileCheckout.Local
        ):
            self.is_local_delete = True

    def abort(self):
        if not self.is_started:
            return

        if self.is_finished:
            return

        self.is_aborted = True
        self.last_reply.abort()

    def transfer(self) -> None:
        if self.type == FileTransfer.Type.DOWNLOAD:
            if self.is_redirect:
                reply = self.network_manager.get(
                    self.last_redirect_url, str(self.fs_filename)
                )
            else:
                params = {"version": self.version} if self.version else {}
                reply = self.network_manager.cloud_get(
                    f"files/{self.cloud_project.id}/{self.filename}/",
                    local_filename=str(self.fs_filename),
                    params=params,
                )
        elif self.type == FileTransfer.Type.UPLOAD:
            reply = self.network_manager.cloud_upload_files(
                "files/" + self.cloud_project.id + "/" + self.filename,
                filenames=[str(self.fs_filename)],
            )
        elif self.type == FileTransfer.Type.DELETE:
            if self.is_local_delete:
                try:
                    assert self.file.local_path
                    Path(self.file.local_path).unlink()
                except Exception as err:
                    self.error = err
                finally:
                    self.is_local_delete_finished = True

                self.finished.emit()
                return

            reply = self.network_manager.delete_file(
                self.cloud_project.id + "/" + self.filename + "/"
            )
        else:
            raise NotImplementedError()

        self.replies.append(reply)

        reply.redirected.connect(lambda *args: self._on_redirected(*args))
        reply.downloadProgress.connect(lambda *args: self._on_progress(*args))
        reply.uploadProgress.connect(lambda *args: self._on_progress(*args))
        reply.finished.connect(lambda *args: self._on_finished(*args))

    def _on_progress(self, bytes_transferred: int, bytes_total: int) -> None:
        # there are always at least a few bytes to send, so ignore this situation
        if bytes_transferred < self.bytes_transferred or bytes_total < self.bytes_total:
            return

        self.bytes_transferred = bytes_transferred
        self.bytes_total = bytes_total

        self.progress.emit(bytes_transferred, bytes_total)

    def _on_redirected(self, url: QUrl) -> None:
        self.redirects.append(url)
        self.last_reply.abort()

    def _on_finished(self) -> None:
        if self.is_redirect:
            if self.type == FileTransfer.Type.DOWNLOAD:
                self.transfer()
                return
            else:
                raise NotImplementedError("Redirects on upload are not supported")

        try:
            self.network_manager.handle_response(self.last_reply, False)

            if (
                self.type == FileTransfer.Type.DOWNLOAD
                and not self.fs_filename.is_file()
            ):
                self.error = Exception(
                    f'Downloaded file "{self.fs_filename}" not found!'
                )
        except Exception as err:
            self.error = err
            if self.fs_filename.is_file():
                self.fs_filename.unlink()

        self.finished.emit()

    @property
    def last_reply(self) -> QNetworkReply:
        if not self.replies:
            raise ValueError("There are no replies yet!")

        return self.replies[-1]

    @property
    def last_redirect_url(self) -> QUrl:
        if not self.replies:
            raise ValueError("There are no redirects!")

        return self.redirects[-1]

    @property
    def is_started(self) -> bool:
        return self.is_local_delete_finished or len(self.replies) > 0

    @property
    def is_finished(self) -> bool:
        if self.is_aborted:
            return True

        if self.is_local_delete_finished:
            return True

        if not self.replies:
            return False

        if self.is_redirect:
            return False

        return self.replies[-1].isFinished()

    @property
    def is_redirect(self) -> bool:
        if not self.replies:
            return False

        return len(self.replies) == len(self.redirects)

    @property
    def is_failed(self) -> bool:
        if self.is_local_delete and self.error:
            return True

        if not self.replies:
            return False

        return self.last_reply.isFinished() and (
            self.error is not None or self.last_reply.error() != QNetworkReply.NoError
        )


class ThrottledFileTransferrer(QObject):
    error = pyqtSignal(str, str)
    finished = pyqtSignal()
    aborted = pyqtSignal()
    file_finished = pyqtSignal(str)
    progress = pyqtSignal(str, int, int)

    def __init__(
        self,
        network_manager,
        cloud_project,
        files: List[ProjectFile],
        transfer_type: FileTransfer.Type,
        max_parallel_requests: int = 8,
    ) -> None:
        super(QObject, self).__init__()

        self.transfers: Dict[str, FileTransfer] = {}
        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self.files = files
        self.filenames = [f.name for f in files]
        self.max_parallel_requests = max_parallel_requests
        self.finished_count = 0
        self.temp_dir = Path(cloud_project.local_dir).joinpath(".qfieldsync")
        self.transfer_type = transfer_type

        for file in self.files:
            transfer = FileTransfer(
                self.network_manager,
                self.cloud_project,
                self.transfer_type,
                file,
                self.temp_dir.joinpath(str(self.transfer_type.value), file.name),
            )
            transfer.progress.connect(
                lambda *args: self._on_transfer_progress(transfer, *args)
            )
            transfer.finished.connect(
                lambda *args: self._on_transfer_finished(transfer, *args)
            )

            assert file.name not in self.transfers

            self.transfers[file.name] = transfer

    def transfer(self):
        transfers_count = 0

        for transfer in self.transfers.values():
            if transfer.is_finished:
                continue

            transfers_count += 1

            # skip a started request but still waiting for a response
            if not transfer.is_started:
                transfer.transfer()

            if transfers_count == self.max_parallel_requests:
                break

    def abort(self) -> None:
        for transfer in self.transfers.values():
            transfer.abort()

        self.aborted.emit()

    def _on_transfer_progress(self, transfer, bytes_received: int, bytes_total: int):
        bytes_received_sum = sum([t.bytes_transferred for t in self.transfers.values()])
        bytes_total_sum = sum([t.bytes_total for t in self.transfers.values()])
        self.progress.emit(transfer.filename, bytes_received_sum, bytes_total_sum)

    def _on_transfer_finished(self, transfer: FileTransfer) -> None:
        self.transfer()

        if transfer.error:
            if transfer.type == FileTransfer.Type.DOWNLOAD:
                msg = self.tr('Downloading file "{}" failed!').format(
                    transfer.fs_filename
                )
            elif transfer.type == FileTransfer.Type.UPLOAD:
                msg = self.tr('Uploading file "{}" failed!').format(
                    transfer.fs_filename
                )
            elif transfer.type == FileTransfer.Type.DELETE:
                msg = self.tr('Deleting file "{}" failed!').format(transfer.fs_filename)
            else:
                raise NotImplementedError()

            self.error.emit(
                transfer.filename,
                msg,
            )

        self.finished_count += 1
        self.file_finished.emit(transfer.filename)

        if self.finished_count == len(self.transfers):
            self.finished.emit()
            return


class TransferFileLogsModel(QAbstractListModel):
    def __init__(
        self, transferrers: List[ThrottledFileTransferrer], parent: QObject = None
    ):
        super(TransferFileLogsModel, self).__init__()
        self.transfers: List[FileTransfer] = []
        self.filename_to_index: Dict[str, int] = {}

        for transferrer in transferrers:
            for filename, transfer in transferrer.transfers.items():
                self.filename_to_index[filename] = len(self.transfers)
                self.transfers.append(transfer)

            transferrer.file_finished.connect(self._on_updated_transfer)
            transferrer.error.connect(self._on_updated_transfer)
            transferrer.progress.connect(self._on_updated_transfer)

    def rowCount(self, parent: QModelIndex) -> int:
        return len(self.transfers)

    def data(self, index: QModelIndex, role: int) -> Any:
        if index.row() < 0 or index.row() >= self.rowCount(QModelIndex()):
            return None

        if role == Qt.DisplayRole:
            return self._data_string(self.transfers[index.row()])

        return None

    def index(self, row: int, col: int, _index: QModelIndex) -> QModelIndex:
        return self.createIndex(row, col)

    def _data_string(self, transfer: FileTransfer) -> str:
        error_msg = ""
        if transfer.is_failed:
            error_msg = (
                str(transfer.error)
                if transfer.error
                else "[{}] {}".format(
                    transfer.last_reply.error(), transfer.last_reply.errorString()
                )
            )

        if transfer.type == FileTransfer.Type.DOWNLOAD:
            if transfer.is_aborted:
                return self.tr('Aborted "{}" download'.format(transfer.filename))
            elif transfer.is_failed:
                return self.tr(
                    'Failed to download "{}": {}'.format(transfer.filename, error_msg)
                )
            elif transfer.is_finished:
                return self.tr('Downloaded "{}"'.format(transfer.filename))
            elif transfer.is_started:
                percentage = (
                    transfer.bytes_transferred / transfer.bytes_total
                    if transfer.bytes_total > 0
                    else 0
                )
                return self.tr(
                    'Downloading "{}" {}%'.format(
                        transfer.filename, round(percentage * 100)
                    )
                )
            else:
                return self.tr('File to download "{}"'.format(transfer.filename))
        elif transfer.type == FileTransfer.Type.UPLOAD:
            if transfer.is_aborted:
                return self.tr('Aborted "{}" upload'.format(transfer.filename))
            elif transfer.is_failed:
                return self.tr(
                    'Failed to upload "{}": {}'.format(transfer.filename, error_msg)
                )
            elif transfer.is_finished:
                return self.tr('Uploaded "{}"'.format(transfer.filename))
            elif transfer.is_started:
                percentage = (
                    transfer.bytes_transferred / transfer.bytes_total
                    if transfer.bytes_total > 0
                    else 0
                )
                return self.tr(
                    'Uploading "{}" {}%'.format(
                        transfer.filename, round(percentage * 100)
                    )
                )
            else:
                return self.tr('File to upload "{}"'.format(transfer.filename))
        elif transfer.type == FileTransfer.Type.DELETE:
            if transfer.file.checkout & ProjectFileCheckout.Cloud:
                if transfer.is_aborted:
                    return self.tr(
                        'Aborted "{}" deleting on the cloud'.format(transfer.filename)
                    )
                elif transfer.is_failed:
                    return self.tr(
                        'Failed delete "{}" on the cloud'.format(transfer.filename)
                    )
                elif transfer.is_finished:
                    return self.tr(
                        'File "{}" deleted on the cloud'.format(transfer.filename)
                    )
                elif transfer.is_started:
                    return self.tr(
                        'Deleting "{}" on the cloud'.format(transfer.filename)
                    )
                else:
                    return self.tr(
                        'File "{}" will be deleted on the cloud'.format(
                            transfer.filename
                        )
                    )
            else:
                if transfer.is_aborted:
                    return self.tr(
                        'Aborted "{}" deleting locally'.format(transfer.filename)
                    )
                elif transfer.is_failed:
                    return self.tr(
                        'Failed delete "{}" locally'.format(transfer.filename)
                    )
                elif transfer.is_finished:
                    return self.tr(
                        'File "{}" locally deleted'.format(transfer.filename)
                    )
                elif transfer.is_started:
                    return self.tr('Locally deleting "{}"'.format(transfer.filename))
                else:
                    return self.tr(
                        'File "{}" to will be locally deleted'.format(transfer.filename)
                    )
        else:
            raise NotImplementedError("Unknown transfer type")

    def _on_updated_transfer(self, filename, *args) -> None:
        row = self.filename_to_index[filename]
        index = self.createIndex(row, 0)

        self.dataChanged.emit(index, index, [Qt.DisplayRole])
