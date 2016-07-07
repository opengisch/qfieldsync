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

from PyQt4 import QtGui, QtCore, uic
from PyQt4.QtGui import QDialogButtonBox, QPushButton

from .export_offline import offline_convert, get_layer_ids_to_offline_convert
from .data_source_utils import *
from .config import *
from .file_utils import fileparts
from .qt_utils import make_folder_selector

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



class PushDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, iface, plugin_instance):
        """Constructor."""
        super(PushDialog, self).__init__(parent=None)
        self.setupUi(self)
        self.iface = iface
        self.plugin_instance = plugin_instance
        self.project = QgsProject.instance()
        self.project_lbl.setText(self.project.title())
        self.push_btn = QPushButton(self.tr('Push'))
        if project_get_remote_layers():
            self.push_btn.clicked.connect(self.show_remote_options)
        else:
            self.push_btn.clicked.connect(self.push_project)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)

        self.devices = None
        self.refresh_devices()
        self.setup_tabs()

    def show_remote_options(self):
        dlg = RemoteOptionsDialog(self, self.plugin_instance, remote_layers=project_get_remote_layers())
        dlg.exec_()

    def refresh_devices(self):
        return
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


    def setup_tabs(self):
        """Populate tabs and connect signals for the tabs of the push dialog"""
        base_folder = self.plugin_instance.get_export_folder()
        project_fn = QgsProject.instance().fileName()
        export_folder_name = fileparts(project_fn)[1]
        export_folder_path = os.path.join(base_folder, export_folder_name)
        self.manualDir.setText(export_folder_path)
        self.cloudDir.setText(export_folder_path)
        self.manualDir_btn.clicked.connect(make_folder_selector(self.manualDir))
        self.cloudDir_btn.clicked.connect(make_folder_selector(self.cloudDir))
        self.tabWidget.currentChanged.connect(self.change_description_text)
        self.change_description_text()

    def change_description_text(self):
        """ Change description text according to tab selected"""
        if self.tabWidget.currentIndex() == 0:
            text = self.tr("A folder containing all the needed files is created for you in the filesystem.")
        if self.tabWidget.currentIndex() == 1:
            text = self.tr("""A folder containing all the needed files is created for you into your chosen destination.
You can use any cloud sync service you want (Dropbox etc)
to sync this destination to your device using a third party app.""")
        if self.tabWidget.currentIndex() == 2:
            text = self.tr("FTP description")
        if self.tabWidget.currentIndex() == 3:
            text = self.tr("ADB description")
        self.label.setText(text)


    def get_export_folder_from_dialog(self):
        """Get the export folder according to the inputs in the tab selected"""
        # manual
        if self.tabWidget.currentIndex() == 0:
            return self.manualDir.text()
        # cloud
        if self.tabWidget.currentIndex() == 1:
            return self.cloudDir.text()

        # ftp (yet to be implemented)
        if self.tabWidget.currentIndex() == 2:
            raise Exception("FTP not implemented yet")

        if self.tabWidget.currentIndex() == 3:
            raise Exception("ADB mode not implemented yet")


    def push_project(self, remote_layers=None, remote_save_mode=None):

        export_folder = self.get_export_folder_from_dialog()
        can_only_be_online_layers = project_get_always_online_layers()
        if can_only_be_online_layers:
            self.how_warning_about_layers_that_cant_work_offline(can_only_be_online_layers)

        vector_layer_ids = get_layer_ids_to_offline_convert(remote_layers, remote_save_mode)
        shpfile_layers = project_get_shp_layers()
        raster_layers = project_get_raster_layers()
        project_directory = offline_convert(vector_layer_ids, raster_layers, shpfile_layers,
                                            export_folder=export_folder)

        if remote_save_mode == HYBRID:
            self.set_hybrid_flag()
        QtGui.QMessageBox.information(self.iface.mainWindow(), 'Info',
                self.tr('Please copy {} to your device').format(project_directory))
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.plugin_instance.get_export_folder()))
        self.close()

        # this here doesn't do anything for now
        #device_index = self.devices_cbx.currentIndex()
        #device = self.devices[device_index][1]
        #mtp = connect_device(device)
        #dest = 'testFILE.qgs'
        #push_file(mtp, self.project.fileName(), dest, self.update_progress)
        #disconnect_device(mtp)

    def show_warning_about_layers_that_cant_work_offline(self, layers):
        layers_list = ','.join([ layer.name() for layer in layers])
        QtGui.QMessageBox.information(self.iface.mainWindow(), 'Warning',
                self.tr('Layers {} require a real time connection').format(layers_list))

    def set_hybrid_flag(self):
        QgsProject.instance().writeEntry(self.plugin_instance.QFIELD_SCOPE,"REMOTE_LAYER_MODE", HYBRID)

    def on_reload_devices_btn_clicked(self):
        self.refresh_devices()
