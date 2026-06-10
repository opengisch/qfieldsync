"""
/***************************************************************************
 QFieldSync
                              -------------------
        begin                : 2026
        copyright            : (C) 2026 by OPENGIS.ch
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

from typing import Any

from qgis.core import Qgis, QgsAuthMethodConfig
from qgis.PyQt.QtCore import (
    QObject,
)
from qgis.PyQt.QtNetwork import (
    QNetworkReply,
)
from qgis.PyQt.QtWidgets import QPushButton
from qgis.testing import start_app, unittest

from qfieldsync.gui.cloud_login_dialog import (
    QGIS_MIN_VERSION_FOR_OAUTH2_EXTRA_TOKENS,
    CloudLoginDialog,
)

start_app()


class DummySignal:
    def connect(self, _callback):
        pass


class DummyReply(QNetworkReply):
    finished = DummySignal()


class DummyNetworkManager(QObject):
    url = "https://dummy.qfield.cloud/"
    login_finished = DummySignal()

    def __init__(self):
        super().__init__()
        self.reply = DummyReply()

    def auth(self) -> QgsAuthMethodConfig:
        return QgsAuthMethodConfig()

    def get_auth_capabilities(self) -> QNetworkReply:
        return self.reply

    def get_remote_resource(self, _resource_url: str) -> QNetworkReply:
        return DummyReply()

    def json_array(self, _reply: QNetworkReply) -> list[Any]:
        return [
            {
                "type": "oauth2",
                "id": "sso",
                "name": "SSO",
                "styles": {"light": {}, "dark": {}},
            }
        ]

    def server_urls(self) -> list[Any]:
        return [self.url]

    def set_url(self, server_url: str) -> None:
        self.url = server_url


@unittest.skipIf(
    Qgis.versionInt() < QGIS_MIN_VERSION_FOR_OAUTH2_EXTRA_TOKENS,
    "OAuth2 SSO requires QGIS 3.44+",
)
class CloudLoginDialogTest(unittest.TestCase):
    def test_sso_only_provider_button_is_enabled(self):
        dialog = CloudLoginDialog(DummyNetworkManager())

        dialog.on_fetch_auth_methods_finished()

        sso_button = None
        for buttons in dialog.findChildren(QPushButton):
            if buttons.text() == "SSO":
                sso_button = buttons
                break

        self.assertIsNotNone(sso_button)
        self.assertTrue(sso_button.isEnabledTo(dialog))
