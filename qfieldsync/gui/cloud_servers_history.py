"""
/***************************************************************************
                             -------------------
        begin                : 2026-07-09
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

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QListWidgetItem, QWidget
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.preferences import Preferences

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/cloud_servers_history.ui")
)


class CloudServerHistoryListWidget(QWidget, WidgetUi):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.preferences = Preferences()

        self.addButton.setIcon(QgsApplication.getThemeIcon("/symbologyAdd.svg"))
        self.addButton.clicked.connect(self._on_add_button_clicked)

        self.removeButton.setIcon(QgsApplication.getThemeIcon("/symbologyRemove.svg"))
        self.removeButton.setEnabled(False)
        self.removeButton.clicked.connect(self._on_remove_button_clicked)

        self.serverHistoryList.itemClicked.connect(
            lambda: self.removeButton.setEnabled(
                len(self.serverHistoryList.selectedItems()) > 0
            )
        )

        self.serverHistoryList.itemChanged.connect(self.save_server_history)

        self.load_server_history()

    def load_server_history(self) -> None:
        self.serverHistoryList.blockSignals(True)
        self.serverHistoryList.clear()

        history = self.preferences.value("qfieldCloudServerUrlsHistory") or []
        for url in history:
            item = QListWidgetItem(url)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.serverHistoryList.addItem(item)

        self.serverHistoryList.blockSignals(False)

    def _on_add_button_clicked(self) -> None:
        item = QListWidgetItem("")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        self.serverHistoryList.addItem(item)

        self.serverHistoryList.setCurrentItem(item)
        self.serverHistoryList.editItem(item)

    def _on_remove_button_clicked(self) -> None:
        current_item = self.serverHistoryList.currentItem()
        if not current_item:
            return

        row = self.serverHistoryList.row(current_item)
        self.serverHistoryList.takeItem(row)

        self.save_server_history()

    def save_server_history(self) -> None:
        urls = []
        for i in range(self.serverHistoryList.count()):
            url = self.serverHistoryList.item(i).text().strip()
            if url:
                urls.append(url)

        unique_urls = list(dict.fromkeys(urls))
        self.preferences.set_value("qfieldCloudServerUrlsHistory", unique_urls)
