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
from typing import Any, Dict

from qgis.PyQt.QtCore import Qt, QItemSelectionModel, pyqtSlot
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QToolButton,
    QTableWidgetItem,
    QWidget,
    QCheckBox,
    QHBoxLayout,
    QTreeWidgetItem,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.core import QgsProject
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.project import ProjectConfiguration
from qfieldsync.core.preferences import Preferences
from qfieldsync.core.cloud_api import QFieldCloudNetworkManager
from qfieldsync.utils.cloud_utils import to_cloud_title


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

    def __init__(self, iface, parent=None):
        """Constructor.
        """
        super(QFieldCloudDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.iface = iface
        self.preferences = Preferences()
        self.networkManager = QFieldCloudNetworkManager(parent)
        self.current_cloud_project = None

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

        username = self.usernameLineEdit.text()
        password = self.passwordLineEdit.text()

        reply = self.networkManager.login(username, password)
        reply.finished.connect(self.onLoginReplyFinished(reply))


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

        self.networkManager.set_token(payload['token'])

        self.usernameLineEdit.setEnabled(False)
        self.passwordLineEdit.setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)
        self.loginButton.setEnabled(False)
        self.logoutButton.setEnabled(True)

        self.getProjects()


    def onLogoutButtonClicked(self):
        self.logoutButton.setEnabled(False)
        self.loginFeedbackLabel.setVisible(False)

        reply = self.networkManager.logout()
        reply.finished.connect(self.onLogoutReplyFinished(reply))


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onLogoutReplyFinished(self, reply, payload):
        if reply.error() != QNetworkReply.NoError or payload is None:
            self.loginFeedbackLabel.setText("Logout failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.loginFeedbackLabel.setVisible(True)
            self.logoutButton.setEnabled(True)
            return

        self.networkManager.set_token("")
        self.projectsTable.setRowCount(0)
        self.projectsStack.setCurrentWidget(self.projectsListPage)
        self.projectsStackGroup.setEnabled(False)

        self.usernameLineEdit.setEnabled(True)
        self.passwordLineEdit.setText("")
        self.passwordLineEdit.setEnabled(True)
        self.rememberMeCheckBox.setEnabled(True)
        self.loginButton.setEnabled(True)


    def onRefreshButtonClicked(self):
        self.getProjects()


    def getProjects(self):
        self.projectsStackGroup.setEnabled(False)
        self.projectsFeedbackLabel.setText("Loading…")
        self.projectsFeedbackLabel.setVisible(True)

        reply = self.networkManager.get_projects()

        reply.finished.connect(self.onGetProjectsReplyFinished(reply))


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onGetProjectsReplyFinished(self, reply, payload):
        self.projectsStackGroup.setEnabled(True)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Project refresh failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

        self.projectsFeedbackLabel.setText("")
        self.projectsFeedbackLabel.setVisible(False)

        self.projectsTable.setRowCount(0)
        self.projectsTable.setSortingEnabled(False)

        for project in payload:
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

            btn_synchronize = QToolButton()
            btn_synchronize.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/refresh.png')))
            btn_edit = QToolButton()
            btn_edit.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/refresh.png')))
            btn_delete = QToolButton()
            btn_delete.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/refresh.png')))
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignCenter)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addWidget(btn_synchronize)
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_delete)
            btn_widget.setLayout(btn_layout)

            btn_synchronize.clicked.connect(self.onProjectSynchronizeButtonClicked(self.projectsTable, count))
            btn_edit.clicked.connect(self.onProjectEditButtonClicked(self.projectsTable, count))
            btn_delete.clicked.connect(self.onProjectDeleteButtonClicked(self.projectsTable, count))

            self.projectsTable.setItem(count, 0, item)
            self.projectsTable.setItem(count, 1, QTableWidgetItem(cloud_project.owner))
            self.projectsTable.setCellWidget(count, 2, cbx_widget)
            self.projectsTable.setCellWidget(count, 3, btn_widget)



        self.projectsTable.resizeColumnsToContents()
        self.projectsTable.sortByColumn(2, Qt.AscendingOrder)
        self.projectsTable.setSortingEnabled(True)


    @select_table_row
    def onProjectSynchronizeButtonClicked(self, is_toggled):
        # TODO check if project already saved
        # if there is saved location for this project id
        #   download all the files
        #   if project is the current one:
        #       reload the project
        # else
        #   if the cloud project is not empty
        #       ask for path that is empty dir
        #       download the project there
        #   else
        #       ask for path
        #    
        #       if path contains .qgs file:
        #           assert single .qgs file
        #           upload all the files
        # 
        # 
        #   save the project location
        # ask should that project be opened

        pass


    @select_table_row
    def onProjectDeleteButtonClicked(self, is_toggled):
        self.projectsStackGroup.setEnabled(False)

        reply = self.networkManager.delete_project(self.current_cloud_project.id)
        reply.finished.connect(self.onDeleteProjectReplyFinished(reply))


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
        else:
            self.projectNameLineEdit.setText(self.current_cloud_project.name)
            self.projectDescriptionTextEdit.setPlainText(self.current_cloud_project.description)
            self.projectIsPrivateCheckBox.setChecked(self.current_cloud_project.is_private)

            index = self.projectOwnerComboBox.findData(self.current_cloud_project.owner)
            
            if index == -1:
                self.projectOwnerComboBox.insertItem(0, self.current_cloud_project.owner, self.current_cloud_project.owner)
                self.projectOwnerComboBox.setCurrentIndex(0)

            reply = self.networkManager.get_files(self.current_cloud_project.id)
            reply.finished.connect(self.onGetFilesFinished(reply))


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
        }

        self.projectsFormPage.setEnabled(False)
        self.projectsFeedbackLabel.setVisible(True)

        if self.current_cloud_project is None:
            self.projectsFeedbackLabel.setText(self.tr("Creating project…"))
            reply = self.networkManager.create_project(
                cloud_project_data['name'], 
                cloud_project_data['owner'], 
                cloud_project_data['description'], 
                cloud_project_data['private'])
            reply.finished.connect(self.onCreateProjectFinished(reply))
        else:
            self.current_cloud_project.update_data(cloud_project_data)
            self.projectsFeedbackLabel.setText(self.tr("Updating project…"))

            reply = self.networkManager.update_project(
                self.current_cloud_project.id, 
                self.current_cloud_project.name, 
                self.current_cloud_project.owner, 
                self.current_cloud_project.description, 
                self.current_cloud_project.is_private)
            reply.finished.connect(self.onUpdateProjectFinished(reply))


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onCreateProjectFinished(self, reply, payload):
        self.projectsFormPage.setEnabled(True)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Project create failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

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


class CloudProject:

    def __init__(self, project_data):
        """Constructor.
        """
        self._data = project_data

    def update_data(self, new_project_data):
        self._data = {**self._data, **new_project_data}

    @property
    def id(self):
        return self._data['id']


    @property
    def name(self):
        return self._data['name']


    @property
    def owner(self):
        return self._data['owner']


    @property
    def description(self):
        return self._data['description']


    @property
    def is_private(self):
        return self._data['private']


    @property
    def created_at(self):
        return self._data['created_at']


    @property
    def updated_at(self):
        return self._data['updated_at']