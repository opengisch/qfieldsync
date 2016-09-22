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
from __future__ import absolute_import
from __future__ import print_function

import os

from qgis.PyQt import QtGui, uic
from qgis.PyQt.QtGui import QDialogButtonBox, QPushButton

from qfieldsync.utils.qt_utils import get_ui_class

FORM_CLASS = get_ui_class('settings.ui')

from qfieldsync.utils.qt_utils import make_folder_selector


class SettingsDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, plugin_instance):
        """Constructor."""
        super(SettingsDialog, self).__init__(parent=None)
        self.setupUi(self)
        self.push_btn = QPushButton(self.tr('Save'))
        self.plugin_instance = plugin_instance
        self.push_btn.clicked.connect(self.save_settings)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)
        import_folder = self.plugin_instance.get_import_folder()
        export_folder = self.plugin_instance.get_export_folder()
        self.importDir.setText(import_folder)
        self.exportDir.setText(export_folder)
        self.importDir_btn.clicked.connect(make_folder_selector(self.importDir))
        self.exportDir_btn.clicked.connect(make_folder_selector(self.exportDir))


    def save_settings(self):
        import_folder = self.importDir.text()
        export_folder = self.exportDir.text()
        self.plugin_instance.update_settings(import_folder, export_folder)
        self.close()
