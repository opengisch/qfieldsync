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

    def __init__(self, upload_transfer: ProjectTransferrer, download_transfer: ProjectTransferrer, parent: QObject = None):
        """Constructor.
        """
        super(QFieldCloudTransferDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.upload_transfer = upload_transfer
        self.download_transfer = download_transfer

        self.upload_transfer.progress.connect(self.on_upload_transfer_progress)
        self.upload_transfer.finished.connect(self.on_upload_transfer_finished)
        self.upload_transfer.error.connect(self.on_error)
        self.download_transfer.progress.connect(self.on_download_transfer_progress)
        self.download_transfer.finished.connect(self.on_download_transfer_finished)
        self.download_transfer.error.connect(self.on_error)

        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        self.uploadProgressBar.setValue(0)
        self.downloadProgressBar.setValue(0)


    def on_error(self, error: str) -> None:
        self.errorLabel.setText(self.errorLabel.text() + '\n' + error)

    
    def on_upload_transfer_progress(self, fraction) -> None:
        self.uploadProgressBar.setValue(fraction * 100)


    def on_upload_transfer_finished(self) -> None:
        self.uploadProgressBar.setValue(100)


    def on_download_transfer_progress(self, fraction: float) -> None:
        self.uploadProgressBar.setValue(fraction * 100)


    def on_download_transfer_finished(self, fraction: float) -> None:
        self.downloadProgressBar.setValue(100)
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        self.buttonBox.button(QDialogButtonBox.Abort).setEnabled(False)
