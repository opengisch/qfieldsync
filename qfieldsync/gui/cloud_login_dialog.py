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
from typing import Callable

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QMainWindow,
    QWidget,
)
from qgis.PyQt.uic import loadUiType

from qfieldsync.core import Preferences
from qfieldsync.core.cloud_api import CloudNetworkAccessManager

CloudLoginDialogUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/cloud_login_dialog.ui")
)


class CloudLoginDialog(QDialog, CloudLoginDialogUi):
    instance = None

    @staticmethod
    def show_auth_dialog(
        network_manager: CloudNetworkAccessManager,
        accepted_cb: Callable = None,
        rejected_cb: Callable = None,
        parent: QWidget = None,
    ):
        if CloudLoginDialog.instance:
            CloudLoginDialog.instance.show()
            CloudLoginDialog.instance.raise_()
            CloudLoginDialog.instance.activateWindow()
            return CloudLoginDialog.instance

        CloudLoginDialog.instance = CloudLoginDialog(network_manager, parent)
        CloudLoginDialog.instance.authenticate()

        if accepted_cb:
            CloudLoginDialog.instance.accepted.connect(accepted_cb)
        if rejected_cb:
            CloudLoginDialog.instance.rejected.connect(rejected_cb)

        def on_finished(result):
            CloudLoginDialog.instance = None

        CloudLoginDialog.instance.finished.connect(on_finished)

        return CloudLoginDialog.instance

    def __init__(
        self, network_manager: CloudNetworkAccessManager, parent: QWidget = None
    ) -> None:
        """Constructor."""
        super(CloudLoginDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.preferences = Preferences()
        self.network_manager = network_manager

        self.buttonBox.button(QDialogButtonBox.Ok).setText(self.tr("Sign In"))
        self.buttonBox.button(QDialogButtonBox.Ok).clicked.connect(
            self.on_login_button_clicked
        )
        self.buttonBox.button(QDialogButtonBox.Cancel).clicked.connect(
            self.on_cancel_button_clicked
        )

        self.serverUrlLabel.setVisible(False)
        self.serverUrlCmb.setVisible(False)
        for server_url in self.network_manager.server_urls():
            self.serverUrlCmb.addItem(server_url)

        cfg = self.network_manager.auth()
        remember_me = self.preferences.value("qfieldCloudRememberMe")

        self.serverUrlCmb.setCurrentText(cfg.uri() or self.network_manager.url)
        self.usernameLineEdit.setText(cfg.config("username"))
        self.passwordLineEdit.setText(cfg.config("password"))
        self.rememberMeCheckBox.setChecked(remember_me)

        self.network_manager.login_finished.connect(self.on_login_finished)

        self.qfieldCloudIcon.setAlignment(Qt.AlignHCenter)
        self.qfieldCloudIcon.setPixmap(
            QPixmap(
                os.path.join(
                    os.path.dirname(__file__), "../resources/qfieldcloud_logo.png"
                )
            )
        )
        self.qfieldCloudIcon.setMinimumSize(175, 180)
        self.qfieldCloudIcon.mouseDoubleClickEvent = (
            lambda event: self.toggle_server_url_visibility()
        )
        self.rejected.connect(self.on_rejected)
        self.hide()

    def on_rejected(self) -> None:
        QApplication.restoreOverrideCursor()
        if self.parent():
            self.parent().setEnabled(True)
            self.setEnabled(True)

    def toggle_server_url_visibility(self) -> None:
        self.serverUrlLabel.setVisible(not self.serverUrlLabel.isVisible())
        self.serverUrlCmb.setVisible(not self.serverUrlCmb.isVisible())

    def authenticate(self) -> None:
        self.usernameLineEdit.setEnabled(True)
        self.passwordLineEdit.setEnabled(True)
        self.rememberMeCheckBox.setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)

        if self.parent() and not isinstance(self.parent(), QMainWindow):
            self.parent().setEnabled(False)
            self.setEnabled(True)

        cfg = self.network_manager.auth()

        if cfg.config("token"):
            self.usernameLineEdit.setEnabled(False)
            self.passwordLineEdit.setEnabled(False)
            self.rememberMeCheckBox.setEnabled(False)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

            self.network_manager.set_url(cfg.uri())
            self.network_manager.set_auth(self.network_manager.url, token="")
            # don't trust the password, just login once again
            self.network_manager.login(cfg.config("username"), cfg.config("password"))

        if not cfg.config("token") or not self.parent():
            self.show()
            self.raise_()
            self.activateWindow()

    def on_login_button_clicked(self) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)

        server_url = self.serverUrlCmb.currentText()
        username = self.usernameLineEdit.text()
        password = self.passwordLineEdit.text()
        remember_me = self.rememberMeCheckBox.isChecked()

        self.network_manager.set_auth(server_url, username=username, password=password)
        self.network_manager.set_url(server_url)
        self.network_manager.login(username, password)

        self.preferences.set_value("qfieldCloudRememberMe", remember_me)

    def on_login_finished(self) -> None:
        QApplication.restoreOverrideCursor()
        if self.parent():
            self.parent().setEnabled(True)
            self.setEnabled(True)

        if not self.network_manager.has_token():
            self.loginFeedbackLabel.setText(self.network_manager.get_last_login_error())
            self.loginFeedbackLabel.setVisible(True)
            self.usernameLineEdit.setEnabled(True)
            self.passwordLineEdit.setEnabled(True)
            self.rememberMeCheckBox.setEnabled(True)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
            return

        self.usernameLineEdit.setEnabled(False)
        self.passwordLineEdit.setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)
        self.done(QDialog.Accepted)

    def on_cancel_button_clicked(self):
        self.reject()
