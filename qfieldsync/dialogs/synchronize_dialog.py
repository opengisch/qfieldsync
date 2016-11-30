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

from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QPushButton
)

from qfieldsync.utils.exceptions import NoProjectFoundError
from qfieldsync.utils.file_utils import get_project_in_folder
from qfieldsync.utils.qgis_utils import open_project
from qfieldsync.utils.qt_utils import get_ui_class, make_folder_selector

FORM_CLASS = get_ui_class('synchronize_dialog')


class SynchronizeDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, qfield_preferences, offline_editing, parent):
        """Constructor.
        :type qfield_preferences: qfieldsync.core.Preferences
        """
        super(SynchronizeDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.iface = iface
        self.offline_editing = offline_editing
        self.push_btn = QPushButton(self.tr('Synchronize'))
        self.push_btn.clicked.connect(self.start_synchronization)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)
        self.qfieldDir.setText(qfield_preferences.import_directory)
        self.qfieldDir_btn.clicked.connect(make_folder_selector(self.qfieldDir))

        self.offline_editing_done = False

    def start_synchronization(self):
        qfield_folder = self.qfieldDir.text()
        try:
            self.progress_group.setEnabled(True)
            qgs_file = get_project_in_folder(qfield_folder)
            open_project(qgs_file)
            self.offline_editing.progressStopped.connect(self.update_done)
            self.offline_editing.layerProgressUpdated.connect(self.update_total)
            self.offline_editing.progressModeSet.connect(self.update_mode)
            self.offline_editing.progressUpdated.connect(self.update_value)
            self.offline_editing.synchronize()
            if self.offline_editing_done:
                self.close()
            else:
                message = self.tr("The project you imported does not seem to be "
                                  "an offline project")
                raise NoProjectFoundError(message)
        except NoProjectFoundError as e:
            self.iface.messageBar().pushWarning('Sync dialog', str(e))
        finally:
            self.progress_group.setEnabled(False)

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
