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
from qfieldsync.core import ProjectConfiguration
from qfieldsync.core.layer import *
from qfieldsync.dialogs.config_dialog import ConfigDialog
from qgis.PyQt.QtCore import (
    pyqtSlot,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QDialogButtonBox,
    QPushButton,
    QLabel,
    QSizePolicy,
    QDialog
)
from qgis.core import (
    QgsProject,
    QgsMapLayerRegistry,
    QgsMessageLog
)
from qgis.gui import (
    QgsMessageBar
)
from ..utils.export_offline_utils import (
    OfflineConverter
)
from ..utils.file_utils import fileparts, get_full_parent_path, open_folder
from ..utils.qgis_utils import get_project_title
from ..utils.qt_utils import get_ui_class
from ..utils.qt_utils import make_folder_selector

try:
    from ..utils.usb import (
        detect_devices,
        connect_device,
        push_file,
        disconnect_device
    )
except:
    pass

FORM_CLASS = get_ui_class('push_dialog_base')


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
        self.push_btn = QPushButton(self.tr('Create'))
        self.push_btn.clicked.connect(self.push_project)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)
        self.iface.mapCanvas().extentsChanged.connect(self.extentChanged)
        self.extentChanged()

        self.devices = None
        # self.refresh_devices()
        self.setup_gui()

        self.offline_editing.warning.connect(self.show_warning)

    def update_progress(self, sent, total):
        progress = float(sent) / total * 100
        self.progress_bar.setValue(progress)

    def setup_gui(self):
        """Populate gui and connect signals of the push dialog"""
        base_folder = self.plugin_instance.get_export_folder()
        project_fn = QgsProject.instance().fileName()
        export_folder_name = fileparts(project_fn)[1]
        export_folder_path = os.path.join(base_folder, export_folder_name)
        self.manualDir.setText(export_folder_path)
        self.manualDir_btn.clicked.connect(make_folder_selector(self.manualDir))
        self.update_info_visibility()
        self.infoLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.infoLabel.linkActivated.connect(lambda: self.show_settings())

    def get_export_folder_from_dialog(self):
        """Get the export folder according to the inputs in the selected"""
        # manual
        return self.manualDir.text()

    def push_project(self):
        self.informationStack.setCurrentWidget(self.progressPage)
        self.plugin_instance.action_start()

        export_folder = self.get_export_folder_from_dialog()

        offline_convertor = OfflineConverter(self.project, export_folder, self.iface.mapCanvas().extent(), self.offline_editing)

        # progress connections
        offline_convertor.layerProgressUpdated.connect(self.update_total)
        offline_convertor.progressModeSet.connect(self.update_mode)
        offline_convertor.progressUpdated.connect(self.update_value)
        offline_convertor.progressJob.connect(self.update_job_status)

        offline_convertor.convert()
        self.do_post_offline_convert_action()
        self.close()

        self.progress_group.setEnabled(False)

    def do_post_offline_convert_action(self):
        """
        Show an information label that the project has been copied
        with a nice link to open the result folder.
        """
        export_folder = self.get_export_folder_from_dialog()
        export_base_folder = get_full_parent_path(export_folder)

        resultLabel = QLabel(self.tr(u'Finished creating the project at {result_folder}. Please copy this folder to the device you want to work with.').format(
            result_folder=u'<a href="{folder}">{folder}</a>'.format(folder=export_folder)))
        resultLabel.setTextFormat(Qt.RichText)
        resultLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        resultLabel.linkActivated.connect(lambda: open_folder(export_folder))
        resultLabel.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)

        self.iface.messageBar().pushWidget(resultLabel, QgsMessageBar.INFO, 0)

    def update_info_visibility(self):
        """
        Show the info label if there are unconfigured layers
        """
        self.infoGroupBox.hide()
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if not LayerSource(layer).is_configured:
                self.infoGroupBox.show()

        project_configuration = ProjectConfiguration(self.project)

        if project_configuration.offline_copy_only_aoi or project_configuration.create_base_map:
            self.informationStack.setCurrentWidget(self.selectExtentPage)
        else:
            self.informationStack.setCurrentWidget(self.progressPage)

    def show_settings(self):
        dlg = ConfigDialog(self.iface, self.iface.mainWindow())
        dlg.exec_()
        self.update_info_visibility()

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

    @pyqtSlot(str)
    def update_job_status(self, status):
        self.statusLabel.setText(status)

    @pyqtSlot()
    def extentChanged(self):
        extent = self.iface.mapCanvas().extent()
        self.xMinLabel.setText(str(extent.xMinimum()))
        self.xMaxLabel.setText(str(extent.xMaximum()))
        self.yMinLabel.setText(str(extent.yMinimum()))
        self.yMaxLabel.setText(str(extent.yMaximum()))

    @pyqtSlot(str, str)
    def show_warning(self, _, message):
        # Most messages from the offline editing plugin are not important enough to show in the message bar.
        # In case we find important ones in the future, we need to filter them.
        QgsMessageLog.instance().logMessage(message,'QFieldSync')
