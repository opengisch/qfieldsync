# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSyncDialog
                                 A QGIS plugin
 Sync your projects to QField on android
                             -------------------
        begin                : 2015-05-20
        git sha              : $Format:%H$
        copyright            : (C) 2015 by OPENGIS.ch
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

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QDir, Qt
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTreeWidgetItem
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.preferences import Preferences
from qfieldsync.libqfieldsync import ProjectConfiguration
from qfieldsync.libqfieldsync.utils.exceptions import NoProjectFoundError
from qfieldsync.libqfieldsync.utils.file_utils import (
    copy_attachments,
    get_project_in_folder,
    import_file_checksum,
)
from qfieldsync.libqfieldsync.utils.qgis import make_temp_qgis_file, open_project
from qfieldsync.utils.file_utils import (
    DirectoryTreeDict,
    DirectoryTreeType,
    path_to_dict,
)
from qfieldsync.utils.qgis_utils import import_checksums_of_project
from qfieldsync.utils.qt_utils import (
    build_file_tree_widget_from_dict,
    make_folder_selector,
)

DialogUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/synchronize_dialog.ui")
)


class SynchronizeDialog(QDialog, DialogUi):
    def __init__(self, iface, offline_editing, parent=None):
        """Constructor."""
        super(SynchronizeDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.iface = iface
        self.preferences = Preferences()
        self.offline_editing = offline_editing
        self.button_box.button(QDialogButtonBox.Save).setText(self.tr("Synchronize"))
        self.button_box.button(QDialogButtonBox.Save).clicked.connect(
            lambda: self.start_synchronization()
        )
        try:
            import_dir = self.preferences.value("importDirectoryProject")
        except ValueError:
            import_dir = None
        if not import_dir:
            import_dir = self.preferences.value("importDirectory")

        self.qfieldDir.setText(QDir.toNativeSeparators(import_dir))
        self.qfieldDir_button.clicked.connect(lambda: self.on_qfield_dir_chosen())
        self.qfieldDir.textChanged.connect(lambda: self.on_qfield_dir_changed())
        self.dirsToCopyRefreshButton.clicked.connect(
            lambda: self.update_dirs_to_sync_tree()
        )

        self.offline_editing_done = False

    def start_synchronization(self):
        self.button_box.button(QDialogButtonBox.Save).setEnabled(False)
        project = QgsProject.instance()
        current_path = Path(project.fileName())
        qfield_project_str_path = self.qfieldDir.text()
        qfield_path = Path(qfield_project_str_path)
        self.preferences.set_value("importDirectoryProject", str(qfield_path))
        self.preferences.set_value(
            "importDirsToCopy",
            {
                **self.preferences.value("importDirsToCopy"),
                qfield_project_str_path: self.extract_dirs_to_copy(),
            },
        )
        backup_project_path = make_temp_qgis_file(project)

        try:
            current_import_file_checksum = import_file_checksum(str(qfield_path))
            imported_files_checksums = import_checksums_of_project(qfield_path)

            if (
                imported_files_checksums
                and current_import_file_checksum
                and current_import_file_checksum in imported_files_checksums
            ):
                message = self.tr(
                    "Data from this file are already synchronized with the original project."
                )
                raise NoProjectFoundError(message)

            open_project(get_project_in_folder(str(qfield_path)))

            self.offline_editing.progressStopped.connect(self.update_done)
            self.offline_editing.layerProgressUpdated.connect(self.update_total)
            self.offline_editing.progressModeSet.connect(self.update_mode)
            self.offline_editing.progressUpdated.connect(self.update_value)

            try:
                self.offline_editing.synchronize(True)
            except Exception:
                self.offline_editing.synchronize()

            project_config = ProjectConfiguration(QgsProject.instance())
            original_path = Path(project_config.original_project_path or "")

            if not original_path.exists():
                answer = QMessageBox.warning(
                    self,
                    self.tr("Original project not found"),
                    self.tr(
                        'The original project path at "{}" is not found. Would you like to use the currently opened project path at "{}" instead?'
                    ).format(
                        original_path,
                        current_path,
                    ),
                    QMessageBox.Yes | QMessageBox.No,
                )

                if answer == QMessageBox.Ok:
                    project_config.original_project_path = str(current_path)
                    original_path = current_path
                else:
                    self.iface.messageBar().pushInfo(
                        "QFieldSync",
                        self.tr('No original project path found at "{}"').format(
                            original_path
                        ),
                    )

            if not self.offline_editing_done:
                raise NoProjectFoundError(
                    self.tr(
                        "The project you imported does not seem to be an offline project"
                    )
                )

            if original_path.exists() and open_project(
                str(original_path), backup_project_path
            ):
                import_dirs_to_copy = self.preferences.value("importDirsToCopy").get(
                    qfield_project_str_path, {}
                )

                # use the import dirs to copy selection if available, otherwise keep the old behavior
                if import_dirs_to_copy:
                    for path, should_copy in import_dirs_to_copy.items():
                        if not should_copy:
                            continue

                        copy_attachments(
                            qfield_path,
                            original_path.parent,
                            path,
                        )
                else:
                    for attachment_dir in self.preferences.value("attachmentDirs"):
                        copy_attachments(
                            qfield_path,
                            original_path.parent,
                            attachment_dir,
                        )

                # save the data_file_checksum to the project and save it
                imported_files_checksums.append(import_file_checksum(str(qfield_path)))
                ProjectConfiguration(
                    QgsProject.instance()
                ).imported_files_checksums = imported_files_checksums
                QgsProject.instance().write()
                self.iface.messageBar().pushInfo(
                    "QFieldSync",
                    self.tr("Opened original project {}".format(original_path)),
                )
            else:
                self.iface.messageBar().pushInfo(
                    "QFieldSync",
                    self.tr(
                        "The data has been synchronized successfully but the original project ({}) could not be opened".format(
                            original_path
                        )
                    ),
                )
            self.close()
        except NoProjectFoundError as e:
            self.iface.messageBar().pushWarning("QFieldSync", str(e))

    def update_total(self, current, layer_count):
        self.totalProgressBar.setMaximum(layer_count)
        self.totalProgressBar.setValue(current)

    def update_value(self, progress):
        self.layerProgressBar.setValue(progress)

    def update_mode(self, _, mode_count):
        self.layerProgressBar.setMaximum(mode_count)
        self.layerProgressBar.setValue(0)

    def update_done(self):
        self.offline_editing.progressStopped.disconnect(self.update_done)
        self.offline_editing.layerProgressUpdated.disconnect(self.update_total)
        self.offline_editing.progressModeSet.disconnect(self.update_mode)
        self.offline_editing.progressUpdated.disconnect(self.update_value)
        self.offline_editing_done = True

    def extract_dirs_to_copy(self):
        def extract_dirs_data(root_item: QTreeWidgetItem):
            data = {}
            for i in range(root_item.childCount()):
                item = root_item.child(i)
                relative_path = item.data(0, Qt.UserRole)
                is_checked = item.checkState(0) == Qt.Checked
                data[relative_path] = is_checked

                if item.childCount() > 0:
                    data.update(extract_dirs_data(item))

            return data

        dirs_to_copy = extract_dirs_data(self.dirsToCopyTreeWidget.invisibleRootItem())

        return dirs_to_copy

    def update_dirs_to_sync_tree(self):
        if not self.qfieldDir.text():
            return

        qfield_project_str_path = self.qfieldDir.text()
        qfield_dir_path = Path(qfield_project_str_path)
        dirs_to_copy = self.preferences.value("importDirsToCopy").get(
            qfield_project_str_path, {}
        )

        if not qfield_dir_path.is_dir():
            return

        self.dirsToCopyTreeWidget.clear()

        def build_item_cb(item: QTreeWidgetItem, node: DirectoryTreeDict):
            relative_path = node["path"].relative_to(qfield_dir_path)
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

        root_item = self.dirsToCopyTreeWidget.invisibleRootItem()
        dict_paths = path_to_dict(qfield_dir_path, dirs_only=True)

        if dict_paths["type"] == DirectoryTreeType.DIRECTORY:
            for subnode in dict_paths["content"]:
                build_file_tree_widget_from_dict(
                    root_item,
                    subnode,
                    build_item_cb,
                )

    def on_qfield_dir_chosen(self):
        make_folder_selector(self.qfieldDir)()
        self.update_dirs_to_sync_tree()

    def on_qfield_dir_changed(self):
        qfield_dir_path = Path(self.qfieldDir.text())
        self.dirsToCopyRefreshButton.setEnabled(qfield_dir_path.is_dir())
