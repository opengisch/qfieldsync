"""
/***************************************************************************
 StorageWidget
                                A QGIS plugin to
                           Sync your projects to QField
                             -------------------
        begin                : 2026-04-24
        git sha              : $Format:%H$
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

import os

from qgis.PyQt.QtWidgets import QWidget
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.cloud_api import CloudNetworkAccessManager, QfcError
from qfieldsync.utils.file_utils import filesizeformat10

StorageWidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/storage_widget.ui")
)


class StorageWidget(QWidget, StorageWidgetUi):
    WARNING_THRESHOLD = 0.8
    CRITICAL_THRESHOLD = 0.95

    NORMAL_COLOR = "#4a6fae"
    WARNING_COLOR = "#ffa500"
    CRITICAL_COLOR = "#c0392b"

    PROGRESSBAR_STYLESHEET = "QProgressBar {{ border: 1px solid palette(Mid); border-radius: 2px; }} QProgressBar::chunk {{ background-color: {}; }}"

    def __init__(
        self, network_manager: CloudNetworkAccessManager, parent: QWidget = None
    ) -> None:
        super().__init__(parent=parent)
        self.setupUi(self)

        self.progressBar.setMaximum(100)
        self.progressBar.setStyleSheet(
            self.PROGRESSBAR_STYLESHEET.format(self.NORMAL_COLOR)
        )

        self.network_manager = network_manager

        self._owner = ""
        self._active_storage_total_bytes = 0
        self._storage_used_bytes = 0
        self._storage_used_percent = 0.0
        self._storage_management_hyperlink = ""

    def set_owner(self, owner: str) -> None:
        self._owner = owner
        if self._owner:
            self.refresh()

    def owner(self) -> str:
        return self._owner

    def active_storage_total_bytes(self) -> int:
        return self._active_storage_total_bytes

    def storage_used_bytes(self) -> int:
        return self._storage_used_bytes

    def storage_used_percent(self) -> float:
        return self._storage_used_percent

    def storage_management_hyperlink(self) -> str:
        return self._storage_management_hyperlink

    def refresh(self) -> None:
        if self._owner:
            self.progressBar.setMaximum(0)
            self.usageLabel.setText(self.tr("Fetching storage details..."))

            reply = self.network_manager.get_subscription_information(self._owner)
            reply.finished.connect(
                lambda: self.on_get_subscription_information_finished(reply)
            )

    def on_get_subscription_information_finished(self, reply) -> None:
        try:
            subscription_information = self.network_manager.json_object(reply)
        except QfcError:
            subscription_information = {}

        self.progressBar.setMaximum(100)

        reply.deleteLater()

        self._active_storage_total_bytes = subscription_information.get(
            "active_storage_total_bytes", 0
        )
        self._storage_used_bytes = subscription_information.get("storage_used_bytes", 0)

        if self._active_storage_total_bytes > 0:
            self._storage_used_percent = (
                self._storage_used_bytes / self._active_storage_total_bytes
            )
        else:
            self._storage_used_percent = 0

        self.progressBar.setValue(int(self._storage_used_percent * 100))
        self.progressBar.setStyleSheet(
            self.PROGRESSBAR_STYLESHEET.format(
                self._get_progressbar_color(self._storage_used_percent)
            )
        )

        usage_label = self.tr("Used {} of {}").format(
            filesizeformat10(self._storage_used_bytes),
            filesizeformat10(self._active_storage_total_bytes),
        )
        if self._owner == self.network_manager.user_details.get("username"):
            self._storage_management_hyperlink = self._get_upgrade_link_url(
                subscription_information.get("plan_is_premium")
            )
            usage_label += " / <a href='{}'>{}</a>".format(
                self._storage_management_hyperlink,
                self._get_upgrade_link_label(self._storage_used_percent),
            )
        else:
            self._storage_management_hyperlink = ""

        if subscription_information:
            self.usageLabel.setText(usage_label)
        else:
            self.usageLabel.setText(self.tr("N/A"))

    def _get_progressbar_color(self, storage_used_percent: float) -> str:
        if storage_used_percent >= self.CRITICAL_THRESHOLD:
            return self.CRITICAL_COLOR
        elif storage_used_percent >= self.WARNING_THRESHOLD:
            return self.WARNING_COLOR
        else:
            return self.NORMAL_COLOR

    def _get_upgrade_link_label(self, storage_used_percent: float) -> str:
        if storage_used_percent >= self.CRITICAL_THRESHOLD:
            return self.tr("upgrade storage")
        else:
            return self.tr("manage storage")

    def _get_upgrade_link_url(self, is_premium: bool) -> str:
        if is_premium:
            return f"https://app.qfield.cloud/settings/{self._owner}/billing"
        else:
            return "https://app.qfield.cloud/plans"
