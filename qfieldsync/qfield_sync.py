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

from __future__ import absolute_import

from qfieldsync.core import Preferences

try:
    from builtins import object
except:
    pass

import os.path
from qgis.PyQt.QtCore import (
    QTranslator,
    qVersion,
    QCoreApplication,
    QSettings,
    Qt,
    QLocale
)
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsOfflineEditing, QgsProject

from qfieldsync.dialogs.package_dialog import PackageDialog
from qfieldsync.dialogs.preferences_dialog import PreferencesDialog
from qfieldsync.dialogs.synchronize_dialog import SynchronizeDialog
from qfieldsync.dialogs.project_configuration_dialog import ProjectConfigurationDialog

# Core processing imports
from processing.core.Processing import Processing
# Plugin provided processing extension
from .processing.provider import QFieldProcessingProvider

# noinspection PyUnresolvedReferences
if qVersion()[0] == '4':
    import qfieldsync.resources_rc4  # pylint: disable=unused-import  # NOQA
else:
    import qfieldsync.resources_rc5  # pylint: disable=unused-import  # NOQA


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
        locale = QLocale(QSettings().value('locale/userLocale'))
        locale_path = os.path.join(self.plugin_dir, 'i18n')
        self.translator = QTranslator()
        self.translator.load(locale, 'QFieldSync', '_', locale_path)

        QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&QFieldSync')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'QFieldSync')
        self.toolbar.setObjectName(u'QFieldSync')

        # instance of the QgsOfflineEditing
        self.offline_editing = QgsOfflineEditing()
        self.preferences = Preferences()

        QgsProject.instance().readProject.connect(self.update_button_enabled_status)

        # store warnings from last run
        self.last_action_warnings = []

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
        return QCoreApplication.translate('QFieldSync', message)

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
            parent=None):
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
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.push_action = self.add_action(
            ':/plugins/qfieldsync/refresh.png',
            text=self.tr(u'Package for QField'),
            callback=self.show_package_dialog,
            parent=self.iface.mainWindow())

        self.add_action(
            ':/plugins/qfieldsync/refresh-reverse.png',
            text=self.tr(u'Synchronize from QField'),
            callback=self.show_synchronize_dialog,
            parent=self.iface.mainWindow())

        self.add_action(
            ':/plugins/qfieldsync/icon.png',
            text=self.tr(u'Project Configuration'),
            callback=self.show_project_configuration_dialog,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False
        )

        self.add_action(
            ':/plugins/qfieldsync/icon.png',
            text=self.tr(u'Preferences'),
            callback=self.show_preferences_dialog,
            parent=self.iface.mainWindow(),
            add_to_toolbar=False)

        self.processing_provider = QFieldProcessingProvider()
        Processing.addProvider(self.processing_provider)

        self.update_button_enabled_status()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&QFieldSync'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar
        Processing.removeProvider(self.processing_provider)
        self.processing_provider = None

    def show_preferences_dialog(self):
        dlg = PreferencesDialog(self.preferences, self.iface.mainWindow())
        dlg.exec_()

    def show_synchronize_dialog(self):
        """
        Synchronize from QField
        """
        dlg = SynchronizeDialog(self.iface, self.preferences, self.offline_editing, self.iface.mainWindow())
        dlg.exec_()

    def show_package_dialog(self):
        """
        Push to QField
        """
        self.push_dlg = PackageDialog(self.iface, self.preferences, QgsProject.instance(), self.offline_editing,
                                      self.iface.mainWindow())
        self.push_dlg.setAttribute(Qt.WA_DeleteOnClose)
        self.push_dlg.setWindowFlags(self.push_dlg.windowFlags() | Qt.Tool)
        self.push_dlg.show()

        self.push_dlg.finished.connect(self.push_dialog_finished)
        self.update_button_enabled_status()

    def show_project_configuration_dialog(self):
        """
        Show the project configuration dialog.
        """
        dlg = ProjectConfigurationDialog(self.iface, self.iface.mainWindow())
        dlg.exec_()

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
        try:
            dialog_is_enabled = self.push_dlg and self.push_dlg.isEnabled()
        except RuntimeError:
            dialog_is_enabled = False

        if self.offline_editing.isOfflineProject() or dialog_is_enabled:
            self.push_action.setEnabled(False)
        else:
            self.push_action.setEnabled(True)
