# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldCloudCreateProjectWidget
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
from pathlib import Path
from typing import Optional

from qgis.core import Qgis, QgsProject
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QRegularExpression, Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QRegularExpressionValidator
from qgis.PyQt.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QMessageBox,
    QToolButton,
    QWidget,
)
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.cloud_api import (
    CloudException,
    CloudNetworkAccessManager,
    from_reply,
)
from qfieldsync.core.cloud_converter import CloudConverter
from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.core.cloud_transferrer import CloudTransferrer
from qfieldsync.core.preferences import Preferences
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.libqfieldsync.layer import LayerSource
from qfieldsync.libqfieldsync.utils.file_utils import (
    fileparts,
    get_unique_empty_dirname,
)
from qfieldsync.libqfieldsync.utils.qgis import get_qgis_files_within_dir
from qfieldsync.utils.cloud_utils import (
    LocalDirFeedback,
    local_dir_feedback,
    to_cloud_title,
)

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/cloud_create_project_widget.ui")
)


class CloudCreateProjectWidget(QWidget, WidgetUi):
    finished = pyqtSignal()
    canceled = pyqtSignal()

    def __init__(
        self,
        iface: QgisInterface,
        network_manager: CloudNetworkAccessManager,
        project: QgsProject,
        parent: QWidget,
    ) -> None:
        """Constructor."""
        super(CloudCreateProjectWidget, self).__init__(parent=parent)
        self.setupUi(self)

        self.cloud_projects_dialog = parent
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

        self.cancelButton.clicked.connect(self.on_cancel_button_clicked)
        self.nextButton.clicked.connect(self.on_next_button_clicked)
        self.backButton.clicked.connect(self.on_back_button_clicked)
        self.createButton.clicked.connect(self.on_create_button_clicked)
        self.dirnameButton.clicked.connect(self.on_dirname_button_clicked)
        self.dirnameLineEdit.textChanged.connect(self.on_dirname_line_edit_text_changed)

        self.use_current_project_directory_action = QAction(
            QIcon(), self.tr("Use Current Project Directory")
        )
        self.use_current_project_directory_action.triggered.connect(
            self.on_use_current_project_directory_action_triggered
        )
        self.dirnameButton.setMenu(QMenu())
        self.dirnameButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.dirnameButton.menu().addAction(self.use_current_project_directory_action)

        self.projectNameLineEdit.setValidator(
            QRegularExpressionValidator(
                QRegularExpression("^[a-zA-Z][-a-zA-Z0-9_]{2,}$")
            )
        )

    def restart(self):
        self.stackedWidget.setCurrentWidget(self.selectTypePage)

        if self.network_manager.projects_cache.is_currently_open_project_cloud_local:
            self.createCloudRadioButton.setChecked(True)
            self.cloudifyRadioButton.setEnabled(False)
            self.cloudifyInfoLabel.setEnabled(False)
        else:
            self.cloudifyRadioButton.setChecked(True)
            self.cloudifyRadioButton.setEnabled(True)
            self.cloudifyInfoLabel.setEnabled(True)

    def cloudify_project(self):
        assert self.network_manager.projects_cache.projects

        for cloud_project in self.network_manager.projects_cache.projects:
            if cloud_project.name == self.get_cloud_project_name():
                QMessageBox.warning(
                    None,
                    self.tr("Warning"),
                    self.tr(
                        "The project name is already present in your QFieldCloud repository, please pick a different name."
                    ),
                )
                return

        if get_qgis_files_within_dir(self.dirnameLineEdit.text()):
            QMessageBox.warning(
                None,
                self.tr("Warning"),
                self.tr(
                    "The export directory already contains a project file, please pick a different directory."
                ),
            )
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.stackedWidget.setCurrentWidget(self.progressPage)
        self.convertProgressBar.setVisible(True)
        self.convertLabel.setVisible(True)
        self.uploadLabel.setText(self.tr("Uploading project"))

        if not self.project.title():
            self.project.setTitle(self.get_cloud_project_name())
            self.project.setDirty()

        cloud_convertor = CloudConverter(self.project, self.dirnameLineEdit.text())

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

    def get_cloud_project_name(self) -> str:
        return self.projectNameLineEdit.text()

    def create_empty_cloud_project(self):
        self.convertProgressBar.setVisible(False)
        self.convertLabel.setVisible(False)
        self.uploadLabel.setText(self.tr("Creating project"))

        self.create_cloud_project()

    def create_cloud_project(self):
        self.stackedWidget.setCurrentWidget(self.progressPage)

        if not self.project.title():
            self.project.setTitle(self.get_cloud_project_name())
            self.project.setDirty()

        reply = self.network_manager.create_project(
            self.get_cloud_project_name(),
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
                "QFieldCloud rejected project creation: {}"
            ).format(from_reply(err.reply))
            self.iface.messageBar().pushMessage(critical_message, Qgis.Critical, 0)
            self.close()
            return
        # save `local_dir` configuration permanently, `CloudProject` constructor does this for free
        cloud_project = CloudProject(
            {**payload, "local_dir": self.dirnameLineEdit.text()}
        )

        if self.createCloudRadioButton.isChecked():
            self.uploadProgressBar.setValue(100)
            self.after_project_creation_action()
        elif self.cloudifyRadioButton.isChecked():
            self.cloud_transferrer = CloudTransferrer(
                self.network_manager, cloud_project
            )
            self.cloud_transferrer.upload_progress.connect(
                self.on_transferrer_update_progress
            )
            self.cloud_transferrer.finished.connect(
                lambda: self.on_transferrer_finished()
            )
            self.cloud_transferrer.sync(list(cloud_project.files_to_sync), [], [])

    def after_project_creation_action(self):
        QApplication.restoreOverrideCursor()

        self.network_manager.projects_cache.refresh()

        result_message = self.tr(
            "Finished uploading the project to QFieldCloud, you are now viewing the locally stored copy."
        )
        self.iface.messageBar().pushMessage(result_message, Qgis.Success, 0)
        self.finished.emit()

    def update_info_visibility(self):
        """
        Show the info label if there are unconfigured layers
        """
        localizedDataPathLayers = []
        for layer in list(self.project.mapLayers().values()):
            layer_source = LayerSource(layer)
            if layer.dataProvider() is not None:
                if layer_source.is_localized_path:
                    localizedDataPathLayers.append(
                        "- {} ({})".format(layer.name(), layer_source.filename)
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

    def get_unique_project_name(self, project: QgsProject) -> str:
        project_name = to_cloud_title(QgsProject.instance().title())

        if not project_name:
            project_name = project.baseName()

        if not project_name:
            project_name = "UntitledCloudProject"

        project_name = (
            self.network_manager.projects_cache.get_unique_name(project_name) or ""
        )

        return project_name

    def set_dirname(self, dirname: str):
        if self.cloudifyRadioButton.isChecked():
            feedback, feedback_msg = local_dir_feedback(
                dirname,
                single_project_status=LocalDirFeedback.Error,
                not_existing_status=LocalDirFeedback.Success,
            )
        elif self.createCloudRadioButton.isChecked():
            feedback, feedback_msg = local_dir_feedback(
                dirname,
                no_path_status=LocalDirFeedback.Warning,
            )
        else:
            raise NotImplementedError("Unknown create new button radio.")

        self.dirnameFeedbackLabel.setText(feedback_msg)

        if feedback == LocalDirFeedback.Error:
            self.dirnameFeedbackLabel.setStyleSheet("color: red;")
            self.createButton.setEnabled(False)
        elif feedback == LocalDirFeedback.Warning:
            self.dirnameFeedbackLabel.setStyleSheet("color: orange;")
            self.createButton.setEnabled(True)
        else:
            self.dirnameFeedbackLabel.setStyleSheet("color: green;")
            self.createButton.setEnabled(True)

    def on_update_total_progressbar(self, current, layer_count, message):
        self.convertProgressBar.setMaximum(layer_count)
        self.convertProgressBar.setValue(current)

    def on_transferrer_update_progress(self, fraction):
        self.uploadProgressBar.setMaximum(100)
        self.uploadProgressBar.setValue(int(fraction * 100))

    def on_transferrer_finished(self):
        self.after_project_creation_action()

    def on_show_warning(self, _, message):
        self.iface.messageBar().pushMessage(message, Qgis.Warning, 0)

    def on_cancel_button_clicked(self):
        self.canceled.emit()

    def on_next_button_clicked(self) -> None:
        project_name = self.get_unique_project_name(self.project)

        self.stackedWidget.setCurrentWidget(self.projectDetailsPage)
        self.projectNameLineEdit.setText(project_name)
        self.projectDescriptionTextEdit.setText(self.project.metadata().abstract())

        if self.cloudifyRadioButton.isChecked():
            project_filename = (
                project_name.lower()
                if project_name
                else fileparts(QgsProject.instance().fileName())[1]
            )
            export_dirname = get_unique_empty_dirname(
                Path(self.qfield_preferences.value("cloudDirectory")).joinpath(
                    project_filename
                )
            )

            self.createButton.setEnabled(True)
            self.set_dirname(str(export_dirname))
        elif self.createCloudRadioButton.isChecked():
            if self.project.fileName():
                self.set_dirname(str(Path(self.project.fileName()).parent))

        self.update_info_visibility()

    def on_back_button_clicked(self):
        self.stackedWidget.setCurrentWidget(self.selectTypePage)

    def on_create_button_clicked(self):
        if self.cloudifyRadioButton.isChecked():
            self.infoLabel.setText(self.cloudifyInfoLabel.text())
            self.cloudify_project()
        elif self.createCloudRadioButton.isChecked():
            self.infoLabel.setText(self.createCloudInfoLabel.text())
            self.create_empty_cloud_project()

    def on_dirname_button_clicked(self):
        dirname = self.cloud_projects_dialog.select_local_dir()

        if dirname:
            self.set_dirname(dirname)
            self.dirnameLineEdit.setText(str(Path(dirname)))

    def on_dirname_line_edit_text_changed(self, text: str):
        self.set_dirname(self.dirnameLineEdit.text())

    def on_use_current_project_directory_action_triggered(self):
        self.dirnameLineEdit.setText(str(Path(self.project.fileName()).parent))
