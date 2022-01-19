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
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QUrl
from qgis.PyQt.QtCore import QAbstractListModel, QModelIndex, QObject, Qt, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from qfieldsync.core.cloud_api import CloudNetworkAccessManager
from qfieldsync.core.cloud_project import CloudProject, ProjectFile, ProjectFileCheckout
from qfieldsync.libqfieldsync.utils.file_utils import copy_multifile


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

        # prepare the files to be uploaded, copy them in a temporary destination
        for project_file in files_to_upload:
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
            [t.name for t in self._files_to_upload.values()],
            FileTransfer.Type.UPLOAD,
        )
        self.throttled_deleter = ThrottledFileTransferrer(
            self.network_manager,
            self.cloud_project,
            [
                t.name
                for t in self._files_to_delete.values()
                if t.checkout & ProjectFileCheckout.Cloud
            ],
            FileTransfer.Type.DELETE,
        )
        self.throttled_downloader = ThrottledFileTransferrer(
            self.network_manager,
            self.cloud_project,
            [t.name for t in self._files_to_download.values()],
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

        for filename in self._files_to_delete:
            project_file = self._files_to_delete[filename]

            if project_file.checkout == ProjectFileCheckout.Local:
                self.delete_files_finished += 1
                Path(project_file.local_path).unlink()

            if project_file.checkout & ProjectFileCheckout.Cloud:
                if project_file.checkout & ProjectFileCheckout.Local:
                    Path(project_file.local_path).unlink()

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
            return

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


class FileTransfer:
    class Type(Enum):
        DOWNLOAD = "download"
        UPLOAD = "upload"
        DELETE = "delete"

    def __init__(self, filename: str, destination: Path, type: Type) -> None:
        self.replies: List[QNetworkReply] = []
        self.redirects: List[QUrl] = []
        self.filename = filename
        # filesystem filename
        self.fs_filename = destination.joinpath(filename)
        self.fs_filename.parent.mkdir(parents=True, exist_ok=True)
        self.error: Optional[Exception] = None
        self.bytes_transferred = 0
        self.bytes_total = 0
        self.is_aborted = False
        self.type = type

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
        return len(self.replies) > 0

    @property
    def is_finished(self) -> bool:
        if self.is_aborted:
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
        filenames: List[str],
        transfer_type: FileTransfer.Type,
        max_parallel_requests: int = 8,
    ) -> None:
        super(QObject, self).__init__()

        self.transfers: Dict[str, FileTransfer] = {}
        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self.filenames = filenames
        self.max_parallel_requests = max_parallel_requests
        self.finished_count = 0
        self.temp_dir = Path(cloud_project.local_dir).joinpath(".qfieldsync")
        self.transfer_type = transfer_type

        for filename in self.filenames:
            self.transfers[filename] = FileTransfer(
                filename,
                self.temp_dir.joinpath(str(self.transfer_type.value)),
                self.transfer_type,
            )

    def transfer(self):
        if self.transfer_type == FileTransfer.Type.DOWNLOAD:
            self._download()
        elif self.transfer_type == FileTransfer.Type.UPLOAD:
            self._upload()
        elif self.transfer_type == FileTransfer.Type.DELETE:
            self._delete()
        else:
            raise NotImplementedError(
                f'Unknown file transfer type "{self.transfer_type}"'
            )

    def abort(self) -> None:
        for transfer in self.transfers.values():
            if not transfer.is_started:
                continue

            transfer.is_aborted = True
            transfer.last_reply.abort()

        self.aborted.emit()

    def _download(self) -> None:
        transfers: List[FileTransfer] = []

        for transfer in self.transfers.values():
            if transfer.is_finished:
                continue

            transfers.append(transfer)

            if len(transfers) == self.max_parallel_requests:
                break

        for transfer in transfers:
            reply = None

            if transfer.is_redirect:
                reply = self.network_manager.get(
                    transfer.last_redirect_url, transfer.fs_filename
                )
            elif transfer.is_started:
                # started a request but still waiting for a response
                continue
            else:
                reply = self.network_manager.get_file_request(
                    self.cloud_project.id + "/" + transfer.filename + "/"
                )

            transfer.replies.append(reply)

            reply.redirected.connect(self._on_redirect_wrapper(transfer))
            reply.downloadProgress.connect(self._on_download_progress_wrapper(transfer))
            reply.finished.connect(self._on_download_finished_wrapper(transfer))

    def _on_redirect_wrapper(self, transfer: FileTransfer) -> Callable:
        def on_redirected(url: QUrl) -> None:
            transfer.redirects.append(url)
            transfer.last_reply.abort()

            self._download()

        return on_redirected

    def _on_download_finished_wrapper(self, transfer: FileTransfer) -> Callable:
        def on_download_finished() -> None:
            # note if the redirect request failed, it will continue
            if transfer.is_redirect:
                return

            self._download()

            try:
                self.network_manager.handle_response(transfer.last_reply, False)
            except Exception as err:
                self.error.emit(
                    transfer.filename,
                    self.tr(
                        f'Downloaded file "{transfer.fs_filename}" had an HTTP error!'
                    ),
                )
                transfer.error = err
                return

            self.finished_count += 1

            if not Path(transfer.fs_filename).exists():
                self.error.emit(
                    transfer.filename,
                    self.tr(f'Downloaded file "{transfer.fs_filename}" not found!'),
                )
                return

            self.file_finished.emit(transfer.filename)

            if self.finished_count == len(self.transfers):
                self.finished.emit()
                return

        return on_download_finished

    def _on_download_progress_wrapper(self, transfer: FileTransfer) -> Callable:
        def on_download_progress(bytes_received: int, bytes_total: int):
            transfer.bytes_transferred = bytes_received
            transfer.bytes_total = bytes_total
            bytes_received_sum = sum(
                [t.bytes_transferred for t in self.transfers.values()]
            )
            bytes_total_sum = sum([t.bytes_total for t in self.transfers.values()])
            self.progress.emit(transfer.filename, bytes_received_sum, bytes_total_sum)

        return on_download_progress

    def _upload(self) -> None:
        transfers: List[FileTransfer] = []

        for transfer in self.transfers.values():
            if transfer.is_finished:
                continue

            transfers.append(transfer)

            if len(transfers) == self.max_parallel_requests:
                break

        for transfer in transfers:
            reply = None

            if transfer.is_redirect:
                raise NotImplementedError("Redirects on upload are not supported")
            elif transfer.is_started:
                # started a request but still waiting for a response
                continue
            else:
                reply = self.network_manager.cloud_upload_files(
                    "files/" + self.cloud_project.id + "/" + transfer.filename,
                    filenames=[str(transfer.fs_filename)],
                )

            transfer.replies.append(reply)

            reply.uploadProgress.connect(self._on_upload_progress_wrapper(transfer))
            reply.finished.connect(self._on_upload_finished_wrapper(transfer))

    def _on_upload_finished_wrapper(self, transfer: FileTransfer) -> Callable:
        def on_upload_finished() -> None:
            self._upload()

            try:
                self.network_manager.handle_response(transfer.last_reply, False)
            except Exception as err:
                self.error.emit(
                    transfer.filename,
                    self.tr(f'Uploading file "{transfer.filename}" failed: {err}'),
                )
                transfer.error = err
                return

            self.finished_count += 1
            self.file_finished.emit(transfer.filename)

            if self.finished_count == len(self.transfers):
                self.finished.emit()
                return

        return on_upload_finished

    def _on_upload_progress_wrapper(self, transfer: FileTransfer) -> Callable:
        def on_upload_progress(bytes_sent: int, bytes_total: int) -> None:
            # there are always at least a few bytes to send, so ignore this situation
            if (
                bytes_sent < transfer.bytes_transferred
                or bytes_total < transfer.bytes_total
            ):
                return

            transfer.bytes_transferred = bytes_sent
            transfer.bytes_total = bytes_total
            bytes_received_sum = sum(
                [t.bytes_transferred for t in self.transfers.values()]
            )
            bytes_total_sum = sum([t.bytes_total for t in self.transfers.values()])
            self.progress.emit(transfer.filename, bytes_received_sum, bytes_total_sum)

        return on_upload_progress

    def _delete(self) -> None:
        transfers = []

        for transfer in self.transfers.values():
            if transfer.is_finished:
                continue

            transfers.append(transfer)

            if len(transfers) == self.max_parallel_requests:
                break

        for transfer in transfers:
            reply = None

            if transfer.is_redirect:
                raise NotImplementedError("Redirects on delete are not supported")
            elif transfer.is_started:
                # started a request but still waiting for a response
                continue
            else:
                reply = self.network_manager.delete_file(
                    self.cloud_project.id + "/" + transfer.filename + "/"
                )

            transfer.replies.append(reply)

            reply.finished.connect(self._on_delete_finished_wrapper(transfer))

    def _on_delete_finished_wrapper(self, transfer: FileTransfer) -> Callable:
        def on_delete_finished() -> None:
            self._delete()

            try:
                self.network_manager.handle_response(transfer.last_reply, False)
            except Exception as err:
                self.error.emit(
                    transfer.filename,
                    self.tr(f'Deleting file "{transfer.filename}" failed: {err}'),
                )
                transfer.error = err
                return

            self.finished_count += 1
            self.file_finished.emit(transfer.filename)

            if self.finished_count == len(self.transfers):
                self.finished.emit()
                return

        return on_delete_finished


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
            if transfer.is_finished:
                return self.tr('File to delete "{}"'.format(transfer.filename))
            else:
                return self.tr('File deleted "{}"'.format(transfer.filename))
        else:
            raise NotImplementedError("Unknown transfer type")

    def _on_updated_transfer(self, filename, *args) -> None:
        row = self.filename_to_index[filename]
        index = self.createIndex(row, 0)

        self.dataChanged.emit(index, index, [Qt.DisplayRole])
