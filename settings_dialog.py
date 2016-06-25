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
from __future__ import print_function
from __future__ import absolute_import

import os
from PyQt4 import QtGui, uic
from PyQt4.QtGui import QDialogButtonBox, QPushButton

from .config import MANUAL, ADB, NETWORK
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'settings.ui'))


class SettingsDialog(QtGui.QDialog, FORM_CLASS):

    def __init__(self, plugin_instance):
        """Constructor."""
        super(SettingsDialog, self).__init__(parent=None)
        self.setupUi(self)
        self.push_btn = QPushButton(plugin_instance.tr('Save'))
        self.plugin_instance = plugin_instance
        self.push_btn.clicked.connect(self.save_settings)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)
        import_folder, export_folder, copy_mode = self.plugin_instance.get_settings()
        self.importDir.setText(import_folder)
        self.exportDir.setText(export_folder)
        self.set_selected_copy_mode(copy_mode)
        self.importDir_btn.clicked.connect(self.selectImportFolder)
        self.exportDir_btn.clicked.connect(self.selectExportFolder)

    def get_selected_copy_mode(self):
        if self.radioButton_adb.isChecked():
            return ADB
        if self.radioButton_network.isChecked():
            return NETWORK
        if self.radioButton_manual.isChecked():
            return MANUAL


    def selectImportFolder(self):
        self.importDir.setText(QtGui.QFileDialog.getExistingDirectory(directory=self.importDir.text()))

    def selectExportFolder(self):
        self.exportDir.setText(QtGui.QFileDialog.getExistingDirectory(directory=self.exportDir.text()))


    def set_selected_copy_mode(self, mode):
        if mode==ADB:
            self.radioButton_adb.setChecked(True)
        if mode==MANUAL:
            self.radioButton_manual.setChecked(True)
        if mode==NETWORK:
            self.radioButton_network.setChecked(True)

    def save_settings(self):
        import_folder = self.importDir.text() 
        export_folder = self.exportDir.text()
        copy_mode = self.get_selected_copy_mode()
        self.plugin_instance.update_settings(import_folder, export_folder, copy_mode)
        self.close()
