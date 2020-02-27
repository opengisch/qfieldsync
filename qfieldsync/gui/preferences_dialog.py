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
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QDialog

from qgis.PyQt.uic import loadUiType
from qfieldsync.utils.qt_utils import make_folder_selector
from qfieldsync.utils.qfieldcloud_utils import login

DialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/preferences_dialog.ui'))


class PreferencesDialog(QDialog, DialogUi):

    def __init__(self, preferences, parent=None):
        """Constructor.
        :type preferences: qfieldsync.core.Preferences
        """
        super(PreferencesDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.preferences = preferences
        self.import_directory.setText(self.preferences.import_directory)
        self.export_directory.setText(self.preferences.export_directory)
        self.qfieldcloud_base_url.setText(self.preferences.qfieldcloud_base_url)
        self.qfieldcloud_username.setText(self.preferences.qfieldcloud_username)
        self.qfieldcloud_password.setText(self.preferences.qfieldcloud_password)
        self.import_directory_button.clicked.connect(make_folder_selector(self.import_directory))
        self.export_directory_button.clicked.connect(make_folder_selector(self.export_directory))

        self.accepted.connect(self.save_settings)
        self.qfieldcloud_check.clicked.connect(self.check_qfieldcloud_connection)

    @pyqtSlot()
    def save_settings(self):
        self.preferences.import_directory = self.import_directory.text()
        self.preferences.export_directory = self.export_directory.text()
        self.preferences.qfieldcloud_base_url = self.qfieldcloud_base_url.text()
        self.preferences.qfieldcloud_username = self.qfieldcloud_username.text()
        self.preferences.qfieldcloud_password = self.qfieldcloud_password.text()
        self.close()

    @pyqtSlot()
    def check_qfieldcloud_connection(self):
        self.qfieldcloud_check.setDisabled(True)
        self.qfieldcloud_check_result.setStyleSheet(
            'QLabel { background-color : white; color : white; }')
        self.qfieldcloud_check_result.setText('')

        token = login(
            self.qfieldcloud_base_url.text(),
            self.qfieldcloud_username.text(),
            self.qfieldcloud_password.text())

        if token:
            self.qfieldcloud_check_result.setStyleSheet(
                'QLabel { background-color : green; color : white; }')
            self.qfieldcloud_check_result.setText(
                'Connection to QFieldCloud was successful')
        else:
            self.qfieldcloud_check_result.setStyleSheet(
                'QLabel { background-color : red; color : white; }')
            self.qfieldcloud_check_result.setText(
                'Unable to connect to QFieldCloud!')

        self.qfieldcloud_check.setDisabled(False)
