# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldCloudDialog
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

from qgis.PyQt.QtCore import Qt, QItemSelectionModel, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QToolButton,
    QTableWidgetItem,
    QWidget,
    QCheckBox,
    QHBoxLayout,
    QTreeWidgetItem,
    QFileDialog,
    QMessageBox,
)
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.core import QgsProject
from qgis.PyQt.uic import loadUiType

from qfieldsync.core import CloudProject, Preferences
from qfieldsync.core.cloud_api import ProjectTransferType, ProjectTransferrer, QFieldCloudNetworkManager
from qfieldsync.utils.cloud_utils import to_cloud_title
from qfieldsync.gui.qfield_cloud_transfer_dialog import QFieldCloudTransferDialog


QFieldCloudDialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/qfield_cloud_dialog.ui'))


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


class QFieldCloudDialog(QDialog, QFieldCloudDialogUi):
    projects_refreshed = pyqtSignal()

    def __init__(self, iface, cloud_network_manager, parent=None):
        """Constructor.
        """
        super(QFieldCloudDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.iface = iface
        self.preferences = Preferences()
        self.cloud_network_manager = cloud_network_manager
        self.transfer_dialog = None
        self.current_cloud_project = None
        self.project_transfer = None
        self.project_download_transfer = None

        self.usernameLineEdit.setText(self.preferences.value('qfieldCloudLastUsername'))

        if self.cloud_network_manager.has_token():
            self.usernameLineEdit.setEnabled(False)
            self.passwordLineEdit.setEnabled(False)
            self.loginButton.setEnabled(False)
            self.rememberMeCheckBox.setEnabled(False)
            self.logoutButton.setEnabled(True)
            self.show_projects(self.preferences.value('qfieldCloudProjectsCache'))

        self.loginButton.clicked.connect(self.onLoginButtonClicked)
        self.logoutButton.clicked.connect(self.onLogoutButtonClicked)
        self.createButton.clicked.connect(self.onCreateButtonClicked)
        self.refreshButton.clicked.connect(self.onRefreshButtonClicked)
        self.backButton.clicked.connect(self.onBackButtonClicked)
        self.submitButton.clicked.connect(self.onSubmitButtonClicked)
        self.projectsTable.cellDoubleClicked.connect(self.onProjectsTableCellDoubleClicked)

        self.projectsTable.selectionModel().selectionChanged.connect(self.onProjectsTableSelectionChanged)


    def onLoginButtonClicked(self):
        self.loginButton.setEnabled(False)
        self.logoutButton.setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)
        self.loginFeedbackLabel.setVisible(False)

        self.preferences.set_value('qfieldCloudProjectsCache', [])

        username = self.usernameLineEdit.text()
        password = self.passwordLineEdit.text()

        reply = self.cloud_network_manager.login(username, password)
        reply.finished.connect(self.onLoginReplyFinished(reply)) # pylint: disable=no-value-for-parameter


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onLoginReplyFinished(self, reply, payload):
        if reply.error() != QNetworkReply.NoError or payload is None:
            self.loginFeedbackLabel.setText("Login failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.loginFeedbackLabel.setVisible(True)
            self.loginButton.setEnabled(True)
            self.rememberMeCheckBox.setEnabled(True)
            return

        if self.rememberMeCheckBox.isChecked():
            # TODO permanently store the token
            # resp['token']
            pass

        self.cloud_network_manager.set_token(payload['token'])

        self.preferences.set_value('qfieldCloudLastUsername', payload['username'])

        self.usernameLineEdit.setEnabled(False)
        self.passwordLineEdit.setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)
        self.loginButton.setEnabled(False)
        self.logoutButton.setEnabled(True)

        self.getProjects()


    def onLogoutButtonClicked(self):
        self.logoutButton.setEnabled(False)
        self.loginFeedbackLabel.setVisible(False)

        reply = self.cloud_network_manager.logout()
        reply.finished.connect(self.onLogoutReplyFinished(reply)) # pylint: disable=no-value-for-parameter


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onLogoutReplyFinished(self, reply, payload):
        if reply.error() != QNetworkReply.NoError or payload is None:
            self.loginFeedbackLabel.setText("Logout failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.loginFeedbackLabel.setVisible(True)
            self.logoutButton.setEnabled(True)
            return

        self.cloud_network_manager.set_token("")
        self.projectsTable.setRowCount(0)
        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.projectsStackGroup.setEnabled(False)

        self.usernameLineEdit.setText(self.preferences.value('qfieldCloudLastUsername'))
        self.usernameLineEdit.setEnabled(True)
        self.passwordLineEdit.setText("")
        self.passwordLineEdit.setEnabled(True)
        self.rememberMeCheckBox.setEnabled(True)
        self.loginButton.setEnabled(True)

        self.preferences.set_value('qfieldCloudProjectsCache', [])


    def onRefreshButtonClicked(self):
        self.getProjects()


    def getProjects(self):
        self.projectsStackGroup.setEnabled(False)
        self.projectsFeedbackLabel.setText("Loading…")
        self.projectsFeedbackLabel.setVisible(True)

        reply = self.cloud_network_manager.get_projects()
        reply.finished.connect(self.onGetProjectsReplyFinished(reply)) # pylint: disable=no-value-for-parameter


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onGetProjectsReplyFinished(self, reply, payload):
        self.projectsStackGroup.setEnabled(True)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Project refresh failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

        self.preferences.set_value('qfieldCloudProjectsCache', payload)

        self.projects_refreshed.emit()
        self.show_projects(payload)


    def show_projects(self, projects):
        self.projectsFeedbackLabel.setText("")
        self.projectsFeedbackLabel.setVisible(False)

        self.projectsTable.setRowCount(0)
        self.projectsTable.setSortingEnabled(False)

        for project in projects:
            cloud_project = CloudProject(project)

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
            btn_sync.setToolTip(self.tr("Synchronize with QFieldCloud"))
            btn_edit = QToolButton()
            btn_edit.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/edit.svg')))
            btn_edit.setToolTip(self.tr("Edit project data"))
            btn_delete = QToolButton()
            btn_delete.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/delete.svg')))
            btn_delete.setToolTip(self.tr("Delete project"))
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignCenter)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addWidget(btn_sync)
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_delete)
            btn_widget.setLayout(btn_layout)

            btn_sync.clicked.connect(self.onProjectSyncButtonClicked(self.projectsTable, count)) # pylint: disable=too-many-function-args
            btn_edit.clicked.connect(self.onProjectEditButtonClicked(self.projectsTable, count)) # pylint: disable=too-many-function-args
            btn_delete.clicked.connect(self.onProjectDeleteButtonClicked(self.projectsTable, count)) # pylint: disable=too-many-function-args

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



    @select_table_row
    def onProjectSyncButtonClicked(self, is_toggled):
        # TODO check if project already saved
        assert self.current_cloud_project is not None

        if self.current_cloud_project.local_dir:
            self.ask_sync_project()
        else:
            reply = self.cloud_network_manager.get_files(self.current_cloud_project.id)
            reply.finished.connect(self.onCheckoutGetFilesListFinished(reply)) # pylint: disable=no-value-for-parameter

        # if there is saved location for this project id #
        #   download all the files #
        #   if project is the current one: #
        #       reload the project #
        # else
        #   if the cloud project is not empty
        #       ask for path that is empty dir
        #       download the project there
        #   else
        #       ask for path #
        #    
        #       if path contains .qgs file: #
        #           assert single .qgs file #
        #           upload all the files #
        # 
        # 
        #   save the project location #
        #
        # ask should that project be opened

        pass

    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onCheckoutGetFilesListFinished(self, reply, payload):
        assert self.current_cloud_project is not None

        if reply.error() != QNetworkReply.NoError or payload is None:
            QMessageBox.warning(self.iface.mainWidnow(), self.tr('Synchronization failed'), self.tr("Obtaining project files list failed: %1").arg(QFieldCloudNetworkManager.error_reason(reply)))
            return
        
        # cloud project is empty, you can upload a local project into it
        if len(payload) == 0:
            dir_path = None

            while dir_path is None:
                dir_path = QFileDialog.getExistingDirectory(self, "Upload local project to QFieldCloud", "/home/suricactus")

                if dir_path == '':
                    return

                # not the most efficient scaninning twice the whole file tree for .qgs and .qgz, but at least readable
                if len(glob.glob("{}/**/*.qgs".format(dir_path))) > 1 or len(glob.glob("{}/**/*.qgz".format(dir_path))) > 1:
                    QMessageBox.warning(None, self.tr('Multiple QGIS projects'), self.tr('When QFieldCloud project has no remote files, the local checkout directory may contains no more than 1 QGIS project.'))
                    dir_path = None
                    continue

                break

            self.current_cloud_project.update_data({'local_dir': dir_path})
            # TODO upload the project

        # cloud project exists and has files in it, so checkout in an empty dir
        else:
            dir_path = None

            while dir_path is None:
                dir_path = QFileDialog.getExistingDirectory(self, "Save QFieldCloud project at", "/home/suricactus")

                if dir_path == '':
                    return

                if len(os.listdir(dir_path)) > 0:
                    QMessageBox.warning(None, self.tr('QFieldSync checkout requires empty directory'), self.tr('When QFieldCloud project contains remote files the checkout destination needs to be an empty directory.'))
                    dir_path = None
                    continue

                break

            self.current_cloud_project.update_data({'local_dir': dir_path})
            # TODO download project


    @select_table_row
    def onProjectDeleteButtonClicked(self, is_toggled):
        self.projectsStackGroup.setEnabled(False)

        reply = self.cloud_network_manager.delete_project(self.current_cloud_project.id)
        reply.finished.connect(self.onDeleteProjectReplyFinished(reply)) # pylint: disable=no-value-for-parameter


    @select_table_row
    def onProjectEditButtonClicked(self, is_toggled):
        self.showProjectForm()


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onDeleteProjectReplyFinished(self, reply, payload):
        self.projectsStackGroup.setEnabled(True)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Project delete failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

        self.getProjects()


    def onProjectsTableCellDoubleClicked(self, _row, _col):
        self.showProjectForm()


    def onCreateButtonClicked(self):
        self.projectsTable.clearSelection()
        self.showProjectForm()

    
    def showProjectForm(self):
        self.projectsStack.setCurrentWidget(self.projectsFormPage)

        self.projectOwnerComboBox.clear()
        self.projectOwnerComboBox.addItem(self.usernameLineEdit.text(), self.usernameLineEdit.text())
        self.projectFilesTree.clear()
        self.projectFilesGroup.setEnabled(False)
        self.projectFilesGroup.setCollapsed(True)

        if self.current_cloud_project is None:
            self.projectNameLineEdit.setText("")
            self.projectDescriptionTextEdit.setPlainText("")
            self.projectIsPrivateCheckBox.setChecked(True)
            self.projectLocalDirFileWidget.setFilePath("")
        else:
            self.projectNameLineEdit.setText(self.current_cloud_project.name)
            self.projectDescriptionTextEdit.setPlainText(self.current_cloud_project.description)
            self.projectIsPrivateCheckBox.setChecked(self.current_cloud_project.is_private)
            self.projectLocalDirFileWidget.setFilePath(self.current_cloud_project.local_dir)

            index = self.projectOwnerComboBox.findData(self.current_cloud_project.owner)
            
            if index == -1:
                self.projectOwnerComboBox.insertItem(0, self.current_cloud_project.owner, self.current_cloud_project.owner)
                self.projectOwnerComboBox.setCurrentIndex(0)

            reply = self.cloud_network_manager.get_files(self.current_cloud_project.id)
            reply.finished.connect(self.onGetFilesFinished(reply)) # pylint: disable=no-value-for-parameter


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onGetFilesFinished(self, reply, payload):
        self.projectFilesGroup.setEnabled(True)
        self.projectFilesGroup.setCollapsed(False)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Obtaining project files list failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

        for file_obj in payload:
            file_item = QTreeWidgetItem(file_obj)
            
            file_item.setText(0, file_obj['name'])
            file_item.setText(1, str(file_obj['size']))
            file_item.setTextAlignment(1, Qt.AlignRight)
            file_item.setText(2, file_obj['versions'][-1]['created_at'])

            for version_idx, version_obj in enumerate(file_obj['versions'], 1):
                version_item = QTreeWidgetItem(version_obj)
                
                version_item.setText(0, 'Version {}'.format(version_idx))
                version_item.setText(1, str(version_obj['size']))
                version_item.setTextAlignment(1, Qt.AlignRight)
                version_item.setText(2, version_obj['created_at'])

                file_item.addChild(version_item)

            self.projectFilesTree.addTopLevelItem(file_item)


    def onBackButtonClicked(self):
        self.projectsStack.setCurrentWidget(self.projectsListPage)


    def onSubmitButtonClicked(self):
        cloud_project_data = {
            "name": self.projectNameLineEdit.text(),
            "description": self.projectDescriptionTextEdit.toPlainText(),
            "owner": self.projectOwnerComboBox.currentData(),
            "private": self.projectIsPrivateCheckBox.isChecked(),
            "local_dir": self.projectLocalDirFileWidget.filePath()
        }

        self.projectsFormPage.setEnabled(False)
        self.projectsFeedbackLabel.setVisible(True)

        if self.current_cloud_project is None:
            self.projectsFeedbackLabel.setText(self.tr("Creating project…"))
            reply = self.cloud_network_manager.create_project(
                cloud_project_data['name'], 
                cloud_project_data['owner'], 
                cloud_project_data['description'], 
                cloud_project_data['private'])
            reply.finished.connect(self.onCreateProjectFinished(reply, local_dir=cloud_project_data['local_dir'])) # pylint: disable=no-value-for-parameter
        else:
            self.current_cloud_project.update_data(cloud_project_data)
            self.projectsFeedbackLabel.setText(self.tr("Updating project…"))

            reply = self.cloud_network_manager.update_project(
                self.current_cloud_project.id, 
                self.current_cloud_project.name, 
                self.current_cloud_project.owner, 
                self.current_cloud_project.description, 
                self.current_cloud_project.is_private)
            reply.finished.connect(self.onUpdateProjectFinished(reply)) # pylint: disable=no-value-for-parameter


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onCreateProjectFinished(self, reply, payload, local_dir=None):
        self.projectsFormPage.setEnabled(True)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Project create failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

        # save `local_dir` configuration permanently, `CloudProject` constructor does this for free
        _project = CloudProject({
            **payload,
            'local_dir': local_dir,
        })

        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.projectsFeedbackLabel.setVisible(False)

        self.getProjects()


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onUpdateProjectFinished(self, reply, payload):
        self.projectsFormPage.setEnabled(True)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Project update failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.projectsFeedbackLabel.setVisible(False)

        self.getProjects()


    def onProjectsTableSelectionChanged(self, _new_selection, _old_selection):
        if self.projectsTable.selectionModel().hasSelection():
            row_idx = self.projectsTable.currentRow()
            self.current_cloud_project = self.projectsTable.item(row_idx, 0).data(Qt.UserRole)
        else:
            self.current_cloud_project = None


    # TODO move this to a separate class
    def ask_sync_project(self):
        assert self.current_cloud_project is not None, 'No project to download selected'
        assert self.current_cloud_project.local_dir, 'Cannot download a project without `local_dir` properly set'

        dialog_result = QMessageBox.question(
            self, 
            self.tr('Replace QFieldCloud files'), 
            self.tr('Would you like to replace remote QFieldCloud files with the version available locally?'), 
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, 
            QMessageBox.No)

        if dialog_result == QDialogButtonBox.Yes:
            self.sync_project(replace_remote_files=True)
        elif dialog_result == QDialogButtonBox.No:
            self.sync_project(replace_remote_files=False)
        else:
            return


    def sync_project(self, replace_remote_files: bool) -> None:
        assert self.current_cloud_project is not None, 'No project to sync selected'
        assert self.project_transfer is None, 'There is a project currently uploading'

        self.project_transfer = ProjectTransferrer(self.cloud_network_manager, self.current_cloud_project, ProjectTransferType.Sync)

        self.transfer_dialog = QFieldCloudTransferDialog(self.project_transfer, self)
        self.transfer_dialog.rejected.connect(self.on_transfer_dialog_rejected)
        self.transfer_dialog.accepted.connect(self.on_transfer_dialog_accepted)
        self.transfer_dialog.open()
        
        self.project_transfer.sync()


    def on_transfer_dialog_rejected(self):
        self.project_transfer.abort_requests()
        self.transfer_dialog.close()
        self.project_transfer = None
        self.project_download_transfer = None
        self.transfer_dialog = None


    def on_transfer_dialog_accepted(self):
        QgsProject().instance().reloadAllLayers()

        self.transfer_dialog.close()
        self.project_transfer = None
        self.project_download_transfer = None
        self.transfer_dialog = None


        # replace_all = False

        # for path in Path(self.temp_dir.path()).glob('**/*'):
        #     dest_path = Path(self.cloud_project.local_dir + '/' + str(path.relative_to(self.temp_dir.path())))

        #     if dest_path.exists() and replace_all != True:
        #         result = QMessageBox.question(
        #             self,
        #             self.tr('Replace local file'), 
        #             self.tr('Would you like to replace file "%1" with its cloud version?'), 
        #             QMessageBox.Yes | QMessageBox.YesToAll | QMessageBox.No | QMessageBox.NoToAll,
        #             QMessageBox.NoToAll)

        #     else:
        #         shutil.copy(path, dest_path)

