# -*- coding: utf-8 -*-
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
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List

from libqfieldsync.offline_converter import ExportType
from libqfieldsync.project_checker import ProjectChecker
from libqfieldsync.utils.file_utils import get_unique_empty_dirname
from libqfieldsync.utils.qgis import get_qgis_files_within_dir
from qgis.core import QgsProject
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
from qfieldsync.core.preferences import Preferences
from qfieldsync.gui.checker_feedback_table import CheckerFeedbackTable

from ..utils.qt_utils import make_folder_selector, make_icon, make_pixmap

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
        cloud_project: CloudProject = None,
        accepted_cb: Callable = None,
        rejected_cb: Callable = None,
        parent: QWidget = None,
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

        def on_finished(result):
            CloudTransferDialog.instance = None

        CloudTransferDialog.instance.finished.connect(on_finished)

        return CloudTransferDialog.instance

    def __init__(
        self,
        network_manager: CloudNetworkAccessManager,
        cloud_project: CloudProject = None,
        parent: QWidget = None,
    ) -> None:
        """Constructor."""
        super(CloudTransferDialog, self).__init__(parent=parent)
        self.setupUi(self)

        self.preferences = Preferences()
        self.network_manager = network_manager
        self.cloud_project = cloud_project
        self.project_transfer = None
        self.is_project_download = False

        self.filesTree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.filesTree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.filesTree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.filesTree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.filesTree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.filesTree.expandAll()

        self.filesTree.model().setHeaderData(
            1, Qt.Horizontal, make_icon("computer.svg"), Qt.DecorationRole
        )
        self.filesTree.model().setHeaderData(
            3, Qt.Horizontal, make_icon("cloud.svg"), Qt.DecorationRole
        )
        self.filesTree.model().setHeaderData(1, Qt.Horizontal, "", Qt.DisplayRole)
        self.filesTree.model().setHeaderData(2, Qt.Horizontal, "", Qt.DisplayRole)
        self.filesTree.model().setHeaderData(3, Qt.Horizontal, "", Qt.DisplayRole)
        # The following does not change the icon alignment:
        # self.filesTree.model().setHeaderData(1, Qt.Horizontal, Qt.AlignCenter, Qt.TextAlignmentRole)
        # self.filesTree.model().setHeaderData(3, Qt.Horizontal, Qt.AlignCenter, Qt.TextAlignmentRole)

        self._update_window_title()

        self.errorLabel.setVisible(False)

        self.buttonBox.button(QDialogButtonBox.Ok).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Ok).clicked.connect(
            lambda: self.on_project_ok_clicked()
        )
        self.buttonBox.button(QDialogButtonBox.Abort).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Cancel).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Apply).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(
            lambda: self.on_project_apply_clicked()
        )
        self.buttonBox.button(QDialogButtonBox.Help).clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://docs.qfield.org/"))
        )

        self.preferNoneButton.clicked.connect(self._on_prefer_none_button_clicked)
        self.preferLocalButton.clicked.connect(self._on_prefer_local_button_clicked)
        self.preferCloudButton.clicked.connect(self._on_prefer_cloud_button_clicked)

    def showEvent(self, event: QShowEvent) -> None:
        self.buttonBox.button(QDialogButtonBox.Cancel).setVisible(True)

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
            if (
                self.network_manager.projects_cache.is_currently_open_project_cloud_local
            ):
                reply = self.network_manager.projects_cache.refresh()
                reply.finished.connect(lambda: self.show_project_compatibility_page())

    def show_project_local_dir_selection(self):
        assert self.cloud_project

        self.is_project_download = True

        self.stackedWidget.setCurrentWidget(self.projectLocalDirPage)
        self.buttonBox.button(QDialogButtonBox.Apply).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.Apply).setText(self.tr("Next"))

        export_dirname = Path(self.preferences.value("cloudDirectory"))
        export_dirname = export_dirname.joinpath(
            self.cloud_project.name
            if self.cloud_project.owner
            == self.network_manager.auth().config("username")
            else f"{self.cloud_project.owner}__{self.cloud_project.name}"
        )

        self.localDirectoryLineEdit.setText(
            QDir.toNativeSeparators(str(get_unique_empty_dirname(export_dirname)))
        )
        self.localDirectoryButton.clicked.connect(
            make_folder_selector(self.localDirectoryLineEdit)
        )

    def show_project_compatibility_page(self):
        feedback = None
        if self.cloud_project and self.cloud_project.is_current_qgis_project:
            checker = ProjectChecker(QgsProject.instance())
            feedback = checker.check(ExportType.Cloud)

        if feedback and feedback.count > 0:
            has_errors = len(feedback.error_feedbacks) > 0

            feedback_table = CheckerFeedbackTable(feedback)
            self.feedbackTableWrapperLayout.addWidget(feedback_table)
            self.stackedWidget.setCurrentWidget(self.projectCompatibilityPage)
            self.buttonBox.button(QDialogButtonBox.Apply).setVisible(True)
            self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(not has_errors)
            self.buttonBox.button(QDialogButtonBox.Apply).setText(self.tr("Next"))
        else:
            self.show_project_files_fetching_page()

    def show_project_files_fetching_page(self):
        self.stackedWidget.setCurrentWidget(self.getProjectFilesPage)
        self.buttonBox.button(QDialogButtonBox.Apply).setVisible(False)
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
            reply.finished.connect(lambda: self.prepare_project_transfer())

    def show_end_page(
        self, feedback: str = "", logs_model: TransferFileLogsModel = None
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

        self.buttonBox.button(QDialogButtonBox.Abort).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Apply).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Cancel).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.Cancel).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)

        self.detailedLogEndPageGroupBox.setVisible(False)
        if logs_model:
            self.detailedLogEndPageGroupBox.setVisible(True)
            self.detailedLogEndPageListView.setModel(logs_model)
            self.detailedLogEndPageListView.setModelColumn(0)

    def prepare_project_transfer(self):
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

        if len(list(self.cloud_project.files_to_sync)) == 0:
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

        self.project_transfer = CloudTransferrer(
            self.network_manager,
            self.cloud_project,
        )
        self.project_transfer.error.connect(self.on_error)
        self.project_transfer.upload_progress.connect(self.on_upload_transfer_progress)
        self.project_transfer.download_progress.connect(
            self.on_download_transfer_progress
        )
        self.project_transfer.finished.connect(self.on_transfer_finished)

        self.explanationLabel.setVisible(False)

        self.build_files_tree()
        if self.is_project_download:
            self._file_tree_set_checkboxes(ProjectFileCheckout.Cloud)
            self._start_synchronization()
        else:
            if self.cloud_project.user_role == "reader":
                self.preferNoneButton.setVisible(False)
                self.preferLocalButton.setVisible(False)
                self.preferCloudButton.setVisible(False)

            self.stackedWidget.setCurrentWidget(self.filesPage)
            self.buttonBox.button(QDialogButtonBox.Apply).setVisible(True)
            self.explanationLabel.setVisible(True)

            self.cloudProjectNameValueLabel.setText(
                '<a href="{}{}">{}</a>'.format(
                    self.network_manager.url,
                    self.cloud_project.url,
                    self.cloud_project.name_with_owner,
                )
            )
            self.projectLocalDirValueLineEdit.setText(
                self.cloud_project.local_dir,
            )
            self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(True)
            self.buttonBox.button(QDialogButtonBox.Apply).setText(
                self.tr("Perform Actions")
                if len(self.cloud_project.get_files(ProjectFileCheckout.Cloud)) > 0
                else self.tr("Upload Project")
            )

            if len(self.cloud_project.get_files(ProjectFileCheckout.Cloud)) > 0:
                self.buttonBox.button(QDialogButtonBox.Apply).setText(
                    self.tr("Perform Actions")
                )
                self.explanationLabel.setText(
                    self.tr(
                        "Some of the files on QFieldCloud differ from the files stored in the local project directory. "
                    )
                )
            else:
                self.buttonBox.button(QDialogButtonBox.Apply).setText(
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

        for project_file in self.project_transfer.cloud_project.files_to_sync:
            parts = tuple(project_file.path.parts)
            for part_idx, part in enumerate(parts):
                if len(stack) > part_idx and stack[part_idx][0] == part:
                    continue
                else:
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
                    item.setData(0, Qt.UserRole, project_file)
                    self.add_file_checkbox_buttons(item, project_file)
                else:
                    # TODO make a fancy button that marks all the child items as checked or not
                    pass
        self.filesTree.expandAll()
        # NOTE END algorithmic part

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
            self.buttonBox.button(QDialogButtonBox.Ok).setVisible(True)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
            self.buttonBox.button(QDialogButtonBox.Abort).setVisible(True)
            self.buttonBox.button(QDialogButtonBox.Apply).setVisible(False)
            self.buttonBox.button(QDialogButtonBox.Cancel).setVisible(False)

            files: Dict[str, List[ProjectFile]] = {
                "to_upload": [],
                "to_download": [],
                "to_delete": [],
            }

            for item_idx in range(self.filesTree.topLevelItemCount()):
                item = self.filesTree.topLevelItem(item_idx)

                self.traverse_tree_item(item, files)

            hasUploads = len(files["to_upload"]) > 0
            self.uploadLabel.setVisible(hasUploads)
            self.uploadProgressBar.setVisible(hasUploads)
            self.uploadProgressFeedbackLabel.setVisible(hasUploads)

            hasDownloads = len(files["to_download"]) > 0
            self.downloadLabel.setVisible(hasDownloads)
            self.downloadProgressBar.setVisible(hasDownloads)
            self.downloadProgressFeedbackLabel.setVisible(hasDownloads)

            # if the cloud project being synchronize matches the currently open project, don't offer to open if nothing is being downloaded
            if (
                not hasDownloads
                and self.network_manager.projects_cache.currently_open_project
                and self.cloud_project.id
                == self.network_manager.projects_cache.currently_open_project.id
            ):
                self.openProjectCheck.setChecked(False)
                self.openProjectCheck.setVisible(False)

            self.show_progress_page(files)

            assert self.project_transfer

            self.project_transfer.sync(
                files["to_upload"], files["to_download"], files["to_delete"]
            )

            assert self.project_transfer.transfers_model

            self.detailedLogListView.setModel(self.project_transfer.transfers_model)
            self.detailedLogListView.setModelColumn(0)

    def traverse_tree_item(
        self, item: QTreeWidgetItem, files: Dict[str, List[ProjectFile]]
    ) -> None:
        project_file = item.data(0, Qt.UserRole)

        if project_file:
            assert item.childCount() == 0

            project_file_action = self.project_file_action(item)

            if (
                project_file_action == ProjectFileAction.DeleteLocal
                or project_file_action == ProjectFileAction.DeleteCloud
            ):
                files["to_delete"].append(project_file)
            elif (
                project_file_action == ProjectFileAction.DownloadAndCreate
                or project_file_action == ProjectFileAction.DownloadAndReplace
            ):
                files["to_download"].append(project_file)
            elif (
                project_file_action == ProjectFileAction.UploadAndCreate
                or project_file_action == ProjectFileAction.UploadAndReplace
            ):
                files["to_upload"].append(project_file)
            elif project_file_action == ProjectFileAction.NoAction:
                pass
            else:
                raise Exception(f"Unknown project file action {project_file_action}")

            return

        for child_idx in range(item.childCount()):
            self.traverse_tree_item(item.child(child_idx), files)

    def add_file_checkbox_buttons(
        self, item: QTreeWidgetItem, project_file: ProjectFile
    ) -> None:
        assert self.cloud_project

        is_local_enabled = self.cloud_project.user_role != "reader"
        is_cloud_enabled = bool(project_file.checkout & ProjectFileCheckout.Cloud)
        is_local_checked = False
        if is_local_enabled and project_file.local_path_exists:
            local_updated_at = os.path.getmtime(
                os.path.join(self.cloud_project.local_dir, project_file.path)
            )
            cloud_updated_at = 0.0
            if project_file.updated_at:
                cloud_updated_at = datetime.strptime(
                    project_file.updated_at, "%d.%m.%Y %H:%M:%S %Z"
                ).timestamp()
            is_local_checked = local_updated_at > cloud_updated_at

        local_checkbox = QCheckBox()
        local_checkbox.setEnabled(is_local_enabled)
        local_checkbox.setChecked(is_local_checked)
        local_checkbox.toggled.connect(
            lambda _is_checked: self.on_local_checkbox_toggled(item)
        )
        local_checkbox_widget = QWidget()
        local_checkbox_layout = QHBoxLayout()
        local_checkbox_layout.setAlignment(Qt.AlignCenter)
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
        cloud_checkbox_layout.setAlignment(Qt.AlignCenter)
        cloud_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        cloud_checkbox_layout.addWidget(cloud_checkbox)
        cloud_checkbox_widget.setLayout(cloud_checkbox_layout)

        arrow_widget = QWidget()
        arrow_layout = QHBoxLayout()
        arrow_layout.setAlignment(Qt.AlignCenter)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        localLabel, arrowLabel, cloudLabel = QLabel(), QLabel(), QLabel()
        localLabel.setObjectName("local")
        arrowLabel.setObjectName("arrow")
        cloudLabel.setObjectName("cloud")
        arrow_layout.addWidget(localLabel)
        arrow_layout.addWidget(arrowLabel)
        arrow_layout.addWidget(cloudLabel)
        arrow_widget.setLayout(arrow_layout)

        self.filesTree.setItemWidget(item, 1, local_checkbox_widget)
        self.filesTree.setItemWidget(item, 2, arrow_widget)
        self.filesTree.setItemWidget(item, 3, cloud_checkbox_widget)

        self.update_detail(item)

    def on_error(self, descr: str, error: Exception = None) -> None:
        self.errorLabel.setVisible(True)
        self.errorLabel.setText(self.errorLabel.text() + "\n" + descr)

    def on_upload_transfer_progress(self, fraction: float) -> None:
        self.uploadProgressBar.setValue(int(fraction * 100))

    def on_download_transfer_progress(self, fraction: float) -> None:
        self.downloadProgressBar.setValue(int(fraction * 100))

    def on_transfer_finished(self) -> None:
        assert self.project_transfer

        self.show_end_page(
            self.tr("Transfer finished."),
            self.project_transfer.transfers_model,
        )

        self.project_synchronized.emit()

    def on_local_checkbox_toggled(self, item: QTreeWidgetItem) -> None:
        project_file = item.data(0, Qt.UserRole)
        project_file.checkout & ProjectFileCheckout.Cloud

        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 3).children()[1]

        if local_checkbox.isChecked():
            cloud_checkbox.setChecked(False)

        self.update_detail(item)

    def on_cloud_checkbox_toggled(self, item: QTreeWidgetItem) -> None:
        project_file = item.data(0, Qt.UserRole)
        project_file.local_path_exists

        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 3).children()[1]

        if cloud_checkbox.isChecked():
            local_checkbox.setChecked(False)

        self.update_detail(item)

    def project_file_action(self, item: QTreeWidgetItem) -> ProjectFileAction:
        project_file = item.data(0, Qt.UserRole)
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

        project_file = item.data(0, Qt.UserRole)
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
            raise Exception(f"Unknown project file action {project_file_action}")

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
        project_file = item.data(0, Qt.UserRole)

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

    def show_progress_page(self, files: Dict[str, List[ProjectFile]]) -> None:
        total_delete_count = 0
        local_delete_count = 0
        cloud_delete_count = 0
        download_count = len(files["to_download"])
        upload_count = len(files["to_upload"])

        for f in files["to_delete"]:
            total_delete_count += 1

            if f.checkout & ProjectFileCheckout.Local:
                local_delete_count += 1
            elif f.checkout & ProjectFileCheckout.Local:
                cloud_delete_count += 1

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
