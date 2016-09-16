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

from PyQt4 import QtGui, uic
from PyQt4.QtGui import QDialogButtonBox, QPushButton
from qgis.gui import QgsMessageBar
from qgis.core import QgsOfflineEditing

from qfieldsync.utils.file_utils import get_children_with_extension
from qfieldsync.utils.qgis_utils import open_project
from qfieldsync.utils.qt_utils import get_ui_class, make_folder_selector
from qfieldsync.config import *

FORM_CLASS = get_ui_class('synchronize_base.ui')


class SynchronizeDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, iface, plugin_instance):
        """Constructor."""
        super(SynchronizeDialog, self).__init__(parent=None)
        self.setupUi(self)
        self.iface = iface
        self.push_btn = QPushButton(self.tr('Synchronize'))
        self.push_btn.clicked.connect(self.start_synchronization)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)
        self.qfieldDir.setText(plugin_instance.get_import_folder())
        self.qfieldDir_btn.clicked.connect(make_folder_selector(self.qfieldDir))

    def start_synchronization(self):
        qfield_folder = self.qfieldDir.text()
        qgs_file = get_children_with_extension(qfield_folder, 'qgs', count=1)[0]
        open_project(qgs_file)
        QgsOfflineEditing().synchronize() # no way to know exactly if it succeeded? 
        text = "Remote layers from {} synchronized.".format(qgs_file)
        self.iface.messageBar().pushMessage(u'Message from {}'.format(LOG_TAG), text, QgsMessageBar.INFO,
                                                MSG_DURATION_SECS)
        self.close()
