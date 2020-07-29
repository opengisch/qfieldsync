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
from typing import Any, Dict

from qgis.PyQt.QtCore import Qt, pyqtSlot
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QToolButton,
    QTableWidgetItem,
    QWidget,
    QCheckBox,
    QHBoxLayout,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.core import QgsProject
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.project import ProjectConfiguration
from qfieldsync.core.preferences import Preferences
from qfieldsync.core.cloud_api import login, logout, create_project, ProjectUploader, get_error_reason, QFieldCloudNetworkManager
from qfieldsync.utils.cloud_utils import to_cloud_title


QFieldCloudDialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/qfield_cloud_dialog.ui'))




class QFieldCloudDialog(QDialog, QFieldCloudDialogUi):

    def __init__(self, iface, parent=None):
        """Constructor.
        """
        super(QFieldCloudDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.iface = iface
        self.preferences = Preferences()
        self.networkManager = QFieldCloudNetworkManager(parent)

        self.loginButton.clicked.connect(self.onLoginButtonClicked)
        self.logoutButton.clicked.connect(self.onLogoutButtonClicked)
        self.createButton.clicked.connect(self.onCreateButtonClicked)
        self.deleteButton.clicked.connect(self.onDeleteButtonClicked)
        self.refreshButton.clicked.connect(self.onRefreshButtonClicked)
        self.backButton.clicked.connect(self.onBackButtonClicked)
        self.submitButton.clicked.connect(self.onSubmitButtonClicked)

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

        self.usernameLineEdit.setEnabled(True)
        self.passwordLineEdit.setText("")
        self.passwordLineEdit.setEnabled(True)
        self.rememberMeCheckBox.setEnabled(True)
        self.loginButton.setEnabled(True)


    def onRefreshButtonClicked(self):
        self.getProjects()


    def getProjects(self):
        self.projectsStackGroup.setEnabled(False)
        self.projectsFeedbackLabel.setText("Loading...")
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
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignCenter)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.addWidget(btn_synchronize)
            btn_widget.setLayout(btn_layout)

            self.projectsTable.setItem(count, 0, item)
            self.projectsTable.setItem(count, 1, QTableWidgetItem(cloud_project.owner))
            self.projectsTable.setCellWidget(count, 2, cbx_widget)
            self.projectsTable.setItem(count, 3, QTableWidgetItem("TODO"))
            self.projectsTable.setCellWidget(count, 4, btn_widget)



        self.projectsTable.resizeColumnsToContents()
        self.projectsTable.sortByColumn(2, Qt.AscendingOrder)
        self.projectsTable.setSortingEnabled(True)


    def onDeleteButtonClicked(self):
        self.projectsStackGroup.setEnabled(False)

        reply = self.networkManager.delete_project(self.current_cloud_project.id)
        reply.finished.connect(self.onDeleteProjectReplyFinished(reply))


    @QFieldCloudNetworkManager.reply_wrapper
    @QFieldCloudNetworkManager.read_json
    def onDeleteProjectReplyFinished(self, reply, payload):
        self.projectsStackGroup.setEnabled(True)

        if reply.error() != QNetworkReply.NoError or payload is None:
            self.projectsFeedbackLabel.setText("Project delete failed: {}".format(QFieldCloudNetworkManager.error_reason(reply)))
            self.projectsFeedbackLabel.setVisible(True)
            return

        self.getProjects()


    def onCreateButtonClicked(self):
        self.projectsStack.setCurrentWidget(self.projectsFormPage)

        self.projectsTable.clearSelection()

        self.projectOwnerComboBox.addItem(self.usernameLineEdit.text())
        self.projectOwnerComboBox.setItemData(0, self.usernameLineEdit.text())


    def onBackButtonClicked(self):
        self.projectsStack.setCurrentWidget(self.projectsListPage)


    def onSubmitButtonClicked(self):
        cloud_project_data = {
            "name": self.projectNameLineEdit.text(),
            "description": self.projectDescriptionTextEdit.toPlainText(),
            "owner": self.projectOwnerComboBox.currentData(),
            "private": self.projectIsPrivateCheckBox.isChecked(),
        }

        if self.current_cloud_project is None:
            reply = self.networkManager.create_project(cloud_project_data['name'], cloud_project_data['owner'], cloud_project_data['description'], cloud_project_data['private'])
            reply.finished.connect(self.onCreateProjectFinished(reply))
        else:
            self.current_cloud_project.update_data(cloud_project_data)

            reply = self.networkManager.update_project(cloud_project_data['id'], cloud_project_data['name'], cloud_project_data['owner'], cloud_project_data['description'], cloud_project_data['private'])
            reply.finished.connect(self.onUpdateProjectFinished(reply))




    def onCreateProjectFinished(self, reply, payload):
        self.projectsStack.setCurrentWidget(self.projectsListPage)
        pass


    def onUpdateProjectFinished(self, reply, payload):
        self.projectsStack.setCurrentWidget(self.projectsListPage)
        pass

    def onProjectsTableSelectionChanged(self, new_selection, old_selection):
        self.current_cloud_project = self.projectsTable.currentItem().data(Qt.UserRole)

        print(old_selection, new_selection, self.projectsTable.currentItem(), self.current_cloud_project)

        self.editButton.setEnabled(self.current_cloud_project is not None)
        self.deleteButton.setEnabled(self.current_cloud_project is not None)




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