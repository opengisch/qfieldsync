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
from qgis.core import QgsMapLayerRegistry, QgsProject
from PyQt4.QtGui import QDialogButtonBox, QPushButton
try:
    from .utils.usb import detect_devices, connect_device, push_file, \
        disconnect_device
except:
    from mock import MagicMock
    push_file = MagicMock()
    connect_device = MagicMock()
    disconnect_device = MagicMock()
    push_file = MagicMock()
    detect_devices = MagicMock(return_value=[("Fake Device", MagicMock())])


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'push_dialog_base.ui'))


class PushDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(PushDialog, self).__init__(parent)
        self.setupUi(self)
        self.project = QgsProject.instance()
        self.project_lbl.setText(self.project.title())
        self.push_btn = QPushButton('Push')
        self.push_btn.clicked.connect(self.push_project)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)

        self.devices = None
        self.refresh_devices()
        # self.suggest_offline_wdg.setEnabled(self.detect_online_layers())

    def refresh_devices(self):
        self.devices = detect_devices()
        device_names = []
        for d in self.devices:
            device_name, device = d
            device_names.append(device_name)
        if device_names:
            self.devices_cbx.clear()
            self.push_btn.setEnabled(True)
            self.devices_cbx.setEnabled(True)
            self.devices_cbx.addItems(device_names)
        else:
            self.push_btn.setEnabled(False)
            self.devices_cbx.setEnabled(False)
            self.devices_cbx.addItems('No devices detected')

    def update_progress(self, sent, total):
        progress = float(sent) / total * 100
        self.progress_bar.setValue(progress)

    def push_project(self):
        device_index = self.devices_cbx.currentIndex()
        device = self.devices[device_index][1]
        mtp = connect_device(device)
        dest = 'testFILE.qgs'
        push_file(mtp, self.project.fileName(), dest, self.update_progress)
        disconnect_device(mtp)

    def on_reload_devices_btn_clicked(self):
        self.refresh_devices()

    @staticmethod
    def detect_online_layers():
        # unused nd not implemented
        map_layers = QgsMapLayerRegistry.instance().mapLayers(
        )
        for name, layer in map_layers.items():
            print(layer.providerType())
            print(layer.publicSource())
        return True
