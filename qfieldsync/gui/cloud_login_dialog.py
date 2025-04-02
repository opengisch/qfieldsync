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
from functools import partial
from typing import Callable, Optional
from urllib.parse import urlparse

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QCursor, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QMainWindow,
    QPushButton,
    QWidget,
)
from qgis.PyQt.uic import loadUiType

from qfieldsync.core import Preferences
from qfieldsync.core.cloud_api import (
    CloudAuthMethod,
    CloudException,
    CloudNetworkAccessManager,
    build_oauth2_auth_config_from_cloud_method,
)

CloudLoginDialogUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/cloud_login_dialog.ui")
)


class CloudLoginDialog(QDialog, CloudLoginDialogUi):
    instance = None

    _fetch_auth_methods_timer: QTimer = QTimer()

    _credentials_auth_method: Optional[dict] = None
    _sso_auth_methods: Optional[dict] = {}

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

        self.buttonBox.setEnabled(False)
        self.buttonBox.hide()

        self._fetch_auth_methods_timer.setInterval(750)
        self._fetch_auth_methods_timer.setSingleShot(True)
        self._fetch_auth_methods_timer.timeout.connect(
            self.fetch_server_auth_capabilities
        )

        self.signInUsernameButton.clicked.connect(
            self.on_credentials_login_button_clicked
        )

        self.loginFormGroup.setVisible(False)
        self.set_login_groupbox_visibility(self.signInUsernameGroupBox, False)

        for server_url in self.network_manager.server_urls():
            self.serverUrlCmb.addItem(server_url)

        cfg = self.network_manager.auth()
        self.serverUrlCmb.setCurrentText(cfg.uri() or self.network_manager.url)
        self.serverUrlCmb.editTextChanged.connect(self.on_server_url_edit_text_changed)

        if self.network_manager == CloudAuthMethod.CREDENTIALS:
            self.usernameLineEdit.setText(cfg.config("username"))
            self.passwordLineEdit.setText(cfg.config("password"))

        remember_me = self.preferences.value("qfieldCloudRememberMe")
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

        self.fetch_server_auth_capabilities()

    def on_rejected(self) -> None:
        QApplication.restoreOverrideCursor()
        if self.parent():
            self.parent().setEnabled(True)
            self.setEnabled(True)

    def toggle_server_url_visibility(self) -> None:
        self.loginFormGroup.setVisible(not self.loginFormGroup.isVisible())

    def clear_login_widgets(self) -> None:
        self.set_login_groupbox_visibility(self.signInUsernameGroupBox, False)

        # clear sso login buttons layout
        while self.oauth2_buttons_layout.count():
            child = self.oauth2_buttons_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def set_login_groupbox_visibility(self, group_box: QGroupBox, visible: bool):
        group_box.setEnabled(visible)

    def fetch_server_auth_capabilities(self) -> None:
        """
        Fetches the provided server authentication method capabilities.
        """
        self.clear_login_widgets()
        self.network_manager.set_url(self.serverUrlCmb.currentText())
        self.auth_methods_reply = self.network_manager.get_auth_capabilities()
        self.auth_methods_reply.finished.connect(self.on_fetch_auth_methods_finished)

    def on_fetch_auth_methods_finished(self) -> None:
        try:
            auth_methods = self.network_manager.json_array(self.auth_methods_reply)
        except CloudException:
            self.set_login_groupbox_visibility(self.signInUsernameGroupBox, True)
            return

        self.clear_login_widgets()

        for auth_method in auth_methods:
            # credentials login: enabled static groupbox.
            if auth_method["id"] == "credentials":
                self._credentials_auth_method = auth_method
                self.set_login_groupbox_visibility(self.signInUsernameGroupBox, True)
                continue

            # sso provider: dynamically generate button to login.
            self._sso_auth_methods[auth_method["id"]] = auth_method
            login_button = QPushButton(
                self.tr("Sign In with {provider}").format(provider=auth_method["name"])
            )
            login_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

            # if google auth available, we need to display the logo for legal reasons.
            if auth_method["id"] == "google":
                login_button.setIcon(
                    QIcon(
                        os.path.join(
                            os.path.dirname(__file__), "../resources/google.svg"
                        )
                    )
                )

            login_button.clicked.connect(
                partial(self.on_login_with_sso_provider_button_clicked, auth_method)
            )
            self.oauth2_buttons_layout.addWidget(login_button)

    def authenticate(self) -> None:
        self.usernameLineEdit.setEnabled(True)
        self.passwordLineEdit.setEnabled(True)
        self.rememberMeCheckBox.setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)

        if self.parent() and not isinstance(self.parent(), QMainWindow):
            self.parent().setEnabled(False)
            self.setEnabled(True)

        cfg = self.network_manager.auth()

        auth_method = self.network_manager.auth_method

        if auth_method == CloudAuthMethod.CREDENTIALS:
            self.usernameLineEdit.setEnabled(False)
            self.passwordLineEdit.setEnabled(False)
            self.rememberMeCheckBox.setEnabled(False)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

            self.network_manager.set_url(cfg.uri())
            self.network_manager.set_auth(self.network_manager.url, token="")
            # don't trust the password, just login once again
            self.network_manager.login_with_credentials(
                cfg.config("username"), cfg.config("password")
            )

        elif auth_method == CloudAuthMethod.SSO:
            self.network_manager.set_url(cfg.uri())
            self.network_manager.login_with_sso()

        elif not cfg.config("token") or not self.parent():
            self.show()
            self.raise_()
            self.activateWindow()

    def on_server_url_edit_text_changed(self) -> None:
        server_url = self.serverUrlCmb.currentText()
        result = urlparse(server_url)
        if all([result.scheme, result.netloc]):
            if self._fetch_auth_methods_timer.isActive():
                return
            self._fetch_auth_methods_timer.start()

    def on_credentials_login_button_clicked(self) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.rememberMeCheckBox.setEnabled(False)

        server_url = self.serverUrlCmb.currentText()
        username = self.usernameLineEdit.text()
        password = self.passwordLineEdit.text()
        remember_me = self.rememberMeCheckBox.isChecked()

        self.network_manager.set_auth(server_url, username=username, password=password)
        self.network_manager.set_url(server_url)
        self.network_manager.login_with_credentials(username, password)

        self.preferences.set_value("qfieldCloudRememberMe", remember_me)

    def on_login_finished(self) -> None:
        QApplication.restoreOverrideCursor()
        if self.parent():
            self.parent().setEnabled(True)
            self.setEnabled(True)

        if not self.network_manager.is_authenticated():
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

    def on_login_with_sso_provider_button_clicked(self, provider_data: dict) -> None:
        server_url = self.serverUrlCmb.currentText()
        auth_config = build_oauth2_auth_config_from_cloud_method(
            provider_data,
            server_url,
            "qfieldcloud-sso",
        )
        self.network_manager.set_url(server_url)
        self.network_manager.set_sso_auth_config(auth_config)
        self.network_manager.login_with_sso()

    def on_cancel_button_clicked(self):
        self.reject()
