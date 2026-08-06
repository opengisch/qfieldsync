"""
/***************************************************************************
 QFieldSync
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2021-07-22
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

from libqfieldsync.layer import LayerSource
from libqfieldsync.offline_converter import ExportType
from libqfieldsync.project_checker import ProjectChecker
from qgis.core import QgsApplication, QgsProject
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QDir, QRegularExpression, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices, QIcon, QRegularExpressionValidator
from qgis.PyQt.QtWidgets import (
    QAction,
    QApplication,
    QMenu,
    QToolButton,
    QWidget,
)
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.cloud_api import CloudNetworkAccessManager, QfcError
from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.core.preferences import Preferences
from qfieldsync.gui.checker_feedback_table import CheckerFeedbackTable
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.gui.storage_widget import StorageWidget
from qfieldsync.utils.cloud_utils import (
    LocalDirFeedback,
    local_dir_feedback,
    to_cloud_title,
)

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/cloud_create_project_widget.ui")
)


class CloudCreateProjectWidget(QWidget, WidgetUi):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    canceled = pyqtSignal()

    def __init__(
        self,
        iface: QgisInterface,
        network_manager: CloudNetworkAccessManager,
        project: QgsProject,
        parent: QWidget,
    ) -> None:
        """Constructor."""
        super().__init__(parent=parent)
        self.setupUi(self)

        self.cloud_projects_dialog = parent
        self.iface = iface
        self.project = project
        self.qfield_preferences = Preferences()
        self.network_manager = network_manager
        self.project_checker = ProjectChecker(self.project)

        if not self.network_manager.is_authenticated():
            CloudLoginDialog.show_auth_dialog(
                self.network_manager, lambda: self.close(), None, parent=self
            )
        else:
            self.network_manager.projects_cache.refresh()

        self.cancelButton.clicked.connect(self.on_cancel_button_clicked)
        self.nextButton.clicked.connect(self.on_next_button_clicked)

        self.backButton.clicked.connect(self.on_back_button_clicked)
        self.createButton.clicked.connect(self.on_create_button_clicked)

        self.localDirButton.clicked.connect(self.on_local_dir_button_clicked)
        self.localDirLineEdit.textChanged.connect(
            self.on_dirname_line_edit_text_changed
        )

        self.use_current_project_directory_action = QAction(
            QIcon(), self.tr("Use Current Project Directory")
        )
        self.use_current_project_directory_action.triggered.connect(
            self.on_use_current_project_directory_action_triggered
        )
        self.localDirButton.setMenu(QMenu())
        self.localDirButton.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.localDirButton.menu().addAction(self.use_current_project_directory_action)

        self.localDirOpenButton.clicked.connect(self.on_local_dir_open_button_clicked)
        self.localDirOpenButton.setIcon(
            QgsApplication.getThemeIcon("/mActionFileOpen.svg")
        )

        self.projectNameLineEdit.setValidator(
            QRegularExpressionValidator(
                QRegularExpression("^[a-zA-Z][-a-zA-Z0-9_]{2,}$")
            )
        )

        self.projectOwnerComboBox.currentTextChanged.connect(
            lambda: self.on_project_owner_changed()
        )

        self.projectOwnerRefreshButton.clicked.connect(
            lambda: self.on_project_owner_refresh_button_click()
        )

        self.storage_widget = StorageWidget(self.network_manager, self)
        self.projectDetailsLayout.addWidget(self.storage_widget, 5, 1)

        if self.network_manager.is_authenticated():
            self.setup_checker_page()

    def restart(self):
        self.stackedWidget.setCurrentWidget(self.projectCompatibilityPage)
        if self.network_manager.is_authenticated():
            self.setup_checker_page()

    def setup_checker_page(self) -> None:
        """Runs ProjectChecker and builds the feedback table"""
        if not self.network_manager.is_authenticated():
            return

        while self.checkerTableLayout.count():
            child = self.checkerTableLayout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        feedback = None
        if os.path.exists(self.project.fileName()):
            feedback = self.project_checker.check(ExportType.Cloud)

        if feedback and feedback.count > 0:
            has_errors = len(feedback.error_feedbacks) > 0

            feedback_table = CheckerFeedbackTable(
                feedback, self.projectCompatibilityPage
            )
            self.checkerTableLayout.addWidget(feedback_table)
            self.stackedWidget.setCurrentWidget(self.projectCompatibilityPage)

            self.nextButton.setEnabled(not has_errors)
            if has_errors:
                self.nextButton.setToolTip(
                    self.tr("Please fix critical project errors before continuing.")
                )
            else:
                self.nextButton.setToolTip("")
        else:
            self.setup_project_details_page()

    def setup_project_details_page(self) -> None:
        """Initializes values on projectDetailsPage"""
        if not self.network_manager.is_authenticated():
            return

        project_name = self.get_unique_project_name(self.project)

        self.stackedWidget.setCurrentWidget(self.projectDetailsPage)
        self.projectNameLineEdit.setText(project_name)
        self.projectDescriptionTextEdit.setText(self.project.metadata().abstract())

        self.refresh_project_owners()

        if self.project.fileName():
            default_dir = str(Path(self.project.fileName()).parent)
        else:
            default_dir = self.qfield_preferences.value("cloudDirectory") or str(
                Path.home()
            )

        self.set_dirname(default_dir)
        self.update_info_visibility()

    def update_info_visibility(self) -> None:
        """Show the info label if there are unconfigured/localized layers."""
        localized_data_path_layers = []
        for layer in list(self.project.mapLayers().values()):
            layer_source = LayerSource(layer)
            if layer.dataProvider() is not None:
                if layer_source.is_localized_path:
                    localized_data_path_layers.append("- {}".format(layer.name()))

        if localized_data_path_layers:
            self.infoLocalizedLayersLabel.setText(
                self.tr(
                    "The current project relies on %n shared dataset(s), make sure to copy them into the shared datasets path of devices running QField. The layer(s) stored in a shared dataset(s) are:\n{}",
                    "",
                    len(localized_data_path_layers),
                ).format("\n".join(localized_data_path_layers))
            )
            self.infoLocalizedLayersLabel.setVisible(True)
        else:
            self.infoLocalizedLayersLabel.setVisible(False)

        self.infoGroupBox.setVisible(len(localized_data_path_layers) > 0)

    def on_next_button_clicked(self) -> None:
        """Navigates from compatibility Checks to project details"""
        self.setup_project_details_page()

    def on_back_button_clicked(self) -> None:
        """Navigates from project details back to compatibility checks"""
        self.stackedWidget.setCurrentWidget(self.projectCompatibilityPage)

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

        description = (
            self.projectDescriptionTextEdit.toPlainText()
            or self.project.metadata().abstract()
        )
        reply = self.network_manager.create_project(
            self.get_cloud_project_name(),
            self.projectOwnerComboBox.currentText(),
            description,
            self.projectIsPublicCheckBox.isChecked(),
        )
        reply.finished.connect(lambda: self.on_create_project_finished(reply))

    def on_create_project_finished(self, reply):
        try:
            payload = self.network_manager.json_object(reply)
        except QfcError as err:
            QApplication.restoreOverrideCursor()
            critical_message = self.tr(
                "QFieldCloud rejected project creation:\n{}"
            ).format(err)
            self.error.emit(critical_message)
            self.stackedWidget.setCurrentWidget(self.projectDetailsPage)
            return
        # save `local_dir` configuration permanently, `CloudProject` constructor does this for free

        cloud_project = CloudProject(
            {**payload, "local_dir": self.localDirLineEdit.text()}
        )

        self.uploadProgressBar.setValue(100)
        self.after_project_creation_action(cloud_project.id)

    def after_project_creation_action(self, project_id: str):
        QApplication.restoreOverrideCursor()
        self.network_manager.projects_cache.refresh()
        self.finished.emit(project_id)

    def get_unique_project_name(self, project: QgsProject) -> str:
        project_name = QgsProject.instance().title()

        if not project_name:
            project_name = project.baseName()

        if not project_name:
            project_name = "UntitledCloudProject"

        project_name = (
            self.network_manager.projects_cache.get_unique_name(project_name) or ""
        )

        return to_cloud_title(project_name)

    def set_dirname(self, dirname: str):
        feedback, feedback_msg = local_dir_feedback(
            dirname,
            no_path_status=LocalDirFeedback.Warning,
        )

        self.localDirFeedbackLabel.setText(feedback_msg)
        self.localDirFeedbackLabel.setVisible(bool(feedback_msg))

        if feedback == LocalDirFeedback.Error:
            self.localDirFeedbackLabel.setStyleSheet("color: red;")
            self.createButton.setEnabled(False)
        elif feedback == LocalDirFeedback.Warning:
            self.localDirFeedbackLabel.setStyleSheet("color: orange;")
            self.createButton.setEnabled(True)
        else:
            self.localDirFeedbackLabel.setStyleSheet("color: green;")
            self.createButton.setEnabled(True)

        self.localDirLineEdit.setText(QDir.toNativeSeparators(dirname))

    def refresh_project_owners(self):
        username = self.network_manager.get_username()
        if not username or not self.network_manager.is_authenticated():
            return

        self.projectOwnerComboBox.setEnabled(False)
        self.projectOwnerComboBox.clear()
        self.projectOwnerComboBox.addItem(username)
        self.projectOwnerRefreshButton.setEnabled(False)
        self.projectOwnerFeedbackLabel.setVisible(False)

        reply = self.network_manager.get_user_organizations(username)
        reply.finished.connect(lambda: self.on_refresh_project_owners_finished(reply))

    def on_refresh_project_owners_finished(self, reply):
        items = [
            self.network_manager.get_username(),
        ]
        try:
            payload = self.network_manager.json_array(reply)
            for org in payload:
                items.append(org["username"])
        except QfcError:
            self.projectOwnerFeedbackLabel.setVisible(True)
            self.projectOwnerFeedbackLabel.setText(
                self.tr("Failed to obtain the potential project owners.")
            )

        self.projectOwnerComboBox.clear()
        self.projectOwnerComboBox.addItems(items)
        self.projectOwnerComboBox.setEnabled(True)
        self.projectOwnerRefreshButton.setEnabled(True)

    def on_cancel_button_clicked(self):
        self.canceled.emit()

    def on_project_owner_changed(self):
        if not self.projectOwnerComboBox.currentText():
            return

        if self.storage_widget.owner() != self.projectOwnerComboBox.currentText():
            self.storage_widget.set_owner(self.projectOwnerComboBox.currentText())

    def on_project_owner_refresh_button_click(self):
        self.refresh_project_owners()

    def on_create_button_clicked(self):
        self.infoLabel.setText(
            self.tr(
                "A new blank QFieldCloud project will be created. Project files will only be uploaded when you click the synchronize button."
            )
        )
        self.create_empty_cloud_project()

    def on_local_dir_button_clicked(self):
        dirname = self.cloud_projects_dialog.select_local_dir()

        if dirname:
            self.set_dirname(dirname)
            self.localDirLineEdit.setText(str(Path(dirname)))

    def on_dirname_line_edit_text_changed(self, _text: str):
        local_dir = self.localDirLineEdit.text()
        self.localDirOpenButton.setEnabled(bool(local_dir) and Path(local_dir).exists())
        self.set_dirname(local_dir)

    def on_use_current_project_directory_action_triggered(self):
        self.localDirLineEdit.setText(str(Path(self.project.fileName()).parent))

    def on_local_dir_open_button_clicked(self) -> None:
        dirname = self.localDirLineEdit.text()
        if dirname and Path(dirname).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(dirname))
