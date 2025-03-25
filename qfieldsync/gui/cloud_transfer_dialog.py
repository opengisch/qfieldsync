"""
/***************************************************************************
 QFieldCloudDialog
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2020-08-01
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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

from libqfieldsync.layer import LayerSource, SyncAction
from libqfieldsync.offline_converter import ExportType
from libqfieldsync.project_checker import ProjectChecker
from libqfieldsync.utils.file_utils import get_unique_empty_dirname
from libqfieldsync.utils.qgis import get_qgis_files_within_dir
from qgis.core import Qgis, QgsApplication, QgsProject, QgsProviderRegistry
from qgis.PyQt.QtCore import QDir, Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices, QShowEvent
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTreeWidgetItem,
    QWidget,
)
from qgis.PyQt.uic import loadUiType
from qgis.utils import iface

from qfieldsync.core.cloud_api import CloudNetworkAccessManager
from qfieldsync.core.cloud_project import CloudProject, ProjectFile, ProjectFileCheckout
from qfieldsync.core.cloud_transferrer import CloudTransferrer, TransferFileLogsModel
from qfieldsync.core.errors import QFieldSyncError
from qfieldsync.core.preferences import Preferences
from qfieldsync.gui.checker_feedback_table import CheckerFeedbackTable
from qfieldsync.utils.qt_utils import make_folder_selector, make_icon, make_pixmap

CloudTransferDialogUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/cloud_transfer_dialog.ui")
)


class ProjectFileAction(Enum):
    NoAction = 0
    DeleteCloud = 1
    DeleteLocal = 2
    UploadAndCreate = 3
    UploadAndReplace = 4
    DownloadAndCreate = 5
    DownloadAndReplace = 6


class CloudTransferDialog(QDialog, CloudTransferDialogUi):
    project_synchronized = pyqtSignal()

    instance = None

    @staticmethod
    def show_transfer_dialog(
        network_manager: CloudNetworkAccessManager,
        cloud_project: Optional[CloudProject] = None,
        accepted_cb: Optional[Callable] = None,
        rejected_cb: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        if CloudTransferDialog.instance:
            CloudTransferDialog.instance.show()
            return CloudTransferDialog.instance

        CloudTransferDialog.instance = CloudTransferDialog(
            network_manager, cloud_project, parent
        )
        CloudTransferDialog.instance.show()

        if accepted_cb:
            CloudTransferDialog.instance.accepted.connect(accepted_cb)
        if rejected_cb:
            CloudTransferDialog.instance.rejected.connect(rejected_cb)

        def on_finished(_result):
            CloudTransferDialog.instance = None

        CloudTransferDialog.instance.finished.connect(on_finished)

        return CloudTransferDialog.instance

    def __init__(
        self,
        network_manager: CloudNetworkAccessManager,
        cloud_project: Optional[CloudProject] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Constructor."""
        super().__init__(parent=parent)
        self.setupUi(self)

        self.preferences = Preferences()
        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self.project_transfer = None
        self.is_project_download = False
        self.is_project_compatible_page_prepared = False

        self.localized_datasets_project = None
        self.localized_datasets_files = []

        self.filesTree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.filesTree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.filesTree.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.filesTree.header().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.filesTree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.filesTree.expandAll()

        self.filesTree.model().setHeaderData(
            1,
            Qt.Orientation.Horizontal,
            make_icon("computer.svg"),
            Qt.ItemDataRole.DecorationRole,
        )
        self.filesTree.model().setHeaderData(
            3,
            Qt.Orientation.Horizontal,
            make_icon("cloud.svg"),
            Qt.ItemDataRole.DecorationRole,
        )
        self.filesTree.model().setHeaderData(
            1, Qt.Orientation.Horizontal, "", Qt.ItemDataRole.DisplayRole
        )
        self.filesTree.model().setHeaderData(
            2, Qt.Orientation.Horizontal, "", Qt.ItemDataRole.DisplayRole
        )
        self.filesTree.model().setHeaderData(
            3, Qt.Orientation.Horizontal, "", Qt.ItemDataRole.DisplayRole
        )
        # The following does not change the icon alignment:
        # self.filesTree.model().setHeaderData(1, Qt.Orientation.Horizontal, Qt.AlignCenter, Qt.TextAlignmentRole)
        # self.filesTree.model().setHeaderData(3, Qt.Orientation.Horizontal, Qt.AlignCenter, Qt.TextAlignmentRole)

        self._update_window_title()

        self.errorLabel.setVisible(False)

        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(
            lambda: self.on_project_ok_clicked()
        )
        self.buttonBox.button(QDialogButtonBox.StandardButton.Abort).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            lambda: self.on_project_apply_clicked()
        )
        self.buttonBox.button(QDialogButtonBox.StandardButton.Help).clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://docs.qfield.org/"))
        )

        self.preferNoneButton.clicked.connect(self._on_prefer_none_button_clicked)
        self.preferLocalButton.clicked.connect(self._on_prefer_local_button_clicked)
        self.preferCloudButton.clicked.connect(self._on_prefer_cloud_button_clicked)

        self.localDirOpenButton.clicked.connect(
            lambda: self.on_local_dir_open_button_clicked()
        )
        self.localDirOpenButton.setIcon(
            QgsApplication.getThemeIcon("/mActionFileOpen.svg")
        )

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setVisible(True)

        super().showEvent(event)

        if (
            not self.cloud_project
            and self.network_manager.projects_cache.currently_open_project
        ):
            self.cloud_project = (
                self.network_manager.projects_cache.currently_open_project
            )

        self._update_window_title()

        if self.cloud_project:
            if self.cloud_project.local_dir:
                self.show_project_compatibility_page()
            else:
                self.show_project_local_dir_selection()
        else:
            if self.network_manager.projects_cache.is_currently_open_project_cloud_local:
                reply = self.network_manager.projects_cache.refresh()
                reply.finished.connect(lambda: self.show_project_compatibility_page())

    def show_project_local_dir_selection(self):
        assert self.cloud_project

        self.is_project_download = True

        self.stackedWidget.setCurrentWidget(self.projectLocalDirPage)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setText(
            self.tr("Next")
        )

        export_dirname = Path(self.preferences.value("cloudDirectory"))
        export_dirname = export_dirname.joinpath(
            self.cloud_project.name
            if self.cloud_project.owner == self.network_manager.get_username()
            else f"{self.cloud_project.owner}__{self.cloud_project.name}"
        )

        self.localDirectoryLineEdit.setText(
            QDir.toNativeSeparators(str(get_unique_empty_dirname(export_dirname)))
        )
        self.localDirectoryButton.clicked.connect(
            make_folder_selector(self.localDirectoryLineEdit)
        )

    def show_project_compatibility_page(self):
        if not self.is_project_compatible_page_prepared:
            feedback = None
            if self.cloud_project and self.cloud_project.is_current_qgis_project:
                checker = ProjectChecker(QgsProject.instance())
                feedback = checker.check(ExportType.Cloud)

            if feedback and feedback.count > 0:
                # check whether the widget has already been added the guard from adding twice due to repeated showEvent signal
                has_errors = len(feedback.error_feedbacks) > 0
                feedback_table = CheckerFeedbackTable(feedback)
                self.feedbackTableWrapperLayout.addWidget(feedback_table)
                self.stackedWidget.setCurrentWidget(self.projectCompatibilityPage)
                self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setVisible(
                    True
                )
                self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(
                    not has_errors
                )
                self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setText(
                    self.tr("Next")
                )
            else:
                self.show_project_files_fetching_page()

            self.is_project_compatible_page_prepared = True

    def show_project_files_fetching_page(self):
        self.stackedWidget.setCurrentWidget(self.getProjectFilesPage)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setVisible(False)
        self.projectFilesLabel.setVisible(True)
        self.projectFilesProgressBar.setVisible(True)

        if (
            not self.cloud_project
            and self.network_manager.projects_cache.currently_open_project
        ):
            self.cloud_project = (
                self.network_manager.projects_cache.currently_open_project
            )

        self._update_window_title()

        if self.cloud_project:
            reply = self.network_manager.projects_cache.get_project_files(
                self.cloud_project.id
            )
            reply.finished.connect(lambda: self.check_localized_datasets())

    def show_end_page(
        self, feedback: str = "", logs_model: Optional[TransferFileLogsModel] = None
    ) -> None:
        summary = ""

        if logs_model:
            failed_count = 0
            success_count = 0
            aborted_count = 0

            for transfer in logs_model.transfers:
                if transfer.is_aborted:
                    aborted_count += 1
                elif transfer.is_failed:
                    failed_count += 1
                elif transfer.is_finished:
                    success_count += 1

            if success_count:
                summary += self.tr("{} file(s) succeeded. ").format(success_count)
            if failed_count:
                summary += self.tr("{} file(s) failed. ").format(failed_count)
            if aborted_count:
                summary += self.tr("{} file(s) aborted. ").format(aborted_count)

        summary = f"{summary}{feedback}"

        self.stackedWidget.setCurrentWidget(self.endPage)

        self.feedbackLabel.setText(summary)

        self.openProjectCheck.setText(
            self.tr("Open project after closing this dialog")
            if self.cloud_project
            is not self.network_manager.projects_cache.currently_open_project
            else self.tr("Re-open project after closing this dialog")
        )

        self.buttonBox.button(QDialogButtonBox.StandardButton.Abort).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

        self.detailedLogEndPageGroupBox.setVisible(False)
        if logs_model:
            self.detailedLogEndPageGroupBox.setVisible(True)
            self.detailedLogEndPageListView.setModel(logs_model)
            self.detailedLogEndPageListView.setModelColumn(0)

    def check_localized_datasets(self):
        localized_datasets_files = self.cloud_project.get_localized_dataset_files()
        if len(localized_datasets_files) > 0:
            localized_datasets_project = (
                self.network_manager.get_or_create_localized_datasets_project(
                    self.cloud_project.owner
                )
            )
            if (
                localized_datasets_project
                and localized_datasets_project.id != self.cloud_project.id
                and (localized_datasets_project.user_role in ("admin", "manager"))
            ):
                self.localized_datasets_project = localized_datasets_project
                self.localized_datasets_files = localized_datasets_files
                reply = self.network_manager.projects_cache.get_project_files(
                    localized_datasets_project.id
                )
                reply.finished.connect(lambda: self.prepare_project_transfer())
                return

        self.prepare_project_transfer()

    def prepare_project_transfer(self):  # noqa: PLR0912, PLR0915
        assert self.cloud_project
        assert self.cloud_project.human_local_dir

        # Failed to update project files
        if self.cloud_project.cloud_files is None:
            self.show_end_page(
                self.tr("Failed to update the project files status from the server.")
            )
            self.openProjectCheck.setChecked(False)
            self.openProjectCheck.setVisible(False)
            return

        # Remove files that are already present remotely, override should be done manually
        if self.localized_datasets_project and self.localized_datasets_files:
            localized_data_paths = (
                QgsApplication.instance().localizedDataPathRegistry().paths()
            )
            localized_datasets_project_files = (
                self.localized_datasets_project.get_files()
            )
            filenames_to_exclude: List[str] = []
            for localized_datasets_project_file in localized_datasets_project_files:
                # If the file is already on the cloud, add to names to exclude
                if bool(
                    localized_datasets_project_file.checkout & ProjectFileCheckout.Cloud
                ):
                    filenames_to_exclude.append(localized_datasets_project_file.name)
            for localized_data_path in localized_data_paths:
                for localized_datasets_file in self.localized_datasets_files[:]:
                    if (
                        localized_datasets_file.local_dir.startswith(
                            localized_data_path
                        )
                        and localized_datasets_file.name in filenames_to_exclude
                    ):
                        self.localized_datasets_files.remove(localized_datasets_file)

        if (
            len(list(self.cloud_project.files_to_sync)) == 0
            and len(self.localized_datasets_files) == 0
        ):
            files_total = len(self.cloud_project.get_files())
            if files_total > 0:
                self.show_end_page(
                    self.tr(
                        "The locally stored cloud project is already synchronized with QFieldCloud, no action is required."
                    )
                )
            else:
                self.show_end_page(
                    self.tr(
                        "This cloud project currently has no file stored either locally or on the server."
                    )
                )
            # if the cloud project being synchronize matches the currently open project, don't offer to open
            if files_total == 0 or (
                self.network_manager.projects_cache.currently_open_project
                and self.cloud_project.id
                == self.network_manager.projects_cache.currently_open_project.id
            ):
                self.openProjectCheck.setChecked(False)
                self.openProjectCheck.setVisible(False)
            return

        self.uploadLocalizedDatasetsCheck.setVisible(
            len(self.localized_datasets_files) != 0
        )
        self.uploadLocalizedDatasetsCheck.setToolTip(
            self.tr("Shared datasets files to upload: {}").format(
                ", ".join([f.name for f in self.localized_datasets_files])
            )
        )

        self.project_transfer = CloudTransferrer(
            self.network_manager,
            self.cloud_project,
            self.localized_datasets_project,
        )
        self.project_transfer.error.connect(self.on_error)
        self.project_transfer.upload_progress.connect(self.on_upload_transfer_progress)
        self.project_transfer.download_progress.connect(
            self.on_download_transfer_progress
        )
        self.project_transfer.finished.connect(self.on_project_transfer_finished)

        self.explanationLabel.setVisible(False)

        self.build_files_tree()
        if (
            self.is_project_download
            and len(list(Path(self.cloud_project.local_dir).glob("**/*"))) == 0
        ):
            # Empty directory, proceed with automated synchronization
            self._file_tree_set_checkboxes(ProjectFileCheckout.Cloud)
            self._start_synchronization()
            return

        if self.cloud_project.user_role == "reader":
            self.preferNoneButton.setVisible(False)
            self.preferLocalButton.setVisible(False)
            self.preferCloudButton.setVisible(False)

        self.stackedWidget.setCurrentWidget(self.filesPage)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setVisible(True)
        self.explanationLabel.setVisible(True)

        self.cloudProjectNameValueLabel.setOpenExternalLinks(True)
        self.cloudProjectNameValueLabel.setText(
            '<a href="{}{}"><b>{}</b></a>'.format(
                self.network_manager.url,
                self.cloud_project.url,
                self.cloud_project.name_with_owner,
            )
        )
        self.projectLocalDirValueLineEdit.setText(
            self.cloud_project.local_dir,
        )
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setText(
            self.tr("Perform Actions")
            if len(self.cloud_project.get_files(ProjectFileCheckout.Cloud)) > 0
            else self.tr("Upload Project")
        )

        if len(self.cloud_project.get_files(ProjectFileCheckout.Cloud)) > 0:
            self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setText(
                self.tr("Perform Actions")
            )
            self.explanationLabel.setText(
                self.tr(
                    "Some of the files on QFieldCloud differ from the files stored in the local project directory. "
                )
            )
        else:
            self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setText(
                self.tr("Upload Files")
            )
            self.explanationLabel.setText(
                self.tr(
                    "All files in the local project directory will be uploaded to QFieldCloud. "
                )
            )

    def build_files_tree(self):
        assert self.project_transfer

        self.filesTree.clear()

        # NOTE algorithmic part
        # ##########
        # The "cloud_files" objects are assumed to be sorted alphabetically by name.
        # First split filenames into parts. For example: '/home/ninja.file' will result into ['home', 'ninja.file'] parts.
        # Then store pairs of the part and the corresponding QTreeWidgetItem in a stack.
        # Pop and push to the stack when the current filename part does not match the previous one.
        # ##########
        stack = []

        offline_layers_paths = self._get_offline_layers()

        for project_file in self.project_transfer.cloud_project.files_to_sync:
            parts = tuple(project_file.path.parts)
            for part_idx, part in enumerate(parts):
                if len(stack) > part_idx and stack[part_idx][0] == part:
                    continue

                stack = stack[0:part_idx]

                item = QTreeWidgetItem()
                item.setText(0, part)
                item.setExpanded(True)

                stack.append((part, item))

                if len(stack) == 1:
                    self.filesTree.addTopLevelItem(item)
                else:
                    stack[-2][1].addChild(stack[-1][1])

                # the length of the stack and the parts is equal for file entries
                if len(stack) == len(parts):
                    item.setData(0, Qt.ItemDataRole.UserRole, project_file)
                    is_offline_layer = (
                        project_file.local_path_exists
                        and str(project_file.local_path) in offline_layers_paths
                    )
                    self.add_file_checkbox_buttons(item, project_file, is_offline_layer)
                else:
                    # TODO @suricactus: make a fancy button that marks all the child items as checked or not
                    pass
        self.filesTree.expandAll()
        # NOTE END algorithmic part

    def _get_offline_layers(self) -> List[str]:
        """Returns a list of paths for project layers which have been configured for offline editing."""
        offline_layers_paths = []
        if self.cloud_project and self.cloud_project.is_current_qgis_project:
            project_layers = list(QgsProject.instance().mapLayers().values())
            for project_layer in project_layers:
                layer_source = LayerSource(project_layer)
                if (
                    layer_source.cloud_action == SyncAction.OFFLINE
                    and layer_source.filename
                ):
                    offline_layers_paths.append(layer_source.filename)
        elif self.cloud_project and len(self.cloud_project.root_project_files) == 1:
            project = QgsProject()

            read_flags = QgsProject.ReadFlags()
            read_flags |= QgsProject.FlagDontResolveLayers
            read_flags |= QgsProject.FlagDontLoadLayouts
            if Qgis.versionInt() >= 32600:  # noqa: PLR2004
                read_flags |= QgsProject.FlagDontLoad3DViews

            project.read(str(self.cloud_project.root_project_files[0]), read_flags)

            project_layers = list(project.mapLayers().values())
            for project_layer in project_layers:
                provider_metadata = QgsProviderRegistry.instance().providerMetadata(
                    project_layer.providerType()
                )
                metadata = provider_metadata.decodeUri(project_layer.source())
                if (
                    metadata.get("path", "") != ""
                    and project_layer.customProperty("QFieldSync/cloud_action")
                    == "offline"
                ):
                    offline_layers_paths.append(metadata.get("path"))

        return offline_layers_paths

    def _update_window_title(self):
        if self.cloud_project:
            self.setWindowTitle(
                self.tr('Synchronizing project "{}"').format(
                    self.cloud_project.name_with_owner
                )
            )
        else:
            self.setWindowTitle(self.tr("Synchronizing project"))

    def on_project_ok_clicked(self):
        assert self.cloud_project

        if not self.openProjectCheck.isChecked() or not self.cloud_project.local_dir:
            return

        project_file_name = get_qgis_files_within_dir(self.cloud_project.local_dir)
        if project_file_name:
            iface.addProject(
                os.path.join(self.cloud_project.local_dir, project_file_name[0])
            )

    def on_project_apply_clicked(self):
        current_page = self.stackedWidget.currentWidget()

        if current_page is self.projectCompatibilityPage:
            self.show_project_files_fetching_page()
        elif current_page is self.filesPage or current_page is self.projectLocalDirPage:
            self._start_synchronization()
        else:
            raise NotImplementedError()

    def on_local_dir_open_button_clicked(self) -> None:
        dirname = self.projectLocalDirValueLineEdit.text()
        if dirname and Path(dirname).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(dirname))

    def _start_synchronization(self):
        assert self.cloud_project

        if self.stackedWidget.currentWidget() is self.projectLocalDirPage:
            if self.localDirectoryLineEdit.text() == "":
                QMessageBox.warning(
                    None,
                    self.tr("Warning"),
                    self.tr("Please provide a local directory."),
                )
                return
            elif get_qgis_files_within_dir(self.localDirectoryLineEdit.text()):
                QMessageBox.warning(
                    None,
                    self.tr("Warning"),
                    self.tr(
                        "The local directory already contains a project file, please pick a different directory."
                    ),
                )
                return
            elif (
                os.makedirs(self.localDirectoryLineEdit.text(), exist_ok=True) is False
            ):
                QMessageBox.warning(
                    None,
                    self.tr("Error"),
                    self.tr(
                        "The local directory provided cannot be created, please pick a different directory."
                    ),
                )
                return

            self.cloud_project.update_data(
                {"local_dir": self.localDirectoryLineEdit.text()}
            )
            self.show_project_compatibility_page()
        else:
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setVisible(True)
            self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            self.buttonBox.button(QDialogButtonBox.StandardButton.Abort).setVisible(
                True
            )
            self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setVisible(
                False
            )
            self.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).setVisible(
                False
            )

            files: Dict[str, List[ProjectFile]] = {
                "to_upload": [],
                "to_download": [],
                "to_delete": [],
                "localized_datasets_to_upload": [],
            }

            for item_idx in range(self.filesTree.topLevelItemCount()):
                item = self.filesTree.topLevelItem(item_idx)

                self.traverse_tree_item(item, files)

            if self.uploadLocalizedDatasetsCheck.isChecked():
                files["localized_datasets_to_upload"] = self.localized_datasets_files

            has_localized_datasets_uploads = len(files["localized_datasets_to_upload"])
            self.localizedDatasetsUploadLabel.setVisible(has_localized_datasets_uploads)
            self.localizedDatasetsUploadProgressBar.setVisible(
                has_localized_datasets_uploads
            )
            self.localizedDatasetsUploadProgressFeedbackLabel.setVisible(
                has_localized_datasets_uploads
            )

            has_uploads = len(files["to_upload"]) > 0
            self.uploadLabel.setVisible(has_uploads)
            self.uploadProgressBar.setVisible(has_uploads)
            self.uploadProgressFeedbackLabel.setVisible(has_uploads)

            has_downloads = len(files["to_download"]) > 0
            self.downloadLabel.setVisible(has_downloads)
            self.downloadProgressBar.setVisible(has_downloads)
            self.downloadProgressFeedbackLabel.setVisible(has_downloads)

            # if the cloud project being synchronize matches the currently open project, don't offer to open if nothing is being downloaded
            if (
                not has_downloads
                and self.network_manager.projects_cache.currently_open_project
                and self.cloud_project.id
                == self.network_manager.projects_cache.currently_open_project.id
            ):
                self.openProjectCheck.setChecked(False)
                self.openProjectCheck.setVisible(False)

            self.show_progress_page(files)

            assert self.project_transfer

            self.project_transfer.sync(
                files["to_upload"],
                files["to_download"],
                files["to_delete"],
                files["localized_datasets_to_upload"],
            )

            assert self.project_transfer.transfers_model

            self.detailedLogListView.setModel(self.project_transfer.transfers_model)
            self.detailedLogListView.setModelColumn(0)

    def traverse_tree_item(
        self, item: QTreeWidgetItem, files: Dict[str, List[ProjectFile]]
    ) -> None:
        project_file = item.data(0, Qt.ItemDataRole.UserRole)

        if project_file:
            assert item.childCount() == 0

            project_file_action = self.project_file_action(item)

            if project_file_action in (
                ProjectFileAction.DeleteLocal,
                ProjectFileAction.DeleteCloud,
            ):
                files["to_delete"].append(project_file)
            elif project_file_action in (
                ProjectFileAction.DownloadAndCreate,
                ProjectFileAction.DownloadAndReplace,
            ):
                files["to_download"].append(project_file)
            elif project_file_action in (
                ProjectFileAction.UploadAndCreate,
                ProjectFileAction.UploadAndReplace,
            ):
                files["to_upload"].append(project_file)
            elif project_file_action == ProjectFileAction.NoAction:
                pass
            else:
                raise QFieldSyncError(
                    f"Unknown project file action {project_file_action}"
                )

            return

        for child_idx in range(item.childCount()):
            self.traverse_tree_item(item.child(child_idx), files)

    def add_file_checkbox_buttons(
        self, item: QTreeWidgetItem, project_file: ProjectFile, is_offline_layer: bool
    ) -> None:
        assert self.cloud_project

        is_local_enabled = self.cloud_project.user_role != "reader"
        is_cloud_enabled = bool(project_file.checkout & ProjectFileCheckout.Cloud)
        is_local_checked = False

        if is_local_enabled and project_file.local_path_exists:
            assert self.cloud_project.local_dir

            local_updated_at = datetime.fromtimestamp(
                os.path.getmtime(
                    os.path.join(self.cloud_project.local_dir, project_file.path)
                ),
                timezone.utc,
            )

            if project_file.uploaded_at:
                is_local_checked = local_updated_at > project_file.uploaded_at
            else:
                is_local_checked = True

        local_checkbox = QCheckBox()
        local_checkbox.setEnabled(is_local_enabled)
        local_checkbox.setChecked(
            is_local_checked and (not is_cloud_enabled or not is_offline_layer)
        )
        local_checkbox.toggled.connect(
            lambda _is_checked: self.on_local_checkbox_toggled(item)
        )
        local_checkbox_widget = QWidget()
        local_checkbox_layout = QHBoxLayout()
        local_checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        local_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        local_checkbox_layout.addWidget(local_checkbox)
        local_checkbox_widget.setLayout(local_checkbox_layout)

        cloud_checkbox = QCheckBox()
        cloud_checkbox.setChecked(is_cloud_enabled and not is_local_checked)
        cloud_checkbox.toggled.connect(
            lambda _is_checked: self.on_cloud_checkbox_toggled(item)
        )
        cloud_checkbox_widget = QWidget()
        cloud_checkbox_layout = QHBoxLayout()
        cloud_checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cloud_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        cloud_checkbox_layout.addWidget(cloud_checkbox)
        cloud_checkbox_widget.setLayout(cloud_checkbox_layout)

        arrow_widget = QWidget()
        arrow_layout = QHBoxLayout()
        arrow_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        local_label, arrow_label, cloud_label = QLabel(), QLabel(), QLabel()
        local_label.setObjectName("local")
        arrow_label.setObjectName("arrow")
        cloud_label.setObjectName("cloud")
        arrow_layout.addWidget(local_label)
        arrow_layout.addWidget(arrow_label)
        arrow_layout.addWidget(cloud_label)
        arrow_widget.setLayout(arrow_layout)

        self.filesTree.setItemWidget(item, 1, local_checkbox_widget)
        self.filesTree.setItemWidget(item, 2, arrow_widget)
        self.filesTree.setItemWidget(item, 3, cloud_checkbox_widget)

        self.update_detail(item)

    def on_error(self, descr: str, _error: Optional[Exception] = None) -> None:
        self.errorLabel.setVisible(True)
        self.errorLabel.setText(self.errorLabel.text() + "\n" + descr)

    def on_upload_transfer_progress(self, fraction: float) -> None:
        self.uploadProgressBar.setValue(int(fraction * 100))

    def on_download_transfer_progress(self, fraction: float) -> None:
        self.downloadProgressBar.setValue(int(fraction * 100))

    def on_project_transfer_finished(self) -> None:
        assert self.project_transfer

        self.show_end_page(
            self.tr("Transfer finished."),
            self.project_transfer.transfers_model,
        )

        self.project_synchronized.emit()

    def on_local_checkbox_toggled(self, item: QTreeWidgetItem) -> None:
        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 3).children()[1]

        if local_checkbox.isChecked():
            cloud_checkbox.setChecked(False)

        self.update_detail(item)

    def on_cloud_checkbox_toggled(self, item: QTreeWidgetItem) -> None:
        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 3).children()[1]

        if cloud_checkbox.isChecked():
            local_checkbox.setChecked(False)

        self.update_detail(item)

    def project_file_action(self, item: QTreeWidgetItem) -> ProjectFileAction:  # noqa: PLR0911
        project_file = item.data(0, Qt.ItemDataRole.UserRole)
        is_local_enabled = project_file.local_path_exists
        is_cloud_enabled = project_file.checkout & ProjectFileCheckout.Cloud
        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 3).children()[1]

        if local_checkbox.isChecked():
            if is_cloud_enabled:
                if is_local_enabled:
                    return ProjectFileAction.UploadAndReplace
                else:
                    return ProjectFileAction.DeleteCloud
            else:
                return ProjectFileAction.UploadAndCreate
        elif cloud_checkbox.isChecked():
            if is_local_enabled:
                if is_cloud_enabled:
                    return ProjectFileAction.DownloadAndReplace
                else:
                    return ProjectFileAction.DeleteLocal
            else:
                return ProjectFileAction.DownloadAndCreate

        return ProjectFileAction.NoAction

    def update_detail(self, item: QTreeWidgetItem) -> None:
        project_file_action = self.project_file_action(item)

        project_file = item.data(0, Qt.ItemDataRole.UserRole)
        has_local = project_file.local_path_exists
        has_cloud = project_file.checkout & ProjectFileCheckout.Cloud

        local_icon = "file.svg" if has_local else "missing.svg"
        cloud_icon = "file.svg" if has_cloud else "missing.svg"

        if project_file_action == ProjectFileAction.NoAction:
            detail = self.tr("No action")
            arrow_icon = "sync_disabled"
        elif project_file_action == ProjectFileAction.UploadAndCreate:
            detail = self.tr("Create file on the cloud")
            cloud_icon = "file_add-green.svg"
            arrow_icon = "arrow_forward-green"
        elif project_file_action == ProjectFileAction.UploadAndReplace:
            detail = self.tr("Upload (will replace file on the cloud)")
            cloud_icon = "file_refresh-orange.svg"
            arrow_icon = "arrow_forward-orange"
        elif project_file_action == ProjectFileAction.DownloadAndCreate:
            detail = self.tr("Download file from the cloud")
            local_icon = "file_add-green.svg"
            arrow_icon = "arrow_back-green.svg"
        elif project_file_action == ProjectFileAction.DownloadAndReplace:
            detail = self.tr("Download (will replace local file)")
            local_icon = "file_refresh-orange.svg"
            arrow_icon = "arrow_back-orange.svg"
        elif project_file_action == ProjectFileAction.DeleteCloud:
            detail = detail = self.tr("Delete file on the cloud")
            cloud_icon = "delete-red.svg"
            arrow_icon = "arrow_forward-red.svg"
        elif project_file_action == ProjectFileAction.DeleteLocal:
            detail = detail = self.tr("Delete local file")
            local_icon = "delete-red.svg"
            arrow_icon = "arrow_back-red.svg"
        else:
            raise QFieldSyncError(f"Unknown project file action {project_file_action}")

        arrow_widget = self.filesTree.itemWidget(item, 2)
        arrow_widget.findChild(QLabel, "local").setPixmap(make_pixmap(local_icon))
        arrow_widget.findChild(QLabel, "arrow").setPixmap(make_pixmap(arrow_icon))
        arrow_widget.findChild(QLabel, "cloud").setPixmap(make_pixmap(cloud_icon))
        item.setText(4, detail)

    def _on_offline_converter_total_progress_updated(
        self, current: int, total: int, message: str
    ) -> None:
        self.totalProgressBar.setMaximum(total)
        self.totalProgressBar.setValue(current)
        self.statusLabel.setText(message)

    def _on_offline_converter_task_progress_updated(
        self, progress: int, total: int
    ) -> None:
        self.layerProgressBar.setMaximum(total)
        self.layerProgressBar.setValue(progress)

    def on_offline_editing_progress_stopped(self) -> None:
        self.offline_editing_done = True

    def on_offline_editing_layer_progress_updated(
        self, progress: int, total: int
    ) -> None:
        self.totalProgressBar.setMaximum(total)
        self.totalProgressBar.setValue(progress)

    def on_offline_editing_progress_mode_set(self, _, total: int) -> None:
        self.layerProgressBar.setMaximum(total)
        self.layerProgressBar.setValue(0)

    def on_offline_editing_progress_updated(self, progress: int) -> None:
        self.layerProgressBar.setValue(progress)

    def _on_prefer_none_button_clicked(self) -> None:
        # NOTE: LocalAndCloud is used to make neither checkbox checked. Don't use Deleted, as it might be added as a checkbox later.
        self._file_tree_set_checkboxes(ProjectFileCheckout.LocalAndCloud)

    def _on_prefer_local_button_clicked(self) -> None:
        self._file_tree_set_checkboxes(ProjectFileCheckout.Local)

    def _on_prefer_cloud_button_clicked(self) -> None:
        self._file_tree_set_checkboxes(ProjectFileCheckout.Cloud)

    def _file_tree_set_checkboxes(self, checkout: ProjectFileCheckout) -> None:
        for item_idx in range(self.filesTree.topLevelItemCount()):
            self._file_tree_set_checkboxes_recursive(
                self.filesTree.topLevelItem(item_idx), checkout
            )

    def _file_tree_set_checkboxes_recursive(
        self, item: QTreeWidgetItem, checkout: ProjectFileCheckout
    ) -> None:
        project_file = item.data(0, Qt.ItemDataRole.UserRole)

        if project_file:
            assert item.childCount() == 0
        else:
            for child_idx in range(item.childCount()):
                self._file_tree_set_checkboxes_recursive(
                    item.child(child_idx), checkout
                )
            return

        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 3).children()[1]

        if checkout == ProjectFileCheckout.Local and local_checkbox.isEnabled():
            local_checkbox.setChecked(True)
        elif checkout == ProjectFileCheckout.Cloud and cloud_checkbox.isEnabled():
            cloud_checkbox.setChecked(True)
        elif checkout == ProjectFileCheckout.LocalAndCloud:
            local_checkbox.setChecked(False)
            cloud_checkbox.setChecked(False)
        elif checkout == ProjectFileCheckout.Deleted:
            # Reserved for a better future
            pass

    def show_progress_page(self, files: Dict[str, List[ProjectFile]]) -> None:  # noqa: PLR0912, PLR0915
        total_delete_count = 0
        local_delete_count = 0
        cloud_delete_count = 0
        download_count = len(files["to_download"])
        upload_count = len(files["to_upload"])
        localized_datasets_upload_count = len(files["localized_datasets_to_upload"])

        for f in files["to_delete"]:
            total_delete_count += 1

            if f.checkout & ProjectFileCheckout.Local:
                local_delete_count += 1
            elif f.checkout & ProjectFileCheckout.Local:
                cloud_delete_count += 1

        localized_datasets_upload_message = ""
        if localized_datasets_upload_count:
            localized_datasets_upload_message += self.tr(
                "%n shared dataset(s) to copy to QFieldCloud.",
                "",
                localized_datasets_upload_count,
            )

            self.localizedDatasetsUploadProgressBar.setValue(0)
            self.localizedDatasetsUploadProgressBar.setEnabled(True)
        else:
            self.localizedDatasetsUploadProgressBar.setValue(100)
            self.localizedDatasetsUploadProgressBar.setEnabled(False)
            localized_datasets_upload_message = self.tr("Nothing to do on QFieldCloud.")

        self.localizedDatasetsUploadProgressFeedbackLabel.setText(
            localized_datasets_upload_message
        )

        upload_message = ""
        if upload_count or cloud_delete_count:
            if upload_count > 1:
                upload_message += self.tr(
                    "{} files to copy to QFieldCloud.".format(upload_count)
                )
            elif upload_count == 1:
                upload_message += self.tr("1 file to copy to QFieldCloud.")
            if cloud_delete_count > 1:
                upload_message += self.tr(
                    "{} files to delete on QFieldCloud.".format(cloud_delete_count)
                )
            elif cloud_delete_count == 1:
                upload_message += self.tr("1 file to delete on QFieldCloud.")

            self.uploadProgressBar.setValue(0)
            self.uploadProgressBar.setEnabled(True)
        else:
            self.uploadProgressBar.setValue(100)
            self.uploadProgressBar.setEnabled(False)
            upload_message = self.tr("Nothing to do on QFieldCloud.")
        self.uploadProgressFeedbackLabel.setText(upload_message)

        download_message = ""
        if download_count or local_delete_count:
            if download_count > 1:
                download_message += self.tr(
                    "{} files to copy locally from QFieldCloud.".format(download_count)
                )
            elif download_count == 1:
                download_message += self.tr("1 file to copy locally from QFieldCloud.")
            if local_delete_count > 1:
                download_message += self.tr(
                    "{} files to delete locally.".format(local_delete_count)
                )
            elif local_delete_count == 1:
                download_message += self.tr("1 file to delete locally.")

            self.downloadProgressBar.setValue(0)
            self.downloadProgressBar.setEnabled(True)
        else:
            self.downloadProgressBar.setValue(100)
            self.downloadProgressBar.setEnabled(False)
            download_message = self.tr("Nothing to do locally.")
        self.downloadProgressFeedbackLabel.setText(download_message)

        self.stackedWidget.setCurrentWidget(self.progressPage)
