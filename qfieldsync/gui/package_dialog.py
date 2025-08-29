# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSyncDialog
                                 A QGIS plugin
 Sync your projects to QField
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
import os
from pathlib import Path
from typing import Optional

from libqfieldsync.layer import LayerSource
from libqfieldsync.offline_converter import (
    ExportType,
    OfflineConverter,
    PackagingCanceledError,
)

# TODO this try/catch was added due to module structure changes in QFS 4.8.0. Remove this as enough time has passed since March 2024.
try:
    from libqfieldsync.offliners import QgisCoreOffliner
except ModuleNotFoundError:
    from qgis.PyQt.QtCore import QCoreApplication
    from qgis.PyQt.QtWidgets import QMessageBox

    QMessageBox.warning(
        None,
        QCoreApplication.translate("QFieldSync", "Please restart QGIS"),
        QCoreApplication.translate(
            "QFieldSync", "To finalize the QFieldSync upgrade, please restart QGIS."
        ),
    )
from libqfieldsync.project import ProjectConfiguration
from libqfieldsync.project_checker import ProjectChecker
from libqfieldsync.utils.file_utils import fileparts
from libqfieldsync.utils.qgis import get_project_title
from qgis.core import Qgis, QgsApplication, QgsProject
from qgis.PyQt.QtCore import QDir, Qt, QUrl
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.preferences import Preferences
from qfieldsync.gui.checker_feedback_table import CheckerFeedbackTable
from qfieldsync.gui.dirs_to_copy_widget import DirsToCopyWidget
from qfieldsync.gui.project_configuration_dialog import ProjectConfigurationDialog

MAX_LENGTH_CHARS_FILEPATH = 200

DialogUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/package_dialog.ui")
)


class PackageDialog(QDialog, DialogUi):
    _offline_convertor: Optional[OfflineConverter] = None

    def __init__(self, iface, project, offline_editing, parent=None):
        """Constructor."""
        super(PackageDialog, self).__init__(parent=parent)
        self.setupUi(self)

        self.iface = iface
        self.offliner = QgisCoreOffliner(offline_editing=offline_editing)
        self.project = project
        self.qfield_preferences = Preferences()
        self.dirsToCopyWidget = DirsToCopyWidget()
        self.__project_configuration = ProjectConfiguration(self.project)
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setText(
            self.tr("Create")
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Save).clicked.connect(
            self.package_project
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Reset).setText(
            self.tr("Configure current project...")
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Reset).setIcon(
            QIcon(
                os.path.join(
                    os.path.dirname(__file__), "../resources/project_properties.svg"
                )
            )
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(
            self.show_settings
        )

        self.devices = None
        self.project_checker = ProjectChecker(QgsProject.instance())
        # self.refresh_devices()
        self.setup_gui()

        self.offliner.warning.connect(self.show_warning)

        self.rejected.connect(self.cancel)

    def update_progress(self, sent, total):
        progress = float(sent) / total * 100
        self.progress_bar.setValue(progress)

    def cancel(self) -> None:
        """
        Cancels an ongoing packaging export, if there is any running.
        Typically used when the user rejects the dialog.
        """
        if self._offline_convertor:
            self._offline_convertor.cancel()

    def setup_gui(self):
        """Populate gui and connect signals of the push dialog"""
        self.packagedProjectTitleLineEdit.setText(get_project_title(self.project))
        self.packagedProjectFileWidget.setFilter("QGIS Project Files (*.qgs)")
        self.packagedProjectFileWidget.setConfirmOverwrite(True)
        self.packagedProjectFileWidget.setFilePath(
            self.get_export_filename_suggestion()
        )

        self.packagedProjectFileWidget.lineEdit().textChanged.connect(
            self._validate_packaged_project_filename
        )
        self.packagedProjectFileFeedbackLabel.setStyleSheet("color: red;")
        self.packagedProjectFileFeedbackLabel.setWordWrap(True)
        self.packagedProjectFileFeedbackLabel.hide()

        self.update_info_visibility()

        self.nextButton.clicked.connect(lambda: self.show_package_page())
        self.nextButton.setVisible(False)
        self.button_box.setVisible(False)

        self.advancedOptionsGroupBox.layout().addWidget(self.dirsToCopyWidget)

        self.dirsToCopyWidget.set_path(QgsProject().instance().homePath())
        self.dirsToCopyWidget.refresh_tree()

        feedback = None
        if os.path.exists(self.project.fileName()):
            feedback = self.project_checker.check(ExportType.Cable)

        if feedback and feedback.count > 0:
            has_errors = len(feedback.error_feedbacks) > 0

            feedback_table = CheckerFeedbackTable(feedback)
            self.feedbackTableWrapperLayout.addWidget(feedback_table)
            self.stackedWidget.setCurrentWidget(self.projectCompatibilityPage)
            self.nextButton.setVisible(True)
            self.nextButton.setEnabled(not has_errors)
        else:
            self.show_package_page()

    def get_export_filename_suggestion(self) -> str:
        """Get the suggested export filename"""
        export_dirname = self.qfield_preferences.value("exportDirectoryProject")
        if not export_dirname:
            export_dirname = os.path.join(
                self.qfield_preferences.value("exportDirectory"),
                fileparts(QgsProject.instance().fileName())[1],
            )
        export_folder = Path(QDir.toNativeSeparators(str(export_dirname)))
        full_project_name_suggestion = export_folder.joinpath(
            f"{self.project.baseName()}_qfield.qgs"
        )
        return str(full_project_name_suggestion)

    def show_package_page(self):
        self.nextButton.setVisible(False)
        self.button_box.setVisible(True)
        self.stackedWidget.setCurrentWidget(self.packagePage)

    def _validate_packaged_project_filename(self) -> None:
        """Check multiple conditions for the packaged project file and show feedback."""
        export_packaged_project = Path(self.packagedProjectFileWidget.filePath())
        feedback_messages = []

        if export_packaged_project.suffix.lower() != ".qgs":
            feedback_messages.append(
                self.tr('The filename must have a ".qgs" extension')
            )

        if len(export_packaged_project.as_posix()) > MAX_LENGTH_CHARS_FILEPATH:
            feedback_messages.append(
                self.tr(
                    "Warning: File path exceeds 200 characters. "
                    "Longer paths may not be handled properly by your file system."
                )
            )

        feedback_text = "\n".join(feedback_messages)
        self.packagedProjectFileFeedbackLabel.setText(feedback_text)
        self.packagedProjectFileFeedbackLabel.setVisible(bool(feedback_text))

        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(
            not feedback_messages
        )

    def package_project(self):
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

        packaged_project_file = Path(self.packagedProjectFileWidget.filePath())
        area_of_interest = (
            self.__project_configuration.area_of_interest
            if self.__project_configuration.area_of_interest
            else self.iface.mapCanvas().extent().asWktPolygon()
        )
        area_of_interest_crs = (
            self.__project_configuration.area_of_interest_crs
            if self.__project_configuration.area_of_interest_crs
            else QgsProject.instance().crs().authid()
        )

        self.qfield_preferences.set_value(
            "exportDirectoryProject", str(packaged_project_file.parent)
        )
        self.dirsToCopyWidget.save_settings()

        self._offline_convertor = OfflineConverter(
            self.project,
            packaged_project_file,
            area_of_interest,
            area_of_interest_crs,
            self.qfield_preferences.value("attachmentDirs"),
            self.offliner,
            ExportType.Cable,
            dirs_to_copy=self.dirsToCopyWidget.dirs_to_copy(),
            export_title=self.packagedProjectTitleLineEdit.text(),
        )

        # progress connections
        self._offline_convertor.total_progress_updated.connect(self.update_total)
        self._offline_convertor.task_progress_updated.connect(self.update_task)
        self._offline_convertor.warning.connect(
            lambda title, body: QMessageBox.warning(None, title, body)
        )

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self._offline_convertor.convert()
            self.do_post_offline_convert_action(True)
        except PackagingCanceledError:
            # packaging was canceled by user, we do nothing.
            return
        except Exception as err:
            self.do_post_offline_convert_action(False)
            raise err
        finally:
            QApplication.restoreOverrideCursor()
            self._offline_convertor = None

        self.accept()

        self.progress_group.setEnabled(False)

    def do_post_offline_convert_action(self, is_success):
        """
        Show an information label that the project has been copied
        with a nice link to open the result folder.
        """
        if is_success:
            export_folder = str(Path(self.packagedProjectFileWidget.filePath()).parent)
            result_message = self.tr(
                "Finished creating the project at {result_folder}. Please copy this folder to "
                "your QField device."
            ).format(
                result_folder='<a href="{folder}">{display_folder}</a>'.format(
                    folder=QUrl.fromLocalFile(export_folder).toString(),
                    display_folder=QDir.toNativeSeparators(export_folder),
                )
            )
            status = Qgis.Success
        else:
            result_message = self.tr(
                "Failed to package project. See message log (Python Error) for more details."
            )
            status = Qgis.Warning

        self.iface.messageBar().pushMessage(result_message, status, 0)

    def update_info_visibility(self):
        """
        Show the info label if there are unconfigured layers
        """
        localizedDataPathLayers = []
        for layer in list(self.project.mapLayers().values()):
            layer_source = LayerSource(layer)

            if layer_source.is_localized_path:
                localizedDataPathLayers.append("- {}".format(layer.name()))

        if localizedDataPathLayers:
            self.infoLocalizedLayersLabel.setText(
                self.tr(
                    "The current project relies on %n shared dataset(s), make sure to copy them into the shared datasets path of devices running QField. The layer(s) stored in a shared dataset(s) are:\n{}",
                    "",
                    len(localizedDataPathLayers),
                ).format("\n".join(localizedDataPathLayers))
            )

            self.infoLocalizedLayersLabel.setVisible(True)
        else:
            self.infoLocalizedLayersLabel.setVisible(False)
        self.infoGroupBox.setVisible(len(localizedDataPathLayers) > 0)

    def show_settings(self):
        if Qgis.QGIS_VERSION_INT >= 31500:
            self.iface.showProjectPropertiesDialog("QField")
        else:
            dlg = ProjectConfigurationDialog(self.iface.mainWindow())
            dlg.exec_()
        self.update_info_visibility()

    def update_total(self, current, layer_count, message):
        self.totalProgressBar.setMaximum(layer_count)
        self.totalProgressBar.setValue(current)
        self.statusLabel.setText(message)

    def update_task(self, progress, max_progress):
        self.layerProgressBar.setMaximum(max_progress)
        self.layerProgressBar.setValue(progress)

    def show_warning(self, _, message):
        # Most messages from the offline editing plugin are not important enough to show in the message bar.
        # In case we find important ones in the future, we need to filter them.
        QgsApplication.instance().messageLog().logMessage(message, "QFieldSync")
