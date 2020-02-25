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
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.uic import loadUiType
from qgis.gui import QgsFileWidget
from qfieldsync.setting_manager import SettingDialog, UpdateMode
from qfieldsync.core.preferences import Preferences

DialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/preferences_dialog.ui'))


class PreferencesDialog(QDialog, DialogUi, SettingDialog):

    def __init__(self, parent=None):
        preferences = Preferences()
        super(PreferencesDialog, self).__init__(parent=parent)
        SettingDialog.__init__(self, setting_manager=preferences, mode=UpdateMode.DialogAccept)
        self.setupUi(self)
        self.init_widgets()

        self.setting_widget('importDirectory').widget.setStorageMode(QgsFileWidget.GetDirectory)
        self.setting_widget('exportDirectory').widget.setStorageMode(QgsFileWidget.GetDirectory)

