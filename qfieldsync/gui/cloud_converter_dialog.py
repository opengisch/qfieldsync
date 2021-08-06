# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldCloudConverterDialog
                                 A QGIS plugin
 Sync your projects to QField on android
                             -------------------
        begin                : 2021-057-22
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

import os
import re
from pathlib import Path
from typing import Optional

from qgis.core import Qgis, QgsProject, QgsProviderRegistry
from qgis.PyQt.QtCore import QDir, Qt
from qgis.PyQt.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.cloud_api import CloudException, from_reply
from qfieldsync.core.cloud_converter import CloudConverter
from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.core.cloud_transferrer import CloudTransferrer
from qfieldsync.core.preferences import Preferences
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.libqfieldsync.utils.file_utils import fileparts

from ..utils.qt_utils import make_folder_selector

DialogUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/cloud_converter_dialog.ui")
)


class CloudConverterDialog(QDialog, DialogUi):
    def __init__(self, iface, network_manager, project, parent=None):
        """Constructor."""
        super(CloudConverterDialog, self).__init__(parent=parent)
        self.setupUi(self)

        self.iface = iface
        self.project = project
        self.qfield_preferences = Preferences()
        self.network_manager = network_manager
        self.cloud_transferrer: Optional[CloudTransferrer] = None

        if not self.network_manager.has_token():
            CloudLoginDialog.show_auth_dialog(
                self.network_manager, lambda: self.close(), None, parent=self
            )
        else:
            self.network_manager.projects_cache.refresh()

        project_name = self.project.baseName()
        if project_name:
            pattern = re.compile(r"[\W_]+")
            project_name = pattern.sub("", project_name)
        else:
            project_name = "CloudProject"
        self.mProjectName.setText(project_name)
        self.button_box.button(QDialogButtonBox.Save).setText(self.tr("Create"))
        self.button_box.button(QDialogButtonBox.Save).clicked.connect(
            self.convert_project
        )

        self.projectGroupBox.setVisible(True)
        self.progressGroupBox.setVisible(False)

        self.setup_gui()

    def setup_gui(self):
        """Populate gui and connect signals of the push dialog"""
        project_filename = QgsProject.instance().fileName()
        export_dirname = Path(self.qfield_preferences.value("cloudDirectory")).joinpath(
            fileparts(project_filename)[1] if project_filename else "new_cloud_project"
        )

        self.exportDirLineEdit.setText(QDir.toNativeSeparators(str(export_dirname)))
        self.exportDirButton.clicked.connect(
            make_folder_selector(self.exportDirLineEdit)
        )
        self.update_info_visibility()

    def get_export_folder_from_dialog(self):
        """Get the export folder according to the inputs in the selected"""
        return self.exportDirLineEdit.text()

    def convert_project(self):
        for cloud_project in self.network_manager.projects_cache.projects:
            if cloud_project.name == self.mProjectName.text():
                QMessageBox.warning(
                    None,
                    self.tr("Warning"),
                    self.tr(
                        "The project name is already present in your QFieldCloud repository, please pick a different name."
                    ),
                )
                return

        if sorted(Path(self.exportDirLineEdit.text()).rglob("*.qgs")) or sorted(
            Path(self.exportDirLineEdit.text()).rglob("*.qgz")
        ):
            QMessageBox.warning(
                None,
                self.tr("Warning"),
                self.tr(
                    "The export directory already contains a project file, please pick a different directory."
                ),
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.button_box.setEnabled(False)
        self.projectGroupBox.setVisible(False)
        self.progressGroupBox.setVisible(True)

        cloud_convertor = CloudConverter(
            self.project, self.get_export_folder_from_dialog()
        )

        cloud_convertor.warning.connect(self.on_show_warning)
        cloud_convertor.total_progress_updated.connect(self.on_update_total_progressbar)

        try:
            cloud_convertor.convert()
        except Exception:
            QApplication.restoreOverrideCursor()
            critical_message = self.tr(
                "The project could not be converted into the export directory."
            )
            self.iface.messageBar().pushMessage(critical_message, Qgis.Critical, 0)
            self.close()
            return

        self.create_cloud_project()

    def create_cloud_project(self):
        pattern = re.compile(r"[\W_]+")
        project_name = pattern.sub("", self.mProjectName.text())

        reply = self.network_manager.create_project(
            project_name,
            self.network_manager.auth().config("username"),
            self.project.metadata().abstract(),
            True,
        )
        reply.finished.connect(lambda: self.on_create_project_finished(reply))

    def on_create_project_finished(self, reply):
        try:
            payload = self.network_manager.json_object(reply)
        except CloudException as err:
            QApplication.restoreOverrideCursor()
            critical_message = self.tr(
                "QFieldCloud rejected projection creation: {}"
            ).format(from_reply(err.reply))
            self.iface.messageBar().pushMessage(critical_message, Qgis.Critical, 0)
            self.close()
            return

        # save `local_dir` configuration permanently, `CloudProject` constructor does this for free
        cloud_project = CloudProject(
            {**payload, "local_dir": self.get_export_folder_from_dialog()}
        )

        self.cloud_transferrer = CloudTransferrer(self.network_manager, cloud_project)
        self.cloud_transferrer.upload_progress.connect(
            self.on_transferrer_update_progress
        )
        self.cloud_transferrer.finished.connect(self.on_transferrer_finished)
        self.cloud_transferrer.sync(list(cloud_project.files_to_sync), [], [])

    def do_post_cloud_convert_action(self):
        QApplication.restoreOverrideCursor()

        self.network_manager.projects_cache.refresh()

        result_message = self.tr(
            "Finished converting the project to QFieldCloud, you are now view its locally stored copy."
        )
        self.iface.messageBar().pushMessage(result_message, Qgis.Success, 0)
        self.close()

    def update_info_visibility(self):
        """
        Show the info label if there are unconfigured layers
        """
        pathResolver = QgsProject.instance().pathResolver()
        localizedDataPathLayers = []
        for layer in list(self.project.mapLayers().values()):
            if layer.dataProvider() is not None:
                metadata = QgsProviderRegistry.instance().providerMetadata(
                    layer.dataProvider().name()
                )
                if metadata is not None:
                    decoded = metadata.decodeUri(layer.source())
                    if "path" in decoded:
                        path = pathResolver.writePath(decoded["path"])
                        if path.startswith("localized:"):
                            localizedDataPathLayers.append(
                                "- {} ({})".format(layer.name(), path[10:])
                            )

        if localizedDataPathLayers:
            if len(localizedDataPathLayers) == 1:
                self.infoLocalizedLayersLabel.setText(
                    self.tr("The layer stored in a localized data path is:\n{}").format(
                        "\n".join(localizedDataPathLayers)
                    )
                )
            else:
                self.infoLocalizedLayersLabel.setText(
                    self.tr(
                        "The layers stored in a localized data path are:\n{}"
                    ).format("\n".join(localizedDataPathLayers))
                )
            self.infoLocalizedLayersLabel.setVisible(True)
            self.infoLocalizedPresentLabel.setVisible(True)
        else:
            self.infoLocalizedLayersLabel.setVisible(False)
            self.infoLocalizedPresentLabel.setVisible(False)
        self.infoGroupBox.setVisible(len(localizedDataPathLayers) > 0)

    def on_update_total_progressbar(self, current, layer_count, message):
        self.totalProgressBar.setMaximum(layer_count)
        self.totalProgressBar.setValue(current)

    def on_transferrer_update_progress(self, fraction):
        self.uploadProgressBar.setMaximum(100)
        self.uploadProgressBar.setValue(int(fraction * 100))

    def on_transferrer_finished(self):
        self.do_post_cloud_convert_action()

    def on_show_warning(self, _, message):
        self.iface.messageBar().pushMessage(message, Qgis.Warning, 0)
