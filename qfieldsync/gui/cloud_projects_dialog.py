# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudProjectsDialog
                                 A QGIS plugin
 Sync your projects to QField on android
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
import functools
import glob
from pathlib import Path
from typing import Optional

from qgis.PyQt.QtCore import pyqtSignal, Qt, QItemSelectionModel, QDateTime
from qgis.PyQt.QtWidgets import (
    QDialog,
    QToolButton,
    QTableWidgetItem,
    QWidget,
    QCheckBox,
    QHBoxLayout,
    QTreeWidgetItem,
    QFileDialog,
    QMessageBox,
    QAbstractButton,
    QMenu,
    QAction,
    QPushButton,
    QHeaderView,
)
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.PyQt.uic import loadUiType

from qgis.core import QgsProject
from qgis.utils import iface

from qfieldsync.gui.cloud_transfer_dialog import CloudTransferDialog
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.core import Preferences
from qfieldsync.core.cloud_project import CloudProject, ProjectFile, ProjectFileCheckout
from qfieldsync.core.cloud_api import CloudException, CloudNetworkAccessManager
from qfieldsync.core.cloud_transferrer import CloudTransferrer
from qfieldsync.utils.cloud_utils import closure, to_cloud_title


CloudProjectsDialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/cloud_projects_dialog.ui'))


def select_table_row(func):
    @functools.wraps(func)
    def closure(self, table_widget, row_idx):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            index = table_widget.model().index(row_idx, 0)
            table_widget.setCurrentIndex(index)
            table_widget.selectionModel().select(index, QItemSelectionModel.ClearAndSelect|QItemSelectionModel.Rows)
            return func(self, *args, **kwargs)
        return wrapper

    return closure


class CloudProjectsDialog(QDialog, CloudProjectsDialogUi):
    projects_refreshed = pyqtSignal()

    def __init__(self, network_manager: CloudNetworkAccessManager, parent: QWidget = None, project: CloudProject = None) -> None:
        """Constructor."""
        super(CloudProjectsDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.setWindowModality(Qt.WindowModal)
        self.preferences = Preferences()
        self.network_manager = network_manager
        self.current_cloud_project = project
        self.transfer_dialog = None
        self.project_transfer = None
        self.default_local_dir = '~/qfieldsync/cloudprojects/'

        if not self.network_manager.has_token():
            login_dlg = CloudLoginDialog(self.network_manager, self)
            login_dlg.authenticate()
            login_dlg.accepted.connect(lambda: self.welcomeLabelValue.setText(self.preferences.value('qfieldCloudLastUsername')))
            login_dlg.accepted.connect(lambda: self.network_manager.projects_cache.refresh())
            login_dlg.rejected.connect(lambda: self.close())
        else:
            self.welcomeLabelValue.setText(self.preferences.value('qfieldCloudLastUsername'))

        if self.network_manager.has_token():
            self.show_projects()

        self.use_current_project_directory_action = QAction(QIcon(), self.tr('Use Current Project Directory'))
        self.use_current_project_directory_action.triggered.connect(self.on_use_current_project_directory_action_triggered)

        self.createButton.clicked.connect(self.on_create_button_clicked)
        self.refreshButton.clicked.connect(self.on_refresh_button_clicked)
        self.backButton.clicked.connect(self.on_back_button_clicked)
        self.submitButton.clicked.connect(self.on_submit_button_clicked)
        self.logoutButton.clicked.connect(self.on_logout_button_clicked)
        self.projectsTable.cellDoubleClicked.connect(self.on_projects_table_cell_double_clicked)
        self.buttonBox.clicked.connect(self.on_button_box_clicked)
        self.projectsTable.selectionModel().selectionChanged.connect(self.on_projects_table_selection_changed)
        self.localDirLineEdit.textChanged.connect(self.on_local_dir_line_edit_text_changed)
        self.localDirButton.clicked.connect(self.on_local_dir_button_clicked)
        self.localDirButton.setMenu(QMenu())
        self.localDirButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.localDirButton.menu().addAction(self.use_current_project_directory_action)

        self.network_manager.projects_cache.projects_started.connect(self.on_projects_cached_projects_started)
        self.network_manager.projects_cache.projects_error.connect(self.on_projects_cached_projects_error)
        self.network_manager.projects_cache.projects_updated.connect(self.on_projects_cached_projects_updated)
        self.network_manager.projects_cache.project_files_started.connect(self.on_projects_cached_project_files_started)
        self.network_manager.projects_cache.project_files_error.connect(self.on_projects_cached_project_files_error)
        self.network_manager.projects_cache.project_files_updated.connect(self.on_projects_cached_project_files_updated)

        self.projectFilesTree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.projectFilesTree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.projectFilesTree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.projectFilesTree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.projectFilesToggleExpandButton.clicked.connect(self.on_project_files_toggle_expand_button_clicked)


    def on_projects_cached_projects_started(self) -> None:
        self.projectsStack.setEnabled(False)
        self.feedbackLabel.setVisible(False)
        self.feedbackLabel.setText('')

        print('on_projects_cached_projects_started')


    def on_projects_cached_projects_error(self, error: str) -> None:
        self.projectsStack.setEnabled(True)
        self.feedbackLabel.setVisible(True)
        self.feedbackLabel.setText(error)

        print('on_projects_cached_projects_error')


    def on_projects_cached_projects_updated(self) -> None:
        self.projectsStack.setEnabled(True)
        self.projects_refreshed.emit()
        self.show_projects()

        print('on_projects_cached_projects_updated')


    def on_projects_cached_project_files_started(self, project_id: str) -> None:
        self.projectFilesTab.setEnabled(False)
        self.feedbackLabel.setVisible(False)
        self.feedbackLabel.setText('')

        print('on_projects_cached_project_files_started', project_id)


    def on_projects_cached_project_files_error(self, project_id: str, error: str) -> None:
        self.projectFilesTab.setEnabled(True)

        if self.current_cloud_project.id != project_id:
            return

        self.feedbackLabel.setText('Obtaining project files list failed: {}'.format(error))
        self.feedbackLabel.setVisible(True)

        print('on_projects_cached_project_files_error', project_id)


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
        if not self.current_cloud_project or self.current_cloud_project.id != project_id:
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

        for project_file in self.current_cloud_project.get_files(ProjectFileCheckout.Cloud):
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

                    for version_idx, version_obj in enumerate(project_file.versions):
                        version_item = QTreeWidgetItem()

                        version_item.setData(0, Qt.UserRole, version_obj)
                        version_item.setText(0, 'Version {}'.format(version_idx + 1))
                        version_item.setText(1, str(version_obj['size']))
                        version_item.setTextAlignment(1, Qt.AlignRight)
                        version_item.setText(2, version_obj['last_modified'])
                        
                        save_as_btn = QPushButton()
                        save_as_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/cloud_download.svg')))
                        save_as_btn.clicked.connect(self.on_save_as_btn_version_clicked(project_file, version_idx))
                        save_as_widget = QWidget()
                        save_as_layout = QHBoxLayout()
                        save_as_layout.setAlignment(Qt.AlignCenter)
                        save_as_layout.setContentsMargins(0, 0, 0, 0)
                        save_as_layout.addWidget(save_as_btn)
                        save_as_widget.setLayout(save_as_layout)

                        item.addChild(version_item)

                        self.projectFilesTree.setItemWidget(version_item, 3, save_as_widget)
                else:
                    item.setExpanded(True)

                    # TODO make a fancy button that marks all the child items as checked or not
        # NOTE END algorithmic part


    @closure
    def on_save_as_btn_version_clicked(self, project_file: ProjectFile, version_idx: int, _is_checked: bool):
        assert project_file.versions
        assert version_idx < len(project_file.versions)

        basename = '{}_{}{}'.format(project_file.path.stem, str(version_idx + 1), project_file.path.suffix)

        if project_file.local_path:
            default_path = project_file.local_path.parent.joinpath(basename)
        else:
            default_path = Path(QgsProject().instance().homePath()).joinpath(project_file.path.parent, basename)

        version_dest_filename, _ = QFileDialog.getSaveFileName(self, self.tr('Select version file name…'), str(default_path))

        if not version_dest_filename:
            return

        reply = self.network_manager.get_file(
            self.current_cloud_project.id + '/' + str(project_file.name) + '/', 
            str(version_dest_filename), 
            project_file.versions[version_idx]['created_at'])
        reply.downloadProgress.connect(lambda r, t: self.on_download_file_progress(reply, r, t, project_file=project_file))
        reply.finished.connect(lambda: self.on_download_file_finished(reply, project_file=project_file))


    def on_download_file_progress(self, _reply: QNetworkReply, bytes_received: int, bytes_total: int, project_file: ProjectFile) -> None:
        self.feedbackLabel.setVisible(True)
        self.feedbackLabel.setText(self.tr('Downloading file "{}" at {}%…').format(project_file.name, int((bytes_total / bytes_received) * 100)))


    def on_download_file_finished(self, reply: QNetworkReply, project_file: ProjectFile) -> None:
        try:
            CloudNetworkAccessManager.handle_response(reply, False)
        except CloudException as err:
            self.feedbackLabel.setText(self.tr('Downloading file "{}" failed: {}'.format(project_file.name, str(err))))
            self.feedbackLabel.setVisible(True)
            return

        self.feedbackLabel.setVisible(False)
        self.feedbackLabel.setText('')


    def on_use_current_project_directory_action_triggered(self, _toggled: bool) -> None:
        self.localDirLineEdit.setText(QgsProject.instance().homePath())


    def on_button_box_clicked(self, _button: QAbstractButton) -> None:
        self.close()


    def on_local_dir_line_edit_text_changed(self) -> None:
        local_dir = self.localDirLineEdit.text()
        self.submitButton.setEnabled(False)

        if local_dir == '' or self._is_local_dir_valid(local_dir):
            self.localDirLineEdit.setStyleSheet('')
            self.submitButton.setEnabled(True)
        else:
            self.localDirLineEdit.setStyleSheet('color: red;')
            self.submitButton.setEnabled(False)

        if self.current_cloud_project:
            self.current_cloud_project.update_data({'local_dir': local_dir})


    def on_local_dir_button_clicked(self) -> None:
        self.localDirLineEdit.setText(self.select_local_dir())


    def on_logout_button_clicked(self) -> None:
        self.logoutButton.setEnabled(False)
        self.feedbackLabel.setVisible(False)

        reply = self.network_manager.logout()
        reply.finished.connect(lambda: self.on_logout_reply_finished(reply))


    def on_logout_reply_finished(self, reply: QNetworkReply) -> None:
        try:
            CloudNetworkAccessManager.json_object(reply)
        except CloudException as err:
            self.feedbackLabel.setText('Logout failed: {}'.format(str(err)))
            self.feedbackLabel.setVisible(True)
            self.logoutButton.setEnabled(True)
            return

        self.projectsTable.setRowCount(0)
        self.network_manager.set_token('')

        self.preferences.set_value('qfieldCloudLastToken', '')

        self.close()


    def on_refresh_button_clicked(self) -> None:
        self.network_manager.projects_cache.refresh()


    def show_projects(self) -> None:
        self.feedbackLabel.setText('')
        self.feedbackLabel.setVisible(False)

        self.projectsTable.setRowCount(0)
        self.projectsTable.setSortingEnabled(False)

        if self.network_manager.projects_cache.projects is None:
            self.network_manager.projects_cache.refresh()
            return

        for cloud_project in self.network_manager.projects_cache.projects:
            count = self.projectsTable.rowCount()
            self.projectsTable.insertRow(count)
            
            item = QTableWidgetItem(cloud_project.name)
            item.setData(Qt.UserRole, cloud_project)
            item.setData(Qt.EditRole, cloud_project.name)

            cbx = QCheckBox()
            cbx.setEnabled(False)
            cbx.setChecked(cloud_project.is_private)
            # # it's more UI friendly when the checkbox is centered, an ugly workaround to achieve it
            cbx_widget = QWidget()
            cbx_layout = QHBoxLayout()
            cbx_layout.setAlignment(Qt.AlignCenter)
            cbx_layout.setContentsMargins(0, 0, 0, 0)
            cbx_layout.addWidget(cbx)
            cbx_widget.setLayout(cbx_layout)
            # NOTE the margin is not updated when the table column is resized, so better rely on the code above
            # cbx.setStyleSheet("margin-left:50%; margin-right:50%;")

            btn_sync = QToolButton()
            btn_sync.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/cloud.svg')))
            btn_sync.setToolTip(self.tr('Synchronize with QFieldCloud'))
            btn_edit = QToolButton()
            btn_edit.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/edit.svg')))
            btn_edit.setToolTip(self.tr('Edit project data'))
            btn_delete = QToolButton()
            btn_delete.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/delete.svg')))
            btn_delete.setToolTip(self.tr('Delete project'))
            btn_launch = QToolButton()
            btn_launch.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/launch.svg')))
            btn_launch.setToolTip(self.tr('Open project'))
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignCenter)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addWidget(btn_sync)
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_delete)
            btn_layout.addWidget(btn_launch)
            btn_widget.setLayout(btn_layout)

            btn_sync.clicked.connect(self.on_project_sync_button_clicked(self.projectsTable, count)) # pylint: disable=too-many-function-args
            btn_edit.clicked.connect(self.on_project_edit_button_clicked(self.projectsTable, count)) # pylint: disable=too-many-function-args
            btn_delete.clicked.connect(self.on_project_delete_button_clicked(self.projectsTable, count)) # pylint: disable=too-many-function-args
            btn_launch.clicked.connect(self.on_project_launch_button_clicked(self.projectsTable, count)) # pylint: disable=too-many-function-args

            self.projectsTable.setItem(count, 0, item)
            self.projectsTable.setItem(count, 1, QTableWidgetItem(cloud_project.owner))
            self.projectsTable.setCellWidget(count, 2, cbx_widget)
            self.projectsTable.setCellWidget(count, 3, btn_widget)

            font = QFont()

            if cloud_project.is_current_qgis_project:
                font.setBold(True)

            self.projectsTable.item(count, 0).setFont(font)
            self.projectsTable.item(count, 1).setFont(font)

        self.projectsTable.resizeColumnsToContents()
        self.projectsTable.sortByColumn(2, Qt.AscendingOrder)
        self.projectsTable.setSortingEnabled(True)


    def sync(self) -> None:
        assert self.current_cloud_project is not None

        if self.current_cloud_project.cloud_files is not None:
            if not self.current_cloud_project.local_dir:
                self.current_cloud_project.update_data({'local_dir': self.select_local_dir()})

            if not self.current_cloud_project.local_dir:
                return

            self.show_sync_popup()
            return

        reply = self.network_manager.projects_cache.get_project_files(self.current_cloud_project.id)
        reply.finished.connect(lambda: self.sync())


    def launch(self) -> None:
        assert self.current_cloud_project is not None

        if self.current_cloud_project.cloud_files is not None:
            project_filename = self.current_cloud_project.local_project_file

            # no local project name found
            if not project_filename:
                iface.messageBar().pushInfo('QFieldSync', self.tr('Cannot find local project file. Please first synchronize.'))
                return

            # it is the current project, no need to reload
            if str(project_filename.local_path) == QgsProject().instance().fileName():
                iface.messageBar().pushInfo('QFieldSync', self.tr('Already loaded the selected project.'))
                return

            if QgsProject.instance().read(str(project_filename.local_path)):
                selected_row_idx = self.projectsTable.selectedItems()[0].row()

                for row_idx in range(self.projectsTable.rowCount()):
                    font = QFont()

                    if row_idx == selected_row_idx:
                        font.setBold(True)

                    self.projectsTable.item(row_idx, 0).setFont(font)
                    self.projectsTable.item(row_idx, 1).setFont(font)


        reply = self.network_manager.projects_cache.get_project_files(self.current_cloud_project.id)
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
        initial_path = self.localDirLineEdit.text() or str(Path(QgsProject.instance().homePath()).parent) or self.default_local_dir

        # cloud project is empty, you can upload a local project into it
        if self.current_cloud_project is None or (self.current_cloud_project.cloud_files is not None and len(self.current_cloud_project.cloud_files) == 0):
            while local_dir is None:
                local_dir = QFileDialog.getExistingDirectory(self, self.tr('Upload local project to QFieldCloud'), initial_path)

                if local_dir == '':
                    return

                if not self._is_local_dir_valid(local_dir, True):
                    QMessageBox.warning(None, self.tr('Multiple QGIS projects'), self.tr('When QFieldCloud project has no remote files, the local checkout directory may contain no more than 1 QGIS project.'))
                    local_dir = None
                    continue

                break

            return local_dir

        # cloud project exists and has files in it, so checkout in an empty dir
        else:
            assert self.current_cloud_project
            assert self.current_cloud_project.cloud_files is not None

            while local_dir is None:
                local_dir = QFileDialog.getExistingDirectory(self, self.tr('Save QFieldCloud project at'), initial_path)

                if local_dir == '':
                    return

                if len(os.listdir(local_dir)) > 0:
                    QMessageBox.warning(None, self.tr('QFieldSync checkout requires empty directory'), self.tr('When QFieldCloud project contains remote files the checkout destination needs to be an empty directory.'))
                    local_dir = None
                    continue

                break

        return local_dir


    def _is_local_dir_valid(self, local_dir: str, should_check_recursive: bool = False) -> bool:
        """Checks whether the selected local dir is suitable for empty cloud project

        Args:
            local_dir (str): local directory
            should_check_recursive (bool, optional): If True, it might take too much time to check recursive the whole file tree. Defaults to False.

        Returns:
            bool: whether the chosen local directory is suitable or not
        """
        if Path(local_dir).is_file():
            return False

        return True

        if (len(glob.glob('{}/**/*.qgs'.format(local_dir), recursive=should_check_recursive)) > 1 
            or len(glob.glob('{}/**/*.qgz'.format(local_dir), recursive=should_check_recursive)) > 1):
            return False

        # already associated local dir with a cloud project
        if CloudProject.get_cloud_project_id(local_dir) is not None:
            return False

        return True


    @select_table_row
    def on_project_sync_button_clicked(self, is_toggled: bool) -> None:
        self.sync()


    @select_table_row
    def on_project_delete_button_clicked(self, is_toggled: bool) -> None:
        button_pressed = QMessageBox.question(
            self, 
            self.tr('Delete project'), 
            self.tr('Are you sure you want to delete project "{}"?').format(self.current_cloud_project.name))

        if button_pressed != QMessageBox.Yes:
            return

        self.projectsStack.setEnabled(False)

        reply = self.network_manager.delete_project(self.current_cloud_project.id)
        reply.finished.connect(lambda: self.on_delete_project_reply_finished(reply))


    @select_table_row
    def on_project_launch_button_clicked(self, is_toggled: bool) -> None:
        self.launch()


    @select_table_row
    def on_project_edit_button_clicked(self, is_toggled: bool) -> None:
        self.show_project_form()


    def on_delete_project_reply_finished(self, reply: QNetworkReply) -> None:
        self.projectsStack.setEnabled(True)

        try:
            CloudNetworkAccessManager.handle_response(reply, False)
        except CloudException as err:
            self.feedbackLabel.setText(self.tr('Project delete failed: {}').format(str(err)))
            self.feedbackLabel.setVisible(True)
            return

        self.network_manager.projects_cache.refresh()


    def on_projects_table_cell_double_clicked(self, _row: int, _col: int) -> None:
        self.show_project_form()


    def on_create_button_clicked(self) -> None:
        self.projectsTable.clearSelection()
        self.show_project_form()


    def show_project_form(self) -> None:
        self.show()

        self.projectsStack.setCurrentWidget(self.projectsFormPage)
        self.projectTabs.setCurrentWidget(self.projectFormTab)

        self.projectOwnerComboBox.clear()
        self.projectOwnerComboBox.addItem(self.preferences.value('qfieldCloudLastUsername'), self.preferences.value('qfieldCloudLastUsername'))
        self.projectFilesTree.clear()

        if self.current_cloud_project is None:
            self.projectTabs.setTabEnabled(1, False)
            self.projectTabs.setTabEnabled(2, False)
            self.projectNameLineEdit.setText(to_cloud_title(QgsProject.instance().title()))
            self.projectDescriptionTextEdit.setPlainText('')
            self.projectIsPrivateCheckBox.setChecked(True)

            if CloudProject.is_cloud_project():
                self.localDirLineEdit.setText('')
            else:
                self.localDirLineEdit.setText(QgsProject().instance().homePath())

        else:
            self.projectTabs.setTabEnabled(1, True)
            self.projectTabs.setTabEnabled(2, True)
            # TODO validate project name to match QFieldCloudRequirements
            self.projectNameLineEdit.setText(self.current_cloud_project.name)
            self.projectDescriptionTextEdit.setPlainText(self.current_cloud_project.description)
            self.projectIsPrivateCheckBox.setChecked(self.current_cloud_project.is_private)
            self.localDirLineEdit.setText(self.current_cloud_project.local_dir)
            self.projectUrlLabelValue.setText('<a href="{url}">{url}</a>'.format(url=self.current_cloud_project.url))
            self.createdAtLabelValue.setText(QDateTime.fromString(self.current_cloud_project.created_at, Qt.ISODateWithMs).toString())
            self.updatedAtLabelValue.setText(QDateTime.fromString(self.current_cloud_project.updated_at, Qt.ISODateWithMs).toString())
            self.lastSyncedAtLabelValue.setText(QDateTime.fromString(self.current_cloud_project.updated_at, Qt.ISODateWithMs).toString())

            index = self.projectOwnerComboBox.findData(self.current_cloud_project.owner)
            
            if index == -1:
                self.projectOwnerComboBox.insertItem(0, self.current_cloud_project.owner, self.current_cloud_project.owner)
                self.projectOwnerComboBox.setCurrentIndex(0)

            self.network_manager.projects_cache.get_project_files(self.current_cloud_project.id)


    def on_back_button_clicked(self) -> None:
        self.projectsStack.setCurrentWidget(self.projectsListPage)


    def on_submit_button_clicked(self) -> None:
        cloud_project_data = {
            'name': self.projectNameLineEdit.text(),
            'description': self.projectDescriptionTextEdit.toPlainText(),
            'owner': self.projectOwnerComboBox.currentData(),
            'private': self.projectIsPrivateCheckBox.isChecked(),
            'local_dir': self.localDirLineEdit.text()
        }

        self.projectsFormPage.setEnabled(False)
        self.feedbackLabel.setVisible(True)

        if self.current_cloud_project is None:
            self.feedbackLabel.setText(self.tr('Creating project…'))
            reply = self.network_manager.create_project(
                cloud_project_data['name'], 
                cloud_project_data['owner'], 
                cloud_project_data['description'], 
                cloud_project_data['private'])
            reply.finished.connect(lambda: self.on_create_project_finished(reply, local_dir=cloud_project_data['local_dir']))
        else:
            self.current_cloud_project.update_data(cloud_project_data)
            self.feedbackLabel.setText(self.tr('Updating project…'))

            reply = self.network_manager.update_project(
                self.current_cloud_project.id, 
                self.current_cloud_project.name, 
                self.current_cloud_project.owner, 
                self.current_cloud_project.description, 
                self.current_cloud_project.is_private)
            reply.finished.connect(lambda: self.on_update_project_finished(reply))


    def on_create_project_finished(self, reply: QNetworkReply, local_dir: str = None) -> None:
        self.projectsFormPage.setEnabled(True)

        try:
            payload = CloudNetworkAccessManager.json_object(reply)
        except CloudException as err:
            self.feedbackLabel.setText('Project create failed: {}'.format(str(err)))
            self.feedbackLabel.setVisible(True)
            return

        # save `local_dir` configuration permanently, `CloudProject` constructor does this for free
        _project = CloudProject({
            **payload,
            'local_dir': local_dir,
        })

        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.feedbackLabel.setVisible(False)

        self.network_manager.projects_cache.refresh()


    def on_update_project_finished(self, reply: QNetworkReply) -> None:
        self.projectsFormPage.setEnabled(True)

        try:
            CloudNetworkAccessManager.json_object(reply)
        except CloudException as err:
            self.feedbackLabel.setText('Project update failed: {}'.format(str(err)))
            self.feedbackLabel.setVisible(True)
            return

        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.feedbackLabel.setVisible(False)

        self.network_manager.projects_cache.refresh()


    def on_projects_table_selection_changed(self, _new_selection, _old_selection) -> None:
        if self.projectsTable.selectionModel().hasSelection():
            row_idx = self.projectsTable.currentRow()
            self.current_cloud_project = self.projectsTable.item(row_idx, 0).data(Qt.UserRole)
        else:
            self.current_cloud_project = None


    def show_sync_popup(self) -> None:
        assert self.current_cloud_project is not None, 'No project to download selected'
        assert self.current_cloud_project.local_dir, 'Cannot download a project without `local_dir` properly set'

        self.project_transfer = CloudTransferrer(self.network_manager, self.current_cloud_project)
        self.transfer_dialog = CloudTransferDialog(self.project_transfer, self)
        self.transfer_dialog.rejected.connect(self.on_transfer_dialog_rejected)
        self.transfer_dialog.accepted.connect(self.on_transfer_dialog_accepted)
        self.transfer_dialog.show()


    def on_transfer_dialog_rejected(self) -> None:
        self.project_transfer.abort_requests()
        self.transfer_dialog.close()
        self.project_transfer = None
        self.transfer_dialog = None


    def on_transfer_dialog_accepted(self) -> None:
        QgsProject().instance().reloadAllLayers()

        self.transfer_dialog.close()
        self.project_transfer = None
        self.transfer_dialog = None
