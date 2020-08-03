# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldCloudDialog
                                 A QGIS plugin
 Sync your projects to QField on android
                             -------------------
        begin                : 2020-08-01
        git sha              : $Format:%H$
        copyright            : (C) 2020 by OPENGIS.ch
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

from PyQt5.QtCore import QObject
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
from qgis.PyQt.uic import loadUiType


from qfieldsync.core.cloud_api import ProjectTransferrer


QFieldCloudTransferDialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/qfield_cloud_transfer_dialog.ui'))


class QFieldCloudTransferDialog(QDialog, QFieldCloudTransferDialogUi):

    def __init__(self, project_transfer: ProjectTransferrer, parent: QObject = None):
        """Constructor.
        """
        super(QFieldCloudTransferDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.project_transfer = project_transfer

        self.project_transfer.error.connect(self.on_error)
        self.project_transfer.upload_progress.connect(self.on_upload_transfer_progress)
        self.project_transfer.download_progress.connect(self.on_download_transfer_progress)
        self.project_transfer.finished.connect(self.on_transfer_finished)

        self.setWindowTitle(self.tr('Synchronizing project "%1"').arg(self.project_transfer.cloud_project.name))
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

        self.uploadProgressBar.setValue(0)
        self.downloadProgressBar.setValue(0)


    def on_error(self, error: str) -> None:
        self.errorLabel.setText(self.errorLabel.text() + '\n' + error)

    
    def on_upload_transfer_progress(self, fraction) -> None:
        self.uploadProgressBar.setValue(fraction * 100)


    def on_download_transfer_progress(self, fraction: float) -> None:
        self.uploadProgressBar.setValue(fraction * 100)


    def on_transfer_finished(self, fraction: float) -> None:
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Abort).setEnabled(False)
