# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudProjectsDialog
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2020-07-28
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
from pathlib import Path
from typing import Optional

from qgis.core import Qgis, QgsApplication, QgsProject
from qgis.PyQt.QtCore import (
    QDateTime,
    QItemSelectionModel,
    QRegularExpression,
    Qt,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QRegularExpressionValidator,
    QValidator,
)
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QAction,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QToolButton,
    QTreeWidgetItem,
    QWidget,
)
from qgis.PyQt.uic import loadUiType
from qgis.utils import iface

from qfieldsync.core import Preferences
from qfieldsync.core.cloud_api import CloudException, CloudNetworkAccessManager
from qfieldsync.core.cloud_project import CloudProject, ProjectFile, ProjectFileCheckout
from qfieldsync.core.cloud_transferrer import FileTransfer
from qfieldsync.gui.cloud_create_project_widget import CloudCreateProjectWidget
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.gui.cloud_transfer_dialog import CloudTransferDialog
from qfieldsync.utils.cloud_utils import LocalDirFeedback, closure, local_dir_feedback
from qfieldsync.utils.permissions import can_delete_project
from qfieldsync.utils.qt_utils import rounded_pixmap

CloudProjectsDialogUi, _ = loadUiType(
    str(Path(__file__).parent.joinpath("../ui/cloud_projects_dialog.ui"))
)


class WindowsIconFixWorkDir(object):
    """Workaround for older QT (M$ QGIS <3.16.5) to make the custom icons load with relative path."""

    def __init__(self, path):
        self.path = path
        self.old_cwd = os.getcwd()

    def __enter__(self):
        os.chdir(self.path)

    def __exit__(self, *_args):
        os.chdir(self.old_cwd)


class CloudProjectsDialog(QDialog, CloudProjectsDialogUi):
    projects_refreshed = pyqtSignal()

    def __init__(
        self,
        network_manager: CloudNetworkAccessManager,
        parent: QWidget = None,
        project: CloudProject = None,
    ) -> None:
        """Constructor."""
        super(CloudProjectsDialog, self).__init__(parent=parent)

        with WindowsIconFixWorkDir(Path(__file__).parent.parent.joinpath("ui")):
            self.setupUi(self)

        self.setWindowModality(Qt.WindowModal)
        self.preferences = Preferences()
        self.network_manager = network_manager
        self._current_cloud_project_id = project.id if project else None
        self._suggest_upload_files = False
        self.transfer_dialog = None
        self.project_transfer = None

        self.update_welcome_label()

        self.use_current_project_directory_action = QAction(
            QIcon(), self.tr("Use Current Project Directory")
        )
        self.use_current_project_directory_action.triggered.connect(
            self.on_use_current_project_directory_action_triggered
        )

        self.projectNameLineEdit.setValidator(
            QRegularExpressionValidator(
                QRegularExpression("^[a-zA-Z][-a-zA-Z0-9_]{2,}$")
            )
        )

        # TODO show when public projects are ready
        self.projectsType.hide()
        self.projectsType.addItem(self.tr("My projects"))
        self.projectsType.addItem(self.tr("Community"))
        self.projectsType.setCurrentIndex(0)
        self.projectsType.currentIndexChanged.connect(lambda: self.show_projects())

        self.projectsTable.setColumnWidth(0, int(self.projectsTable.width() * 0.75))
        self.projectsTable.setColumnWidth(1, int(self.projectsTable.width() * 0.2))

        self.synchronizeButton.clicked.connect(
            lambda: self.on_project_sync_button_clicked()
        )
        self.synchronizeButton.setEnabled(False)
        self.editButton.setIcon(
            QgsApplication.getThemeIcon("/mActionProjectProperties.svg")
        )
        self.editButton.clicked.connect(lambda: self.on_project_edit_button_clicked())
        self.editButton.setEnabled(False)
        self.openButton.setIcon(QgsApplication.getThemeIcon("/mActionFileOpen.svg"))
        self.openButton.clicked.connect(lambda: self.on_project_launch_button_clicked())
        self.openButton.setEnabled(False)
        self.deleteButton.clicked.connect(
            lambda: self.on_project_delete_button_clicked()
        )
        self.deleteButton.setEnabled(False)

        self.show()

        if self.network_manager.has_token():
            self.show_projects()
            self.createButton.setEnabled(True)
        else:
            CloudLoginDialog.show_auth_dialog(
                self.network_manager,
                lambda: self.on_auth_accepted(),
                lambda: self.close(),
                parent=self,
            )
            self.createButton.setEnabled(False)

        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.createProjectWidget = CloudCreateProjectWidget(
            iface,
            self.network_manager,
            QgsProject.instance(),
            self,
        )

        self.projectCreatePage.layout().addWidget(self.createProjectWidget)
        self.createProjectWidget.finished.connect(
            lambda project_id: self.on_create_project_finished(project_id)
        )
        self.createProjectWidget.error.connect(
            lambda m: self.on_create_project_error(m)
        )
        self.createProjectWidget.canceled.connect(
            lambda: self.on_create_project_canceled()
        )

        self.refreshButton.setIcon(QgsApplication.getThemeIcon("/mActionRefresh.svg"))
        self.refreshButton.clicked.connect(lambda: self.on_refresh_button_clicked())

        self.createButton.clicked.connect(lambda: self.on_create_button_clicked())
        self.backButton.clicked.connect(lambda: self.on_back_button_clicked())
        self.submitButton.clicked.connect(lambda: self.on_submit_button_clicked())
        self.editOnlineButton.clicked.connect(self.on_edit_online_button_clicked)
        self.projectsTable.cellDoubleClicked.connect(
            lambda: self.on_projects_table_cell_double_clicked()
        )

        self.buttonBox.button(QDialogButtonBox.Close).clicked.connect(
            lambda: self.on_button_box_clicked()
        )
        self.buttonBox.button(QDialogButtonBox.Help).clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://docs.qfield.org/"))
        )
        self.avatarButton.clicked.connect(lambda: self.on_logout_button_clicked())

        self.projectsTable.selectionModel().selectionChanged.connect(
            lambda: self.on_projects_table_selection_changed()
        )
        self.localDirLineEdit.textChanged.connect(
            lambda: self.on_local_dir_line_edit_text_changed()
        )
        self.localDirButton.clicked.connect(lambda: self.on_local_dir_button_clicked())
        self.localDirButton.setMenu(QMenu())
        self.localDirButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.localDirButton.menu().addAction(self.use_current_project_directory_action)
        self.localDirOpenButton.clicked.connect(
            lambda: self.on_local_dir_open_button_clicked()
        )
        self.localDirOpenButton.setIcon(
            QgsApplication.getThemeIcon("/mActionFileOpen.svg")
        )

        self.network_manager.avatar_success.connect(lambda: self.update_welcome_label())
        self.network_manager.login_finished.connect(lambda: self.update_welcome_label())
        self.network_manager.logout_success.connect(lambda: self._on_logout_success())
        self.network_manager.logout_failed.connect(
            lambda err: self._on_logout_failed(err)
        )
        self.network_manager.projects_cache.projects_started.connect(
            lambda: self.on_projects_cached_projects_started()
        )
        self.network_manager.projects_cache.projects_error.connect(
            lambda err: self.on_projects_cached_projects_error(err)
        )
        self.network_manager.projects_cache.projects_updated.connect(
            lambda: self.on_projects_cached_projects_updated()
        )
        self.network_manager.projects_cache.project_files_started.connect(
            lambda project_id: self.on_projects_cached_project_files_started(project_id)
        )
        self.network_manager.projects_cache.project_files_error.connect(
            lambda project_id, error: self.on_projects_cached_project_files_error(
                project_id, error
            )
        )
        self.network_manager.projects_cache.project_files_updated.connect(
            lambda project_id: self.on_projects_cached_project_files_updated(project_id)
        )

        self.projectFilesTree.header().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.projectFilesTree.header().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.projectFilesTree.header().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.projectFilesTree.header().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )

        self.update_ui_state()

    @property
    def current_cloud_project(self) -> Optional[CloudProject]:
        return self.network_manager.projects_cache.find_project(
            self._current_cloud_project_id
        )

    @current_cloud_project.setter
    def current_cloud_project(self, value: Optional[CloudProject]):
        if (
            (value is not None and self._current_cloud_project_id == value.id)
            or value is None
            and self._current_cloud_project_id is None
        ):
            return

        self._current_cloud_project_id = value.id if value else None
        self.update_project_table_selection()
        self.update_ui_state()

    def set_feedback(self, msg, color: str = Qt.red):
        color_hex = QColor(color).name()
        self.feedbackLabel.setStyleSheet(f"QLabel {{ color: {color_hex}; }}")

        if msg:
            self.feedbackLabel.setVisible(True)
            self.feedbackLabel.setText(msg)
        else:
            self.feedbackLabel.setVisible(False)
            self.feedbackLabel.setText("")

    def on_auth_accepted(self):
        self.network_manager.projects_cache.refresh()
        self.update_welcome_label()
        self.createButton.setEnabled(True)

    def on_projects_cached_projects_started(self) -> None:
        self.projectsStack.setEnabled(False)
        self.set_feedback("Loading projects list…", Qt.blue)

    def on_projects_cached_projects_error(self, error: str) -> None:
        self.projectsStack.setEnabled(True)
        self.set_feedback(error)

    def on_projects_cached_projects_updated(self) -> None:
        self.projectsStack.setEnabled(True)
        self.projects_refreshed.emit()
        self.show_projects()

    def on_projects_cached_project_files_started(self, project_id: str) -> None:
        self.projectFilesTab.setEnabled(False)
        self.set_feedback(None)

    def on_projects_cached_project_files_error(
        self, project_id: str, error: str
    ) -> None:
        self.projectFilesTab.setEnabled(True)

        if self.current_cloud_project and self.current_cloud_project.id != project_id:
            return

        self.set_feedback("Obtaining project files list failed: {}".format(error))

    def on_project_files_toggle_expand_button_clicked(self) -> None:
        should_expand = not self.projectFilesTree.topLevelItem(0).data(1, Qt.UserRole)
        self.projectFilesTree.topLevelItem(0).setData(1, Qt.UserRole, should_expand)

        for idx in range(self.projectFilesTree.topLevelItemCount()):
            self.expand_state(self.projectFilesTree.topLevelItem(idx), should_expand)

    def expand_state(self, item: QTreeWidgetItem, should_expand: bool) -> None:
        item.setExpanded(should_expand)

        for idx in range(item.childCount()):
            child = item.child(idx)

            if child.childCount() == 0:
                continue

            self.expand_state(child, should_expand)

    def on_projects_cached_project_files_updated(self, project_id: str) -> None:
        if (
            not self.current_cloud_project
            or self.current_cloud_project.id != project_id
        ):
            return

        self.projectFilesTab.setEnabled(True)

        # NOTE algorithmic part
        # ##########
        # The "cloud_files" objects are assumed to be sorted alphabetically by name.
        # First split filenames into parts. For example: '/home/ninja.file' will result into ['home', 'ninja.file'] parts.
        # Then store pairs of the part and the corresponding QTreeWidgetItem in a stack.
        # Pop and push to the stack when the current filename part does not match the previous one.
        # ##########
        stack = []

        for project_file in self.current_cloud_project.get_files(
            ProjectFileCheckout.Cloud
        ):
            assert isinstance(project_file.versions, list)

            parts = tuple(project_file.path.parts)
            for part_idx, part in enumerate(parts):
                if len(stack) > part_idx and stack[part_idx][0] == part:
                    continue
                else:
                    stack = stack[0:part_idx]

                item = QTreeWidgetItem()
                item.setText(0, part)

                stack.append((part, item))

                if len(stack) == 1:
                    self.projectFilesTree.addTopLevelItem(item)
                else:
                    stack[-2][1].addChild(stack[-1][1])

                # the length of the stack and the parts is equal for file entries
                if len(stack) == len(parts):
                    item.setToolTip(0, project_file.name)
                    item.setData(0, Qt.UserRole, project_file)

                    item.setText(1, str(project_file.size))
                    item.setTextAlignment(1, Qt.AlignRight)
                    item.setText(2, project_file.created_at)

                    versions_count = len(project_file.versions)
                    for version_idx, version_obj in enumerate(project_file.versions):
                        version_item = QTreeWidgetItem()

                        version_item.setData(0, Qt.UserRole, version_obj)
                        # TODO remove default value `versions_count - version_idx`, the "display" key is standard for newer QFC releases
                        version_display = version_obj.get(
                            "display", versions_count - version_idx
                        )
                        version_item.setText(0, "Version {}".format(version_display))
                        version_item.setText(1, str(version_obj["size"]))
                        version_item.setTextAlignment(1, Qt.AlignRight)
                        version_item.setText(2, version_obj["last_modified"])

                        save_as_btn = QPushButton()
                        save_as_btn.setIcon(
                            QIcon(
                                str(
                                    Path(__file__).parent.joinpath(
                                        "../resources/cloud_download.svg"
                                    )
                                )
                            )
                        )
                        save_as_btn.clicked.connect(
                            self.on_save_as_btn_version_clicked(
                                project_file, version_idx
                            )
                        )
                        save_as_widget = QWidget()
                        save_as_layout = QHBoxLayout()
                        save_as_layout.setAlignment(Qt.AlignCenter)
                        save_as_layout.setContentsMargins(0, 0, 0, 0)
                        save_as_layout.addWidget(save_as_btn)
                        save_as_widget.setLayout(save_as_layout)

                        item.addChild(version_item)

                        self.projectFilesTree.setItemWidget(
                            version_item, 3, save_as_widget
                        )
                else:
                    item.setExpanded(True)

                    # TODO make a fancy button that marks all the child items as checked or not
        # NOTE END algorithmic part

    @closure
    def on_save_as_btn_version_clicked(
        self, project_file: ProjectFile, version_idx: int, _is_checked: bool
    ):
        assert self.current_cloud_project
        assert project_file.versions
        assert version_idx < len(project_file.versions)

        basename = "{}_{}{}".format(
            project_file.path.stem,
            str(len(project_file.versions) - version_idx),
            project_file.path.suffix,
        )

        if project_file.local_path:
            default_path = project_file.local_path.parent.joinpath(basename)
        else:
            default_path = Path(QgsProject().instance().homePath()).joinpath(
                project_file.path.parent, basename
            )

        version_dest_filename, _ = QFileDialog.getSaveFileName(
            self, self.tr("Select version file name…"), str(default_path)
        )

        if not version_dest_filename:
            return

        transfer = FileTransfer(
            self.network_manager,
            self.current_cloud_project,
            FileTransfer.Type.DOWNLOAD,
            project_file,
            Path(version_dest_filename),
            project_file.versions[version_idx]["version_id"],
        )
        transfer.progress.connect(
            lambda r, t: self.on_download_file_progress(transfer, r, t)
        )
        transfer.finished.connect(lambda: self.on_download_file_finished(transfer))
        transfer.transfer()

    def on_download_file_progress(
        self,
        transfer: FileTransfer,
        bytes_received: int,
        bytes_total: int,
    ) -> None:
        progress = int((bytes_received / bytes_total) * 100) if bytes_total > 0 else 100

        self.set_feedback(
            self.tr('Downloading file "{}" at {}%…').format(transfer.filename, progress)
        )

    def on_download_file_finished(self, transfer: FileTransfer) -> None:
        if transfer.is_failed:
            self.set_feedback(
                self.tr(
                    'Downloading file "{}" failed: {}'.format(
                        transfer.name, str(transfer.error)
                    )
                )
            )
            return

        self.set_feedback(None)

    def on_use_current_project_directory_action_triggered(self, _toggled: bool) -> None:
        self.localDirLineEdit.setText(str(Path(QgsProject.instance().homePath())))

    def on_button_box_clicked(self) -> None:
        self.close()

    def on_local_dir_line_edit_text_changed(self) -> None:
        local_dir = self.localDirLineEdit.text()
        self.update_local_dir_feedback(local_dir)

    def on_local_dir_button_clicked(self) -> None:
        dirname = self.select_local_dir()
        if dirname:
            self.localDirLineEdit.setText(str(Path(dirname)))

    def on_local_dir_open_button_clicked(self) -> None:
        dirname = self.localDirLineEdit.text()
        if dirname and Path(dirname).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(dirname))

    def on_logout_button_clicked(self) -> None:
        self.avatarButton.setEnabled(False)
        self.set_feedback(None)
        self.network_manager.logout()

    def on_refresh_button_clicked(self) -> None:
        self.network_manager.projects_cache.refresh()

    def show_projects(self) -> None:
        self.set_feedback(None)

        self.projectsTable.setRowCount(0)
        self.projectsTable.setSortingEnabled(False)

        if self.network_manager.projects_cache.projects is None:
            self.network_manager.projects_cache.refresh()
            return

        if len(self.network_manager.projects_cache.projects) == 0:
            self.set_feedback(
                "You don't have any projects, create some by clicking the button in the bottom bar.",
                Qt.blue,
            )
            return

        self.projectsTable.setEnabled(True)

        for cloud_project in self.network_manager.projects_cache.projects:
            if (
                self.projectsType.currentIndex() != 1
                and cloud_project.user_role_origin == "public"
            ) or (
                self.projectsType.currentIndex() == 1
                and cloud_project.user_role_origin != "public"
            ):
                continue

            count = self.projectsTable.rowCount()
            self.projectsTable.insertRow(count)

            item = QTableWidgetItem(cloud_project.name)

            if cloud_project.status == "ok":
                color = QColor("#87af87")
            elif cloud_project.status == "busy":
                color = QColor("#9e6a03")
            elif cloud_project.status == "failed":
                color = QColor("#dc3545")
            else:
                raise NotImplementedError()

            pm = QPixmap(40, 20)
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            painter.setPen(QPen(color, 8, Qt.SolidLine))
            painter.setBrush(QBrush(color, Qt.SolidPattern))
            painter.drawEllipse(30, 10, 5, 5)
            icon = QIcon(
                str(
                    Path(__file__).parent.joinpath(
                        "../resources/cloud_project.svg"
                        if cloud_project.local_dir
                        else "../resources/cloud_project_remote.svg"
                    )
                )
            )
            painter.drawPixmap(0, 0, icon.pixmap(pm.size()))
            del painter

            item.setData(Qt.UserRole, cloud_project)
            item.setData(Qt.EditRole, cloud_project.name)
            item.setData(
                Qt.DecorationRole,
                pm,
            )

            tooltip = self.tr("Cloud status: {}. \nLocal status: ").format(
                cloud_project.status
            )

            if bool(cloud_project.local_dir):
                tooltip += self.tr('Project stored at "{}".').format(
                    str(cloud_project.local_dir)
                )
            else:
                tooltip += self.tr("No local dir configured.")

            item.setToolTip(tooltip)

            self.projectsTable.setItem(count, 0, item)
            self.projectsTable.setItem(count, 1, QTableWidgetItem(cloud_project.owner))

        self.projectsTable.sortByColumn(1, Qt.AscendingOrder)
        self.projectsTable.sortByColumn(0, Qt.AscendingOrder)
        self.projectsTable.setSortingEnabled(True)
        self.update_project_table_selection()

        if self._suggest_upload_files:
            self._suggest_upload_files = False

            self.sync()

    def sync(self) -> None:
        assert self.current_cloud_project is not None
        self.show_sync_popup()

    def launch(self) -> None:
        assert self.current_cloud_project is not None

        if self.current_cloud_project.local_dir is None:
            self.sync()
            return

        if self.current_cloud_project.cloud_files is not None:
            project_filename = self.current_cloud_project.local_project_file

            # no local project name found
            if not project_filename:
                iface.messageBar().pushInfo(
                    f'QFieldSync "{self.current_cloud_project.name}":',
                    self.tr(
                        "Cannot find local project file. QFieldSync will first download the project."
                    ),
                )
                return

            # it is the current project, no need to reload
            if str(project_filename.local_path) == QgsProject().instance().fileName():
                iface.messageBar().pushInfo(
                    f'QFieldSync "{self.current_cloud_project.name}":',
                    self.tr("Already loaded the selected project."),
                )
                return

            iface.addProject(str(project_filename.local_path))

            self.update_project_table_selection()
            self.update_ui_state()

            return

        reply = self.network_manager.projects_cache.get_project_files(
            self.current_cloud_project.id
        )
        reply.finished.connect(lambda: self.launch())

    def select_local_dir(self) -> Optional[str]:
        """
        ```
            if there is saved location for this project id #
                upload all the files (or the missing on the cloud only)
                download all the files (or the missing on the local only) #
                if project is the current one: #
                    reload the project #
            else
                if the cloud project is not empty
                    ask for path that is empty dir
                    download the project there
                else
                    ask for path #

                    if path contains .qgs file: #
                        assert single .qgs file #
                        upload all the files #

                save the project location #

            ask should that project be opened
        ```
        """

        local_dir = None
        initial_path = (
            self.localDirLineEdit.text()
            or str(Path(QgsProject.instance().homePath()).parent)
            or self.preferences.value("cloudDirectory")
        )

        # cloud project is empty, you can upload a local project into it
        if self.current_cloud_project is None or (
            self.current_cloud_project.cloud_files is not None
            and len(self.current_cloud_project.cloud_files) == 0
        ):
            while local_dir is None:
                local_dir = QFileDialog.getExistingDirectory(
                    self, self.tr("Upload local project to QFieldCloud…"), initial_path
                )

                if local_dir == "":
                    return

                feedback, feedback_msg = local_dir_feedback(
                    local_dir, no_project_status=LocalDirFeedback.Warning
                )
                title = self.tr("Cannot upload local QFieldSync directory")

                # all is good, we can continue
                if feedback == LocalDirFeedback.Success:
                    break

                if feedback == LocalDirFeedback.Error:
                    QMessageBox.critical(self, title, feedback_msg)
                elif feedback == LocalDirFeedback.Warning:
                    QMessageBox.warning(self, title, feedback_msg)
                    break

                local_dir = None
                continue

            return local_dir

        # cloud project exists and has files in it, so checkout in an empty dir
        else:
            assert self.current_cloud_project

            while local_dir is None:
                local_dir = QFileDialog.getExistingDirectory(
                    self, self.tr("Save QFieldCloud project to…"), initial_path
                )

                if local_dir == "":
                    return

                # when the dir is empty, all is good. But if not there are some file, we need to ask the user to confirm what to do
                if list(Path(local_dir).iterdir()):
                    buttons = QMessageBox.Ok | QMessageBox.Abort
                    feedback, feedback_msg = local_dir_feedback(
                        local_dir, single_project_status=LocalDirFeedback.Warning
                    )
                    title = self.tr("QFieldSync checkout prefers an empty directory")
                    answer = None

                    if feedback == LocalDirFeedback.Error:
                        answer = QMessageBox.critical(
                            self, title, feedback_msg, buttons
                        )
                    elif feedback == LocalDirFeedback.Warning:
                        answer = QMessageBox.warning(self, title, feedback_msg, buttons)

                    if answer == QMessageBox.Abort:
                        local_dir = None
                        continue

                break

        return local_dir

    def on_project_sync_button_clicked(self) -> None:
        self.sync()

    def on_project_edit_button_clicked(self) -> None:
        self.show_project_form()

    def on_project_launch_button_clicked(self) -> None:
        self.launch()

    def on_project_delete_button_clicked(self) -> None:
        username = self.network_manager.user_details["username"]
        project_name = self.current_cloud_project.name
        expected_input = f"{username}/{project_name}"

        def ask(maybe_warning: str = ""):
            delete_msg = self.tr("Delete QFieldCloud project")
            are_you_sure = self.tr(
                "Are you sure you want to delete this QFieldCloud project?"
            )
            confirm_with = self.tr("To confirm deletion, please type")
            reassuring_remark = self.tr(
                "The project will be permanently deleted from QFieldCloud, your local copy will remain unaffected"
            )
            return QInputDialog().getText(
                self,
                delete_msg,
                f"<p><b>{are_you_sure}</b></p>{maybe_warning}<p>{confirm_with} <em>{expected_input}</em>. {reassuring_remark}.</p>",
            )

        text, ok = ask()

        if ok:
            clean_text = text.strip()
            error = self.tr("Incorrect project name!")
            while clean_text != expected_input:
                updated_text, updated_ok = ask(f"<p style='color:red'>{error}</p>")
                if not updated_ok:
                    return
                clean_text = updated_text.strip()

            self.projectsStack.setEnabled(False)
            reply = self.network_manager.delete_project(self.current_cloud_project.id)
            reply.finished.connect(lambda: self.on_delete_project_reply_finished(reply))

    def on_delete_project_reply_finished(self, reply: QNetworkReply) -> None:
        self.projectsStack.setEnabled(True)

        try:
            self.network_manager.handle_response(reply, False)
        except CloudException as err:
            self.set_feedback(self.tr("Project delete failed: {}").format(str(err)))
            return

        self.network_manager.projects_cache.refresh()

    def on_projects_table_cell_double_clicked(self) -> None:
        self.show_project_form()

    def on_create_button_clicked(self) -> None:
        self.show_create_project()

    def show_project_form(self) -> None:
        assert self.current_cloud_project

        self.show()

        self.projectsStack.setCurrentWidget(self.projectsFormPage)
        self.projectTabs.setCurrentWidget(self.projectFormTab)
        self.projectFilesTree.clear()
        self.projectNameLineEdit.setEnabled(True)
        self.projectDescriptionTextEdit.setEnabled(True)

        self.projectTabs.setTabEnabled(1, True)
        self.projectTabs.setTabEnabled(2, True)
        self.projectNameLineEdit.setText(self.current_cloud_project.name)
        self.projectDescriptionTextEdit.setPlainText(
            self.current_cloud_project.description
        )
        self.projectIsPrivateCheckBox.setChecked(self.current_cloud_project.is_private)
        self.projectOwnerLineEdit.setText(self.current_cloud_project.owner)
        self.localDirLineEdit.setText(self.current_cloud_project.local_dir or "")
        self.projectUrlLabelValue.setText(
            '<a href="{url}">{url}</a>'.format(
                url=(self.network_manager.url + self.current_cloud_project.url)
            )
        )
        self.createdAtLabelValue.setText(
            QDateTime.fromString(
                self.current_cloud_project.created_at, Qt.ISODateWithMs
            ).toString()
        )
        self.updatedAtLabelValue.setText(
            QDateTime.fromString(
                self.current_cloud_project.updated_at, Qt.ISODateWithMs
            ).toString()
        )
        self.lastSyncedAtLabelValue.setText(
            QDateTime.fromString(
                self.current_cloud_project.updated_at, Qt.ISODateWithMs
            ).toString()
        )

        self.update_local_dir_feedback(self.localDirLineEdit.text())

        if self.current_cloud_project.user_role not in ("admin", "manager"):
            self.projectNameLineEdit.setEnabled(False)
            self.projectDescriptionTextEdit.setEnabled(False)

        self.network_manager.projects_cache.get_project_files(
            self.current_cloud_project.id
        )

    def show_create_project(self):
        self.projectsTable.clearSelection()
        self.projectsStack.setCurrentWidget(self.projectCreatePage)
        self.createProjectWidget.restart()

    def on_back_button_clicked(self) -> None:
        self.projectsStack.setCurrentWidget(self.projectsListPage)

    def on_submit_button_clicked(self) -> None:
        assert self.current_cloud_project

        should_update_online = False
        if (
            self.current_cloud_project.name != self.projectNameLineEdit.text()
            or self.current_cloud_project.description
            != self.projectDescriptionTextEdit.toPlainText()
        ):
            cloud_project_data = {
                "name": self.projectNameLineEdit.text(),
                "description": self.projectDescriptionTextEdit.toPlainText(),
            }

            if (
                self.projectNameLineEdit.validator().validate(
                    cloud_project_data["name"], 0
                )[0]
                != QValidator.Acceptable
            ):
                QMessageBox.warning(
                    None,
                    self.tr("Invalid project name"),
                    self.tr(
                        "You cannot create a new project without setting a valid name first."
                    ),
                )
                return

            self.projectsFormPage.setEnabled(False)

            self.set_feedback(self.tr("Updating project…"))

            reply = self.network_manager.update_project(
                self.current_cloud_project.id,
                cloud_project_data["name"],
                cloud_project_data["description"],
            )
            reply.finished.connect(lambda: self.on_update_project_finished(reply))

            should_update_online = True

        if self.current_cloud_project.local_dir != self.localDirLineEdit.text():
            self.current_cloud_project.update_data(
                {"local_dir": self.localDirLineEdit.text()}
            )

        if not should_update_online:
            self.projectsStack.setCurrentWidget(self.projectsListPage)

    def on_edit_online_button_clicked(self) -> None:
        assert self.current_cloud_project

        QDesktopServices.openUrl(
            QUrl(self.network_manager.url + self.current_cloud_project.url)
        )

    def on_create_project_finished(self, project_id) -> None:
        self._current_cloud_project_id = project_id
        self._suggest_upload_files = True
        self.projectsStack.setCurrentWidget(self.projectsListPage)

    def on_create_project_error(self, message) -> None:
        self.set_feedback(message)
        iface.messageBar().pushMessage(message, Qgis.Critical, 0)

    def on_create_project_canceled(self) -> None:
        self.projectsStack.setCurrentWidget(self.projectsListPage)

    def update_welcome_label(self) -> None:
        if self.network_manager.has_token():
            avatar_filename = self.network_manager.user_details.get("avatar_filename")
            self.avatarButton.setVisible(True)
            if not avatar_filename:
                avatar_filename = os.path.join(
                    os.path.dirname(__file__), "../resources/qfieldcloud_logo.png"
                )

            self.avatarButton.setVisible(True)
            pixmap = rounded_pixmap(avatar_filename, self.avatarButton.height())
            self.avatarButton.setIcon(QIcon(pixmap))

            self.welcomeLabel.setText(
                self.tr("Greetings {}.").format(
                    f'<a href="{self.network_manager.url}">{self.network_manager.auth().config("username")}</a>'
                )
            )

            if self.network_manager.url == self.network_manager.server_urls()[0]:
                self.welcomeLabel.setToolTip(
                    self.tr("You are signed in with this username.")
                )
            else:
                self.welcomeLabel.setToolTip(
                    self.tr("You are signed in with this username at {}.").format(
                        self.network_manager.url
                    )
                )
        else:
            self.avatarButton.setVisible(False)
            self.welcomeLabel.setText("Signed out.")
            self.welcomeLabel.setToolTip("")

    def update_ui_state(self) -> None:
        if (
            self.network_manager.projects_cache.currently_open_project
            or self.network_manager.projects_cache.is_currently_open_project_cloud_local
        ):
            pass
            # self.convertButton.setEnabled(False)
        else:
            pass
            # self.convertButton.setEnabled(True)

    def update_project_table_selection(self) -> None:
        font = QFont()

        for row_idx in range(self.projectsTable.rowCount()):
            cloud_project: CloudProject = self.projectsTable.item(row_idx, 0).data(
                Qt.UserRole
            )
            is_currently_open_project = (
                cloud_project
                == self.network_manager.projects_cache.currently_open_project
            )

            font.setBold(is_currently_open_project)

            self.projectsTable.item(row_idx, 0).setFont(font)
            self.projectsTable.item(row_idx, 1).setFont(font)

            if (
                self.current_cloud_project is None
                and self._current_cloud_project_id == cloud_project.id
            ) or cloud_project == self.current_cloud_project:
                index = self.projectsTable.model().index(row_idx, 0)
                self.projectsTable.setCurrentIndex(index)
                self.projectsTable.selectionModel().select(
                    index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
                )
                self.projectsTable.scrollToItem(
                    self.projectsTable.item(row_idx, 0),
                    QAbstractItemView.EnsureVisible,
                )

            self.update_project_buttons()

    def on_update_project_finished(self, reply: QNetworkReply) -> None:
        self.projectsFormPage.setEnabled(True)

        try:
            self.network_manager.json_object(reply)
        except CloudException as err:
            self.set_feedback("Project update failed: {}".format(str(err)))
            return

        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.set_feedback(None)

        self.network_manager.projects_cache.refresh()

    def on_projects_table_selection_changed(self) -> None:
        if self.projectsTable.selectionModel().hasSelection():
            row_idx = self.projectsTable.currentRow()
            self.current_cloud_project = self.projectsTable.item(row_idx, 0).data(
                Qt.UserRole
            )

        self.update_project_buttons()

    def update_project_buttons(self) -> None:
        has_selection = False
        is_currently_open_project = False
        can_delete_selected_project = False
        if self.projectsTable.selectionModel().hasSelection():
            has_selection = True
            row_idx = self.projectsTable.currentRow()
            self.current_cloud_project = self.projectsTable.item(row_idx, 0).data(
                Qt.UserRole
            )
            assert self.current_cloud_project

            is_currently_open_project = (
                self.current_cloud_project
                == self.network_manager.projects_cache.currently_open_project
            )
            can_delete_selected_project = can_delete_project(self.current_cloud_project)
            root_project_files = self.current_cloud_project.root_project_files
            if len(root_project_files) == 1:
                self.openButton.setToolTip(
                    self.tr('Open Project "{}"').format(root_project_files[0])
                )
            elif len(root_project_files) == 0:
                self.openButton.setToolTip(
                    self.tr(
                        "Cannot open project since no local .qgs or .qgz project file found"
                    )
                )
            else:
                self.openButton.setToolTip(
                    self.tr(
                        "Multiple .qgs or .qgz project files found in the project directory"
                    )
                )

        self.synchronizeButton.setEnabled(has_selection)
        self.editButton.setEnabled(has_selection)
        self.openButton.setEnabled(has_selection and not is_currently_open_project)
        self.deleteButton.setEnabled(has_selection and can_delete_selected_project)

    def show_sync_popup(self) -> None:
        assert self.current_cloud_project is not None, "No project to download selected"

        self.transfer_dialog = CloudTransferDialog.show_transfer_dialog(
            self.network_manager, self.current_cloud_project, None, None, self
        )
        self.transfer_dialog.rejected.connect(self.on_transfer_dialog_rejected)
        self.transfer_dialog.accepted.connect(self.on_transfer_dialog_accepted)
        self.transfer_dialog.open()

    def update_local_dir_feedback(self, local_dir: str) -> None:
        feedback, feedback_msg = local_dir_feedback(
            local_dir, no_path_status=LocalDirFeedback.Warning
        )
        self.localDirFeedbackLabel.setText(feedback_msg)
        self.localDirOpenButton.setEnabled(bool(local_dir) and Path(local_dir).exists())

        if feedback == LocalDirFeedback.Error:
            self.localDirFeedbackLabel.setStyleSheet("color: red;")
            self.submitButton.setEnabled(False)
        elif feedback == LocalDirFeedback.Warning:
            self.localDirFeedbackLabel.setStyleSheet("color: orange;")
            self.submitButton.setEnabled(True)
        else:
            self.localDirFeedbackLabel.setStyleSheet("color: green;")
            self.submitButton.setEnabled(True)

    def on_transfer_dialog_rejected(self) -> None:
        if self.project_transfer:
            self.project_transfer.abort_requests()

        if self.transfer_dialog:
            self.transfer_dialog.close()

        self.project_transfer = None
        self.transfer_dialog = None

    def on_transfer_dialog_accepted(self) -> None:
        QgsProject().instance().reloadAllLayers()
        self.show_projects()

        if self.transfer_dialog:
            self.transfer_dialog.close()

        self.project_transfer = None
        self.transfer_dialog = None

    def _on_logout_success(self) -> None:
        self.projectsTable.setRowCount(0)

        self.close()

    def _on_logout_failed(self, err: str) -> None:
        self.set_feedback("Sign out failed: {}".format(str(err)))
        self.avatarButton.setEnabled(True)
