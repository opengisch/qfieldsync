# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AttachmentNamingTableWidget
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2023-02-26
        git sha              : $Format:%H$
        copyright            : (C) 2023 by OPENGIS.ch
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
from pathlib import Path
from typing import Dict, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QTreeWidgetItem, QWidget
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.preferences import Preferences
from qfieldsync.utils.file_utils import (
    DirectoryTreeDict,
    DirectoryTreeType,
    path_to_dict,
)
from qfieldsync.utils.qt_utils import build_file_tree_widget_from_dict

LayersConfigWidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/dirs_to_copy_widget.ui")
)

DirsToCopySettings = Dict[str, bool]


class DirsToCopyWidget(QWidget, LayersConfigWidgetUi):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)

        self.path: Optional[Path] = None
        self.preferences: Preferences = Preferences()
        self.refreshButton.clicked.connect(lambda: self.refresh_tree())
        self.selectAllButton.clicked.connect(
            lambda: self._set_checked_state_recursively(True)
        )
        self.deselectAllButton.clicked.connect(
            lambda: self._set_checked_state_recursively(False)
        )

    def refresh_tree(self):
        if self.path is None:
            return

        if not self.path.is_dir():
            return

        dirs_to_copy = self.load_settings()

        self.dirsTreeWidget.clear()

        def build_item_cb(item: QTreeWidgetItem, node: DirectoryTreeDict):
            relative_path = node["path"].relative_to(self.path)
            str_path = str(relative_path)

            # TODO decide whether or not to take into account the attachment_dirs into account
            # attachment_dirs = self.preferences.value("attachmentDirs") # TODO move this in the outer scope
            # matches = False

            # for attachment_dir in attachment_dirs:
            #     if str_path.startswith(attachment_dir):
            #         matches = True

            # if not matches:
            #     return False

            check_state = (
                Qt.Checked if dirs_to_copy.get(str_path, True) else Qt.Unchecked
            )

            item.setCheckState(0, check_state)
            item.setExpanded(True)
            item.setData(0, Qt.UserRole, str_path)
            item.setToolTip(0, str(node["path"].absolute()))
            item.setFlags(
                item.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsSelectable
                | Qt.ItemIsAutoTristate
            )

        root_item = self.dirsTreeWidget.invisibleRootItem()
        dict_paths = path_to_dict(self.path, dirs_only=True)

        if dict_paths["type"] == DirectoryTreeType.DIRECTORY:
            for subnode in dict_paths["content"]:
                build_file_tree_widget_from_dict(
                    root_item,
                    subnode,
                    build_item_cb,
                )

    def dirs_to_copy(self) -> DirsToCopySettings:
        def extract_dirs_data(root_item: QTreeWidgetItem) -> Dict[str, bool]:
            data = {}
            for i in range(root_item.childCount()):
                item = root_item.child(i)
                relative_path = item.data(0, Qt.UserRole)
                is_checked = item.checkState(0) == Qt.Checked
                data[relative_path] = is_checked

                if item.childCount() > 0:
                    data.update(extract_dirs_data(item))

            return data

        dirs_to_copy = extract_dirs_data(self.dirsTreeWidget.invisibleRootItem())

        return dirs_to_copy

    def set_path(self, path: str) -> None:
        if path.strip():
            self.path = Path(path)
        else:
            self.path = None

        is_enabled = bool(self.path and self.path.is_dir())
        self.refreshButton.setEnabled(is_enabled)

    def load_settings(self) -> DirsToCopySettings:
        return self.preferences.value("dirsToCopy")

    def save_settings(self) -> None:
        self.preferences.set_value("dirsToCopy", self.dirs_to_copy())

    def _set_checked_state_recursively(self, checked: bool) -> None:
        def set_checked_state(root_item: QTreeWidgetItem) -> Dict[str, bool]:
            for i in range(root_item.childCount()):
                item = root_item.child(i)
                checked_state = Qt.Checked if checked else Qt.Unchecked
                print(i, checked_state)
                item.setCheckState(i, checked_state)

                if item.childCount() > 0:
                    set_checked_state(item)

        set_checked_state(self.dirsTreeWidget.invisibleRootItem())
