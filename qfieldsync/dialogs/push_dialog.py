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

from qgis.PyQt.QtCore import pyqtSlot, QUrl
from qgis.PyQt.QtGui import (QDialogButtonBox, QPushButton, QDialog,
                             QDesktopServices, QMessageBox)

from qgis.gui import QgsMessageBar
from qgis.core import QgsProject

from qfieldsync.config import *
from qfieldsync.utils.data_source_utils import *
from qfieldsync.utils.export_offline_utils import offline_convert, \
    get_layer_ids_to_offline_convert
from qfieldsync.utils.file_utils import fileparts, get_full_parent_path
from qfieldsync.utils.qgis_utils import get_project_title
from qfieldsync.utils.qt_utils import make_folder_selector

from qfieldsync.utils.qt_utils import get_ui_class

try:
    from qfieldsync.utils.usb import detect_devices, connect_device, \
        push_file, \
        disconnect_device
except:
    pass

from qfieldsync.dialogs.remote_options_dialog import RemoteOptionsDialog

FORM_CLASS = get_ui_class('push_dialog_base.ui')


class PushDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, plugin_instance):
        """Constructor."""
        super(PushDialog, self).__init__(parent=None)
        self.setupUi(self)
        self.iface = iface
        self.plugin_instance = plugin_instance
        self.offline_editing = plugin_instance.offline_editing
        self.project = QgsProject.instance()
        self.project_lbl.setText(get_project_title(self.project))
        self.push_btn = QPushButton(self.tr('Push'))
        if project_get_remote_layers():
            self.push_btn.clicked.connect(self.show_remote_options)
        else:
            self.push_btn.clicked.connect(self.push_project)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)

        self.devices = None
        self.refresh_devices()
        self.setup_tabs()
        self.cloud_tab.setEnabled(True)
        self.adb_tab.setEnabled(False)
        self.ftp_tab.setEnabled(False)

        self.offline_editing_done = False

    def show_remote_options(self):
        dlg = RemoteOptionsDialog(self, self.plugin_instance,
                                  remote_layers=project_get_remote_layers())
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
        self.plugin_instance.action_start()

        # progress connections
        self.offline_editing.progressStopped.connect(self.update_done)
        self.offline_editing.layerProgressUpdated.connect(self.update_total)
        self.offline_editing.progressModeSet.connect(self.update_mode)
        self.offline_editing.progressUpdated.connect(self.update_value)

        export_folder = self.get_export_folder_from_dialog()
        can_only_be_online_layers = project_get_always_online_layers()
        if can_only_be_online_layers:
            self.show_warning_about_layers_that_cant_work_offline(
                    can_only_be_online_layers)
        non_qfield_layers = project_get_qfield_unsupported_layers()
        if non_qfield_layers:
            self.show_warning_about_layers_that_cant_work_with_qfield(
                    non_qfield_layers)

        vector_layer_ids = get_layer_ids_to_offline_convert(remote_layers,
                                                            remote_save_mode)
        shpfile_layers = project_get_shp_layers()
        raster_layers = project_get_raster_layers()
        project_directory = offline_convert(self.offline_editing,
                                            vector_layer_ids,
                                            raster_layers,
                                            shpfile_layers,
                                            export_folder=export_folder)

        if remote_save_mode == HYBRID:
            self.set_hybrid_flag()

        self.do_post_offline_convert_action()
        self.plugin_instance.action_end(self.tr('Push to QField'))

        self.progress_group.setEnabled(False)
        if self.offline_editing_done:
            self.close()
        else:
            message = self.tr("The project export did't work")
            self.iface.messageBar().pushCritical('Sync dialog', message)

        # this here doesn't do anything for now
        # device_index = self.devices_cbx.currentIndex()
        # device = self.devices[device_index][1]
        # mtp = connect_device(device)
        # dest = 'testFILE.qgs'
        # push_file(mtp, self.project.fileName(), dest, self.update_progress)
        # disconnect_device(mtp)

    def do_post_offline_convert_action(self):
        if self.tabWidget.currentIndex() == 0:
            export_folder = self.get_export_folder_from_dialog()
            export_base_folder = get_full_parent_path(export_folder)
            text = "Your project has been exported sucessfully to {}, please " \
                   "copy the entire folder to the device".format(
                    export_folder)
            self.iface.messageBar().pushMessage(
                    u'Message from {}'.format(LOG_TAG), text,
                    QgsMessageBar.INFO,
                    MSG_DURATION_SECS)
            if self.checkBox_open.isChecked():
                QDesktopServices.openUrl(
                        QUrl.fromLocalFile(export_base_folder))
        else:
            raise Exception("FTP and ADB not fully supported yet")

    def show_warning_about_layers_that_cant_work_offline(self, layers):
        layers_list = ','.join([layer.name() for layer in layers])
        QMessageBox.information(self.iface.mainWindow(), 'Warning',
                                      self.tr(
                                              'Layers {} require a real time '
                                              'connection').format(
                                              layers_list))

    def show_warning_about_layers_that_cant_work_with_qfield(self, layers):
        layers_list = ','.join([layer.name() for layer in layers])
        QMessageBox.information(self.iface.mainWindow(), 'Warning',
                                      self.tr(
                                              'Layers {} are not supported by '
                                              'QField').format(
                                              layers_list))

    def set_hybrid_flag(self):
        QgsProject.instance().writeEntry(self.plugin_instance.QFIELD_SCOPE,
                                         "REMOTE_LAYER_MODE", HYBRID)

    @pyqtSlot(int, int)
    def update_total(self, current, layer_count):
        self.totalProgressBar.setMaximum(layer_count)
        self.totalProgressBar.setValue(current)

    @pyqtSlot(int)
    def update_value(self, progress):
        self.layerProgressBar.setValue(progress)

    @pyqtSlot('QgsOfflineEditing::ProgressMode', int)
    def update_mode(self, _, mode_count):
        self.layerProgressBar.setMaximum(mode_count)
        self.layerProgressBar.setValue(0)

    @pyqtSlot()
    def update_done(self):
        self.offline_editing_done = True
