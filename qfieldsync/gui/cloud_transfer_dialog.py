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
from typing import Dict, List

from qgis.PyQt.QtCore import Qt, QObject
from qgis.PyQt.QtGui import QShowEvent
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QTreeWidgetItem, QWidget, QCheckBox, QHBoxLayout, QHeaderView
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.cloud_transferrer import CloudTransferrer
from qfieldsync.core.cloud_project import ProjectFile, ProjectFileCheckout


CloudTransferDialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/cloud_transfer_dialog.ui'))


class CloudTransferDialog(QDialog, CloudTransferDialogUi):

    def __init__(self, project_transfer: CloudTransferrer, parent: QObject = None) -> None:
        """Constructor.
        """
        super(CloudTransferDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.project_transfer = project_transfer

        self.project_transfer.error.connect(self.on_error)
        self.project_transfer.upload_progress.connect(self.on_upload_transfer_progress)
        self.project_transfer.download_progress.connect(self.on_download_transfer_progress)
        self.project_transfer.finished.connect(self.on_transfer_finished)

        self.filesTree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.filesTree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.filesTree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.filesTree.expandAll()

        self.setWindowTitle(self.tr('Synchronizing project "{}"').format(self.project_transfer.cloud_project.name))
        self.buttonBox.button(QDialogButtonBox.Ok).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Abort).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Cancel).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Apply).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Apply).setText(self.tr('Sync!'))
        self.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.on_project_apply_clicked)

        self.preferNoneButton.clicked.connect(self._on_prefer_none_button_clicked)
        self.preferLocalButton.clicked.connect(self._on_prefer_local_button_clicked)
        self.preferCloudButton.clicked.connect(self._on_prefer_cloud_button_clicked)

        self.uploadProgressBar.setValue(0)
        self.downloadProgressBar.setValue(0)


    def showEvent(self, event: QShowEvent) -> None:
        self.buttonBox.button(QDialogButtonBox.Cancel).setVisible(True)

        super().showEvent(event)

        self.build_files_tree()
        self.stackedWidget.setCurrentWidget(self.filesPage)
        self.buttonBox.button(QDialogButtonBox.Apply).setVisible(True)


    def build_files_tree(self):
        # NOTE algorithmic part
        # ##########
        # The "cloud_files" objects are assumed to be sorted alphabetically by name.
        # First split filenames into parts. For example: '/home/ninja.file' will result into ['home', 'ninja.file'] parts.
        # Then store pairs of the part and the corresponding QTreeWidgetItem in a stack. 
        # Pop and push to the stack when the current filename part does not match the previous one.
        # ##########
        stack = []

        for project_file in self.project_transfer.cloud_project.files_to_sync:
            parts = tuple(project_file.path.parts)
            for part_idx, part in enumerate(parts):
                if len(stack) > part_idx and stack[part_idx][0] == part:
                    continue
                else:
                    stack = stack[0:part_idx]

                item = QTreeWidgetItem()
                item.setText(0, part)

                stack.append((part, item))

                if len(stack) == 1:
                    self.filesTree.addTopLevelItem(item)
                else:
                    stack[-2][1].addChild(stack[-1][1])

                # the length of the stack and the parts is equal for file entries
                if len(stack) == len(parts):
                    item.setData(0, Qt.UserRole, project_file)
                    self.add_file_checkbox_buttons(item, project_file)
                else:
                    # TODO make a fancy button that marks all the child items as checked or not
                    pass
        # NOTE END algorithmic part


    def on_project_apply_clicked(self) -> None:
        self.buttonBox.button(QDialogButtonBox.Ok).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.buttonBox.button(QDialogButtonBox.Abort).setVisible(True)
        self.buttonBox.button(QDialogButtonBox.Apply).setVisible(False)
        self.buttonBox.button(QDialogButtonBox.Cancel).setVisible(False)

        files: Dict[str, List[ProjectFile]] = {'to_upload': [], 'to_download': []}

        for item_idx in range(self.filesTree.topLevelItemCount()):
            item = self.filesTree.topLevelItem(item_idx)

            self.traverse_tree_item(item, files)
            
        self.stackedWidget.setCurrentWidget(self.progressPage)
        self.project_transfer.sync(files['to_upload'], files['to_download'])


    def traverse_tree_item(self, item: QTreeWidgetItem, files: Dict[str, List[ProjectFile]]) -> None:
        project_file = item.data(0, Qt.UserRole)

        if project_file:
            assert item.childCount() == 0

            if self.filesTree.itemWidget(item, 1).children()[1].isChecked():
                files['to_upload'].append(project_file)
            elif self.filesTree.itemWidget(item, 2).children()[1].isChecked():
                files['to_download'].append(project_file)

            return

        for child_idx in range(item.childCount()):
            self.traverse_tree_item(item.child(child_idx), files)


    def add_file_checkbox_buttons(self, item: QTreeWidgetItem, project_file: ProjectFile) -> None:
        is_local_enabled = project_file.local_path_exists
        is_cloud_enabled = project_file.checkout & ProjectFileCheckout.Cloud
        is_local_checked = is_local_enabled

        local_checkbox = QCheckBox()
        local_checkbox.setEnabled(is_local_enabled)
        local_checkbox.setChecked(is_local_checked)
        local_checkbox.toggled.connect(lambda _is_checked: self.on_local_checkbox_toggled(item))
        local_checkbox_widget = QWidget()
        local_checkbox_layout = QHBoxLayout()
        local_checkbox_layout.setAlignment(Qt.AlignCenter)
        local_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        local_checkbox_layout.addWidget(local_checkbox)
        local_checkbox_widget.setLayout(local_checkbox_layout)

        cloud_checkbox = QCheckBox()
        cloud_checkbox.setEnabled(is_cloud_enabled)
        cloud_checkbox.setChecked(is_cloud_enabled and not is_local_checked)
        cloud_checkbox.toggled.connect(lambda _is_checked: self.on_cloud_checkbox_toggled(item))
        cloud_checkbox_widget = QWidget()
        cloud_checkbox_layout = QHBoxLayout()
        cloud_checkbox_layout.setAlignment(Qt.AlignCenter)
        cloud_checkbox_layout.setContentsMargins(0, 0, 0, 0)
        cloud_checkbox_layout.addWidget(cloud_checkbox)
        cloud_checkbox_widget.setLayout(cloud_checkbox_layout)

        self.filesTree.setItemWidget(item, 1, local_checkbox_widget)
        self.filesTree.setItemWidget(item, 2, cloud_checkbox_widget)


    def on_error(self, descr: str, error: Exception = None) -> None:
        self.errorLabel.setText(self.errorLabel.text() + '\n' + descr)

    
    def on_upload_transfer_progress(self, fraction: float) -> None:
        self.uploadProgressBar.setValue(int(fraction * 100))


    def on_download_transfer_progress(self, fraction: float) -> None:
        self.downloadProgressBar.setValue(int(fraction * 100))


    def on_transfer_finished(self) -> None:
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Abort).setEnabled(False)


    def on_local_checkbox_toggled(self, item: QTreeWidgetItem) -> None:
        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 2).children()[1]
        is_checked = local_checkbox.isChecked()

        if cloud_checkbox.isEnabled() and is_checked:
            cloud_checkbox.setChecked(False)


    def on_cloud_checkbox_toggled(self, item: QTreeWidgetItem) -> None:
        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 2).children()[1]
        is_checked = cloud_checkbox.isChecked()

        if local_checkbox.isEnabled() and is_checked:
            local_checkbox.setChecked(False)


    def _on_offline_converter_total_progress_updated(self, current: int, total: int, message: str) -> None:
        self.totalProgressBar.setMaximum(total)
        self.totalProgressBar.setValue(current)
        self.statusLabel.setText(message)


    def _on_offline_converter_task_progress_updated(self, progress: int, total: int) -> None:
        self.layerProgressBar.setMaximum(total)
        self.layerProgressBar.setValue(progress)


    def on_offline_editing_progress_stopped(self) -> None:
        self.offline_editing_done = True


    def on_offline_editing_layer_progress_updated(self, progress: int, total: int) -> None:
        self.totalProgressBar.setMaximum(total)
        self.totalProgressBar.setValue(progress)


    def on_offline_editing_progress_mode_set(self, _, total: int) -> None:
        self.layerProgressBar.setMaximum(total)
        self.layerProgressBar.setValue(0)


    def on_offline_editing_progress_updated(self, progress: int) -> None:
        self.layerProgressBar.setValue(progress)


    def _on_prefer_none_button_clicked(self) -> None:
        # NOTE: LocalAndCloud is used to make neither checkbox checked. Don't use Deleted, as it might be added as a checkbox later.
        self._file_tree_set_checkboxes(ProjectFileCheckout.LocalAndCloud)


    def _on_prefer_local_button_clicked(self) -> None:
        self._file_tree_set_checkboxes(ProjectFileCheckout.Local)


    def _on_prefer_cloud_button_clicked(self) -> None:
        self._file_tree_set_checkboxes(ProjectFileCheckout.Cloud)


    def _file_tree_set_checkboxes(self, checkout: ProjectFileCheckout) -> None:
        for item_idx in range(self.filesTree.topLevelItemCount()):
            self._file_tree_set_checkboxes_recursive(self.filesTree.topLevelItem(item_idx), checkout)


    def _file_tree_set_checkboxes_recursive(self, item: QTreeWidgetItem, checkout: ProjectFileCheckout) -> None:
        project_file = item.data(0, Qt.UserRole)

        if project_file:
            assert item.childCount() == 0
        else:
            for child_idx in range(item.childCount()):
                self._file_tree_set_checkboxes_recursive(item.child(child_idx), checkout)
            return

        local_checkbox = self.filesTree.itemWidget(item, 1).children()[1]
        cloud_checkbox = self.filesTree.itemWidget(item, 2).children()[1]

        if checkout == ProjectFileCheckout.Local and local_checkbox.isEnabled():
            local_checkbox.setChecked(True)
        elif checkout == ProjectFileCheckout.Cloud and cloud_checkbox.isEnabled():
            cloud_checkbox.setChecked(True)
        elif checkout == ProjectFileCheckout.LocalAndCloud:
            local_checkbox.setChecked(False)
            cloud_checkbox.setChecked(False)
        elif checkout == ProjectFileCheckout.Deleted:
            # Reserved for a better future
            pass
