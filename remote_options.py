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

from .config import ONLINE, OFFLINE, HYBRID
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'remote_options_base.ui'))


class RemoteOptionsDialog(QtGui.QDialog, FORM_CLASS):

    def __init__(self, parent, plugin_instance, remote_layers):
        """Constructor."""
        super(RemoteOptionsDialog, self).__init__(parent)
        self.setupUi(self)
        self.push_btn = QPushButton(self.tr('Push'))
        self.parent = parent
        self.remote_layers = remote_layers
        self.push_btn.clicked.connect(self.save_options)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)

    def get_selected_mode(self):
        if self.radioButton_offline.isChecked():
            return OFFLINE
        if self.radioButton_online.isChecked():
            return ONLINE
        if self.radioButton_hybrid.isChecked():
            return HYBRID

    def save_options(self):
        mode = self.get_selected_mode()
        self.parent.push_project(remote_layers = self.remote_layers, remote_save_mode = mode)
        self.close()

