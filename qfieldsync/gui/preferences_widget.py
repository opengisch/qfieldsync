# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSyncDialog
                                 A QGIS plugin
 Sync your projects to QField
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

from qgis.gui import QgsFileWidget, QgsOptionsPageWidget
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.preferences import Preferences
from qfieldsync.setting_manager import SettingDialog

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/preferences_widget.ui")
)


class PreferencesWidget(WidgetUi, QgsOptionsPageWidget, SettingDialog):
    def __init__(self, qfieldSync, parent=None):
        self.qfieldSync = qfieldSync
        preferences = Preferences()
        SettingDialog.__init__(self, setting_manager=preferences)
        super().__init__(parent, setting_manager=preferences)
        self.setupUi(self)
        self.init_widgets()

        self.setting_widget("importDirectory").widget.setStorageMode(
            QgsFileWidget.GetDirectory
        )
        self.setting_widget("exportDirectory").widget.setStorageMode(
            QgsFileWidget.GetDirectory
        )
        self.setting_widget("cloudDirectory").widget.setStorageMode(
            QgsFileWidget.GetDirectory
        )

    def apply(self):
        self.set_values_from_widgets()
        self.qfieldSync.update_button_visibility()
