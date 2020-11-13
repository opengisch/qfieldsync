# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldCloudDialog
                                 A QGIS plugin
 Sync your projects to QField on android
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

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QWidget, QDialog
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.PyQt.uic import loadUiType

from qfieldsync.core import Preferences
from qfieldsync.core.cloud_api import CloudException, CloudNetworkAccessManager


CloudLoginDialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/cloud_login_dialog.ui'))


class CloudLoginDialog(QDialog, CloudLoginDialogUi):

    def __init__(self, network_manager: CloudNetworkAccessManager, parent: QWidget = None) -> None:
        """Constructor.
        """
        super(CloudLoginDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.preferences = Preferences()
        self.network_manager = network_manager

        self.loginButton.clicked.connect(self.on_login_button_clicked)
        self.cancelButton.clicked.connect(lambda: self.close())

        for server_url in self.network_manager.server_urls():
            self.serverUrlCmb.addItem(server_url)

        url, username, password = self.network_manager.auth()
        remember_me = self.preferences.value('qfieldCloudRememberMe')

        self.serverUrlCmb.setCurrentText(url or self.network_manager.url)
        self.usernameLineEdit.setText(username)
        self.passwordLineEdit.setText(password)
        self.rememberMeCheckBox.setChecked(remember_me)


    def authenticate(self) -> None:
        last_token = self.preferences.value('qfieldCloudLastToken')

        self.usernameLineEdit.setEnabled(True)
        self.passwordLineEdit.setEnabled(True)
        self.rememberMeCheckBox.setEnabled(True)
        self.loginButton.setEnabled(True)

        if self.parent():
            self.parent().setEnabled(False)
            self.setEnabled(True)

        if last_token:
            self.usernameLineEdit.setEnabled(False)
            self.passwordLineEdit.setEnabled(False)
            self.rememberMeCheckBox.setEnabled(False)
            self.loginButton.setEnabled(False)

            self.network_manager.set_token(last_token)

            reply = self.network_manager.get_user(last_token)
            reply.finished.connect(lambda: self.on_get_user_reply_finished(reply))
        else:
            self.show()


    def on_login_button_clicked(self) -> None:
        self.loginButton.setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)

        server_url = self.serverUrlCmb.currentText()
        username = self.usernameLineEdit.text()
        password = self.passwordLineEdit.text()

        self.network_manager.set_auth(server_url, username, password)
        self.network_manager.set_url(server_url)
        
        self.preferences.set_value('qfieldCloudRememberMe', self.rememberMeCheckBox.isChecked())

        reply = self.network_manager.login(username, password)
        reply.finished.connect(lambda: self.on_login_reply_finished(reply))


    def on_get_user_reply_finished(self, reply: QNetworkReply) -> None:
        if self.parent():
            self.parent().setEnabled(True)
            self.setEnabled(True)

        try:
            resp = CloudNetworkAccessManager.json_object(reply)
            self.network_manager.username = resp['username']
        except CloudException as err:
            self.preferences.set_value('qfieldCloudLastToken', '')
            self.network_manager.set_token('')
            
            self.loginFeedbackLabel.setText(self.tr('Token reuse failed: %1').format(str(err)))
            self.loginFeedbackLabel.setVisible(True)
            self.usernameLineEdit.setEnabled(True)
            self.passwordLineEdit.setEnabled(True)
            self.rememberMeCheckBox.setEnabled(True)
            self.loginButton.setEnabled(True)
            return

        self.network_manager.authenticated.emit()

        self.done(QDialog.Accepted)


    def on_login_reply_finished(self, reply: QNetworkReply) -> None:
        if self.parent():
            self.parent().setEnabled(True)
            self.setEnabled(True)

        try:
            payload = CloudNetworkAccessManager.json_object(reply)
        except CloudException as err:
            self.loginFeedbackLabel.setText(self.tr('Login failed: {}').format(str(err)))
            self.loginFeedbackLabel.setVisible(True)
            self.usernameLineEdit.setEnabled(True)
            self.passwordLineEdit.setEnabled(True)
            self.rememberMeCheckBox.setEnabled(True)
            self.loginButton.setEnabled(True)

            return

        self.network_manager.set_token(payload['token'])
        self.network_manager.username = payload['username']

        if self.rememberMeCheckBox.isChecked():
            self.preferences.set_value('qfieldCloudLastToken', payload['token'])

        self.usernameLineEdit.setEnabled(False)
        self.passwordLineEdit.setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)

        self.network_manager.authenticated.emit()

        self.done(QDialog.Accepted)
