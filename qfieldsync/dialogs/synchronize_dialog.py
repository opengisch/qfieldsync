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

from qfieldsync.utils.qt_utils import get_ui_class

FORM_CLASS = get_ui_class('synchronize_base.ui')

from qfieldsync.utils.qt_utils import make_folder_selector


class SynchronizeDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, plugin_instance):
        """Constructor."""
        super(SynchronizeDialog, self).__init__(parent=None)
        self.setupUi(self)
        self.push_btn = QPushButton(self.tr('Synchronize'))
        self.push_btn.clicked.connect(self.start_synchronization)
        self.qfieldDir.setText(plugin_instance.get_import_folder())
        self.qfieldDir_btn.clicked.connect(make_folder_selector(self.qfieldDir))

    def start_synchronization(self):
        qfield_folder = self.qfieldDir.text()
        # TODO: Do the synchronization here!
        self.close()
