# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
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

from qgis.core import Qgis, QgsApplication, QgsOfflineEditing, QgsProject
from qgis.gui import QgsGui, QgsOptionsWidgetFactory
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QSettings, Qt, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from qfieldsync.core import Preferences
from qfieldsync.core.cloud_api import CloudNetworkAccessManager
from qfieldsync.gui.cloud_browser_tree import (
    QFieldCloudItemGuiProvider,
    QFieldCloudItemProvider,
)
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.gui.cloud_projects_dialog import CloudProjectsDialog
from qfieldsync.gui.cloud_transfer_dialog import CloudTransferDialog
from qfieldsync.gui.map_layer_config_widget import MapLayerConfigWidgetFactory
from qfieldsync.gui.package_dialog import PackageDialog
from qfieldsync.gui.preferences_widget import PreferencesWidget
from qfieldsync.gui.project_configuration_dialog import ProjectConfigurationDialog
from qfieldsync.gui.project_configuration_widget import ProjectConfigurationWidget
from qfieldsync.gui.synchronize_dialog import SynchronizeDialog


class QFieldSyncProjectPropertiesFactory(QgsOptionsWidgetFactory):
    """
    Factory class for QFieldSync project properties widget
    """

    def __init__(self):
        super().__init__()

    def icon(self):
        return QIcon(
            os.path.join(os.path.dirname(__file__), "resources", "qfield_logo.svg")
        )

    def createWidget(self, parent):
        return ProjectConfigurationWidget(parent)


class QFieldSyncOptionsFactory(QgsOptionsWidgetFactory):
    def __init__(self):
        super(QgsOptionsWidgetFactory, self).__init__()

    def icon(self):
        return QIcon(
            os.path.join(os.path.dirname(__file__), "resources", "qfield_logo.svg")
        )

    def createWidget(self, parent):
        return PreferencesWidget(parent)


class QFieldSync(object):
    """QGIS Plugin Implementation."""

    QFIELD_SCOPE = "QFieldSync"

    push_dlg = None

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale_str = QSettings().value("locale/userLocale")
        if isinstance(locale_str, str):
            locale = QLocale(locale_str)
        else:
            locale = QLocale()

        locale_path = os.path.join(self.plugin_dir, "i18n")
        self.translator = QTranslator()
        self.translator.load(locale, "qfieldsync", "_", locale_path)

        QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&QFieldSync")
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar("QFieldSync")
        self.toolbar.setObjectName("QFieldSync")

        # instance of the map config widget factory, shown in layer properties
        self.mapLayerConfigWidgetFactory = MapLayerConfigWidgetFactory(
            "QField",
            QIcon(os.path.join(os.path.dirname(__file__), "resources/qfield_logo.svg")),
        )

        # instance of the QgsOfflineEditing
        self.offline_editing = QgsOfflineEditing()
        self.preferences = Preferences()

        QgsProject.instance().readProject.connect(self.update_button_enabled_status)
        QgsProject.instance().cleared.connect(self.update_button_enabled_status)

        # store warnings from last run
        self.last_action_warnings = []

        self.network_manager = CloudNetworkAccessManager(self.iface.mainWindow())
        self.network_manager.projects_cache.projects_updated.connect(
            self.update_button_enabled_status
        )

        self.cloud_item_provider = QFieldCloudItemProvider(self.network_manager)
        QgsApplication.instance().dataItemProviderRegistry().addProvider(
            self.cloud_item_provider
        )
        self.cloud_item_gui_provider = QFieldCloudItemGuiProvider(self.network_manager)
        QgsGui.instance().dataItemGuiProviderRegistry().addProvider(
            self.cloud_item_gui_provider
        )

        # autologin
        if self.preferences.value("qfieldCloudRememberMe"):
            self.network_manager.auto_login_attempt()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("QFieldSync", message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
        separator_before: bool = False,
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :param separator_before: Optionally adds a separator before the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            if separator_before:
                self.toolbar.addSeparator()
            self.toolbar.addAction(action)

        if add_to_menu:
            if separator_before:
                self.get_qfield_action().menu().addSeparator()
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.cloud_projects_overview_action = self.add_action(
            os.path.join(os.path.dirname(__file__), "./resources/cloud.svg"),
            text=self.tr("QFieldCloud Projects Overview"),
            callback=self.show_cloud_overview_dialog,
            parent=self.iface.mainWindow(),
        )

        self.cloud_synchronize_action = self.add_action(
            QIcon(
                os.path.join(
                    os.path.dirname(__file__), "resources/cloud_synchronize.svg"
                )
            ),
            text=self.tr("Synchronize Current Cloud Project"),
            callback=self.open_cloud_synchronize_dialog,
            parent=self.iface.mainWindow(),
        )

        self.push_action = self.add_action(
            QIcon(os.path.join(os.path.dirname(__file__), "resources/package.svg")),
            text=self.tr("Package for QField"),
            callback=self.show_package_dialog,
            parent=self.iface.mainWindow(),
            separator_before=True,
        )

        self.sync_action = self.add_action(
            QIcon(os.path.join(os.path.dirname(__file__), "resources/synchronize.svg")),
            text=self.tr("Synchronize from QField"),
            callback=self.show_synchronize_dialog,
            parent=self.iface.mainWindow(),
        )

        self.add_action(
            QIcon(
                os.path.join(
                    os.path.dirname(__file__), "./resources/project_properties.svg"
                )
            ),
            text=self.tr("Configure Current Project"),
            callback=self.show_project_configuration_dialog,
            parent=self.iface.mainWindow(),
            separator_before=True,
        )

        self.add_action(
            QgsApplication.getThemeIcon("/mActionOptions.svg"),
            text=self.tr("Preferences"),
            callback=self.show_preferences_dialog,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False,
            separator_before=True,
        )

        self.iface.registerMapLayerConfigWidgetFactory(self.mapLayerConfigWidgetFactory)

        if Qgis.QGIS_VERSION_INT >= 31500:
            self.project_properties_factory = QFieldSyncProjectPropertiesFactory()
            self.project_properties_factory.setTitle("QField")
            self.iface.registerProjectPropertiesWidgetFactory(
                self.project_properties_factory
            )
        self.options_factory = QFieldSyncOptionsFactory()
        self.options_factory.setTitle(self.tr("QField"))
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        self.update_button_enabled_status()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar
        QgsApplication.instance().dataItemProviderRegistry().removeProvider(
            self.cloud_item_provider
        )
        QgsGui.instance().dataItemGuiProviderRegistry().removeProvider(
            self.cloud_item_gui_provider
        )
        self.cloud_item_gui_provider = None

        self.iface.unregisterMapLayerConfigWidgetFactory(
            self.mapLayerConfigWidgetFactory
        )

        if Qgis.QGIS_VERSION_INT >= 31500:
            self.iface.unregisterProjectPropertiesWidgetFactory(
                self.project_properties_factory
            )
        self.iface.unregisterOptionsWidgetFactory(self.options_factory)

    def show_preferences_dialog(self):
        self.iface.showOptionsDialog(
            self.iface.mainWindow(), currentPage="QFieldPreferences"
        )

    def show_synchronize_dialog(self):
        """
        Synchronize from QField
        """
        dlg = SynchronizeDialog(
            self.iface, self.offline_editing, self.iface.mainWindow()
        )
        dlg.show()

    def open_cloud_synchronize_dialog(self):
        if not self.network_manager.has_token():
            CloudLoginDialog.show_auth_dialog(
                self.network_manager, lambda: self.show_cloud_synchronize_dialog()
            )
        else:
            self.show_cloud_synchronize_dialog()

    def show_cloud_synchronize_dialog(self, firstTry=True):
        """
        Synchornize cloud project.
        """
        if self.network_manager.projects_cache.is_currently_open_project_cloud_local:
            self.transfer_dialog = CloudTransferDialog.show_transfer_dialog(
                self.network_manager,
                None,
                None,
                None,
                self.iface.mainWindow(),
            )

    def show_package_dialog(self):
        """
        Package to QField
        """
        self.push_dlg = PackageDialog(
            self.iface,
            QgsProject.instance(),
            self.offline_editing,
            self.iface.mainWindow(),
        )
        self.push_dlg.setAttribute(Qt.WA_DeleteOnClose)
        self.push_dlg.setWindowFlags(self.push_dlg.windowFlags() | Qt.Tool)
        self.push_dlg.show()

        self.push_dlg.finished.connect(self.push_dialog_finished)
        self.update_button_enabled_status()

    def show_project_configuration_dialog(self):
        """
        Show the project configuration dialog.
        """
        if Qgis.QGIS_VERSION_INT >= 31500:
            self.iface.showProjectPropertiesDialog("QField")
        else:
            dlg = ProjectConfigurationDialog(self.iface.mainWindow())
            dlg.show()

    def show_cloud_overview_dialog(self):
        """
        Show the QFieldCloud overview dialog.
        """
        dlg = CloudProjectsDialog(self.network_manager, self.iface.mainWindow())
        dlg.show()

    def show_cloud_project_details_dialog(self):
        """
        Show the QFieldCloud project details dialog.
        """
        currently_open_project = (
            self.network_manager.projects_cache.currently_open_project
        )
        dlg = CloudProjectsDialog(
            self.network_manager, self.iface.mainWindow(), currently_open_project
        )
        dlg.show_project_form()

    def sync_qfieldcloud_project(self):
        """Synchronize the current QFieldCloud project"""
        currently_open_project = (
            self.network_manager.projects_cache.currently_open_project
        )

        if currently_open_project is None or not self.network_manager.has_token():
            self.show_cloud_overview_dialog()
            return

        dlg = CloudProjectsDialog(
            self.network_manager,
            self.iface.mainWindow(),
            project=currently_open_project,
        )
        dlg.sync()

    def action_start(self):
        self.clear_last_action_warnings()

    def clear_last_action_warnings(self):
        self.last_action_warnings = []

    def push_dialog_finished(self):
        """
        When the push dialog is closed, make sure it's no longer
        enabled before entering update_button_enabled_status()
        """
        try:
            self.push_dlg.setEnabled(False)
        except RuntimeError:
            pass
        self.update_button_enabled_status()

    def update_button_enabled_status(self):
        """
        Will update the plugin buttons according to open dialog and project properties.
        """
        if self.network_manager.projects_cache.is_currently_open_project_cloud_local:
            self.cloud_synchronize_action.setEnabled(True)
        else:
            self.cloud_synchronize_action.setEnabled(False)

        try:
            dialog_is_enabled = self.push_dlg and self.push_dlg.isEnabled()
        except RuntimeError:
            dialog_is_enabled = False

        if self.offline_editing.isOfflineProject() or dialog_is_enabled:
            self.push_action.setEnabled(False)
        else:
            self.push_action.setEnabled(True)

    def get_qfield_action(self) -> QAction:
        actions = self.iface.pluginMenu().actions()
        result_actions = [action for action in actions if action.text() == self.menu]

        # OSX does not support & in the menu title
        if not result_actions:
            result_actions = [
                action
                for action in actions
                if action.text() == self.menu.replace("&", "")
            ]

        return result_actions[0]
