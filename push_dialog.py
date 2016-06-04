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

from datetime import datetime
import os

from PyQt4 import QtGui, QtCore, uic
from qgis.core import QgsMapLayerRegistry, QgsProject, QgsOfflineEditing
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

from .remote_options import RemoteOptionsDialog


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'push_dialog_base.ui'))


BASE_SAVE_LOCATION="/tmp/" #FIXME subject to change

class PushDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        """Constructor."""
        super(PushDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.project = QgsProject.instance()
        self.project_lbl.setText(self.project.title())
        self.push_btn = QPushButton('Push')
        if self.project_get_remote_layers():
            self.push_btn.clicked.connect(self.show_remote_options)
        else:
            self.push_btn.clicked.connect(self.push_project)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)

        self.devices = None
        self.refresh_devices()
        self.suggest_offline_wdg.setEnabled(len(self.project_get_always_online_layers())>0)

    def show_remote_options(self):
        dlg = RemoteOptionsDialog(self, remote_layers=self.project_get_remote_layers())
        dlg.exec_()

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

    def get_layer_ids_to_offline_convert(self, remote_layers, remote_save_mode):
        layer_ids = []
        if remote_save_mode == RemoteOptionsDialog.OFFLINE: 
            for layer in remote_layers:
                layer_ids.append(layer.id())

        for layer in self.project_get_always_offline_layers():
            layer_ids.append(layer.id())
        return layer_ids

    def offline_convert(self, vector_layer_ids):
        dt_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        existing_filepath = QgsProject.instance().fileName()
        existing_fn, ext = os.path.splitext(os.path.basename(existing_filepath)) 
        dataPath = os.path.join(BASE_SAVE_LOCATION, existing_fn+"_"+dt_tag)
        if not os.path.exists(dataPath):
            os.mkdir(dataPath)
        dbPath = "data.sqlite"
        success = QgsOfflineEditing().convertToOfflineProject(dataPath, dbPath, vector_layer_ids)
        if not success:
            raise Exception("Converting to offline project did not succeed")
        # Now we have a project state which can be saved as offline project
        QgsProject.instance().write(QtCore.QFileInfo(os.path.join(dataPath, existing_fn+"_offline"+ext)))
        # TODO rasters also


    def push_project(self, remote_layers=None, remote_save_mode=None):

        can_only_be_online_layers = self.project_get_always_online_layers()
        if can_only_be_online_layers:
            self.show_warning_about_layers_that_cant_work_offline(can_only_be_online_layers)

        vector_layer_ids = self.get_layer_ids_to_offline_convert(remote_layers, remote_save_mode)
        self.offline_convert(vector_layer_ids)

        if remote_save_mode == RemoteOptionsDialog.HYBRID:
            self.set_hybrid_flag()
        # TODO: show actual, more informative dialog with button and warning not to keep working on this file
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(BASE_SAVE_LOCATION))

        # this here doesn't do anything for now
        device_index = self.devices_cbx.currentIndex()
        device = self.devices[device_index][1]
        mtp = connect_device(device)
        dest = 'testFILE.qgs'
        push_file(mtp, self.project.fileName(), dest, self.update_progress)
        disconnect_device(mtp)

    def show_warning_about_layers_that_cant_work_offline(self, layers):
        layers_list = ','.join([ layer.name() for layer in layers])
        QtGui.QMessageBox.information(self.iface.mainWindow(), 'Warning','Layers {} require a real time connection'.format(layers_list))

    def set_hybrid_flag(self):
        QgsProject.instance().writeEntry(QgsOfflineEditing.PROJECT_ENTRY_SCOPE_OFFLINE,"REMOTE_LAYER_MODE",RemoteOptions.HYBRID)

    def on_reload_devices_btn_clicked(self):
        self.refresh_devices()

    @staticmethod
    def project_get_layers_of_given_types(types):
        # can see all types via
        # QgsProviderRegistry.instance().providerList()
        map_layers = QgsMapLayerRegistry.instance().mapLayers(
        )
        result = []
        for name, layer in map_layers.items():
            if layer.providerType() in types:
                result.append(layer)
        return result

    @staticmethod
    def project_get_always_online_layers():
        """ Layers that can't be made offline by the offline plugin """
        online_types = ["WFS", "wcs", "wms", "mssql", "ows"]
        return PushDialog.project_get_layers_of_given_types(online_types)

    @staticmethod
    def project_get_remote_layers():
        """ Remote layers are layers that can either be converted to offline or kept in a realtime or hybrid mode"""
        return PushDialog.project_get_layers_of_given_types(types=["postgres"])

    @staticmethod
    def project_get_always_offline_layers():
        """ Layers that are file based and hence can always be handled by the offline plugin"""
        types = ['delimitedtext', u'gdal', u'gpx', u'memory', u'ogr', u'spatialite']
        return PushDialog.project_get_layers_of_given_types(types=types)
