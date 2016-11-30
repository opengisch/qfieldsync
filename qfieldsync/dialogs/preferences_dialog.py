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

from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QDialog

from qfieldsync.utils.qt_utils import get_ui_class
from qfieldsync.utils.qt_utils import make_folder_selector

FORM_CLASS = get_ui_class('preferences_dialog')


class PreferencesDialog(QDialog, FORM_CLASS):
    def __init__(self, preferences, parent=None):
        """Constructor.
        :type preferences: qfieldsync.core.Preferences
        """
        super(PreferencesDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.preferences = preferences
        self.import_directory.setText(self.preferences.import_directory)
        self.export_directory.setText(self.preferences.export_directory)
        self.import_directory_button.clicked.connect(make_folder_selector(self.import_directory))
        self.export_directory_button.clicked.connect(make_folder_selector(self.export_directory))

        self.accepted.connect(self.save_settings)

    @pyqtSlot()
    def save_settings(self):
        self.preferences.import_directory = self.import_directory.text()
        self.preferences.export_directory = self.export_directory.text()
        self.close()
