# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              -------------------
        begin                : 21.11.2016
        git sha              : :%H$
        copyright            : (C) 2016 by OPENGIS.ch
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

from requests import HTTPError

from qgis.PyQt.QtCore import Qt, QTemporaryDir
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QTableWidgetItem, QToolButton, QComboBox, QCheckBox, QMenu, QAction, QWidget, QHBoxLayout
from qgis.PyQt.uic import loadUiType

from qgis.core import QgsProject, QgsMapLayerProxyModel, Qgis, QgsOfflineEditing

from qfieldsync.core import ProjectConfiguration, OfflineConverter
from qfieldsync.core.layer import LayerSource, SyncAction
from qfieldsync.core.project import ProjectProperties
from qfieldsync.gui.photo_naming_widget import PhotoNamingTableWidget
from qfieldsync.gui.utils import set_available_actions
from qfieldsync.core.cloud_api import login, logout, create_project, ProjectUploader, get_error_reason
from qfieldsync.utils.cloud_utils import to_cloud_title

DialogUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), '../ui/project_configuration_dialog.ui'),
    import_from='..'
)


class ProjectConfigurationDialog(QDialog, DialogUi):
    """
    Configuration dialog for QFieldSync on a particular project.
    """

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(ProjectConfigurationDialog, self).__init__(parent=parent)
        self.iface = iface

        self.accepted.connect(self.onAccepted)
        self.project = QgsProject.instance()
        self.__project_configuration = ProjectConfiguration(self.project)

        self.setupUi(self)
        self.multipleToggleButton.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '../resources/visibility.svg')))

        self.toggle_menu = QMenu(self)
        self.remove_all_action = QAction(self.tr("Remove All Layers"), self.toggle_menu)
        self.toggle_menu.addAction(self.remove_all_action)
        self.remove_hidden_action = QAction(self.tr("Remove Hidden Layers"), self.toggle_menu)
        self.toggle_menu.addAction(self.remove_hidden_action)
        self.add_all_copy_action = QAction(self.tr("Add All Layers"), self.toggle_menu)
        self.toggle_menu.addAction(self.add_all_copy_action)
        self.add_visible_copy_action = QAction(self.tr("Add Visible Layers"), self.toggle_menu)
        self.toggle_menu.addAction(self.add_visible_copy_action)
        self.add_all_offline_action = QAction(self.tr("Add All Vector Layers as Offline"), self.toggle_menu)
        self.toggle_menu.addAction(self.add_all_offline_action)
        self.add_visible_offline_action = QAction(self.tr("Add Visible Vector Layers as Offline"), self.toggle_menu)
        self.toggle_menu.addAction(self.add_visible_offline_action)
        self.multipleToggleButton.setMenu(self.toggle_menu)
        self.multipleToggleButton.setAutoRaise(True)
        self.multipleToggleButton.setPopupMode(QToolButton.InstantPopup)
        self.toggle_menu.triggered.connect(self.toggle_menu_triggered)

        self.loginButton.clicked.connect(self.onLoginButtonClicked)
        self.logoutButton.clicked.connect(self.onLogoutButtonClicked)
        self.cloudSyncButton.clicked.connect(self.onCloudSyncButtonClicked)

        self.singleLayerRadioButton.toggled.connect(self.baseMapTypeChanged)
        self.unsupportedLayersList = list()

        self.reloadProject()

    def reloadProject(self):
        """
        Load all layers from the map layer registry into the table.
        """
        self.unsupportedLayersList = list()

        self.photoNamingTable = PhotoNamingTableWidget()
        self.photoNamingTab.layout().addWidget(self.photoNamingTable)

        self.layersTable.setRowCount(0)
        self.layersTable.setSortingEnabled(False)
        for layer in self.project.mapLayers().values():
            layer_source = LayerSource(layer)
            if not layer_source.is_supported:
                self.unsupportedLayersList.append(layer_source)
            count = self.layersTable.rowCount()
            self.layersTable.insertRow(count)
            item = QTableWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer_source)
            item.setData(Qt.EditRole, layer.name())
            self.layersTable.setItem(count, 0, item)

            cmb = QComboBox()
            set_available_actions(cmb, layer_source)
            
            cbx = QCheckBox()
            cbx.setEnabled(layer_source.can_lock_geometry)
            cbx.setChecked(layer_source.is_geometry_locked)
            # it's more UI friendly when the checkbox is centered, an ugly workaround to achieve it
            cbx_widget = QWidget()
            cbx_layout = QHBoxLayout()
            cbx_layout.setAlignment(Qt.AlignCenter)
            cbx_layout.setContentsMargins(0, 0, 0, 0)
            cbx_layout.addWidget(cbx)
            cbx_widget.setLayout(cbx_layout)
            # NOTE the margin is not updated when the table column is resized, so better rely on the code above
            # cbx.setStyleSheet("margin-left:50%; margin-right:50%;")

            self.layersTable.setCellWidget(count, 1, cbx_widget)
            self.layersTable.setCellWidget(count, 2, cmb)

            # make sure layer_source is the same instance everywhere
            self.photoNamingTable.addLayerFields(layer_source)

        self.layersTable.resizeColumnsToContents()
        self.layersTable.sortByColumn(0, Qt.AscendingOrder)
        self.layersTable.setSortingEnabled(True)

        # Remove the tab when not yet suported in QGIS
        if Qgis.QGIS_VERSION_INT < 31300:
            self.tabWidget.removeTab(self.tabWidget.count() - 1)

        # Load Map Themes
        for theme in self.project.mapThemeCollection().mapThemes():
            self.mapThemeComboBox.addItem(theme)

        self.layerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)

        self.__project_configuration = ProjectConfiguration(self.project)
        self.createBaseMapGroupBox.setChecked(self.__project_configuration.create_base_map)

        if self.__project_configuration.base_map_type == ProjectProperties.BaseMapType.SINGLE_LAYER:
            self.singleLayerRadioButton.setChecked(True)
        else:
            self.mapThemeRadioButton.setChecked(True)

        self.mapThemeComboBox.setCurrentIndex(
            self.mapThemeComboBox.findText(self.__project_configuration.base_map_theme))
        layer = QgsProject.instance().mapLayer(self.__project_configuration.base_map_layer)
        self.layerComboBox.setLayer(layer)
        self.mapUnitsPerPixel.setText(str(self.__project_configuration.base_map_mupp))
        self.tileSize.setText(str(self.__project_configuration.base_map_tile_size))
        self.onlyOfflineCopyFeaturesInAoi.setChecked(self.__project_configuration.offline_copy_only_aoi)

        if self.unsupportedLayersList:
            self.unsupportedLayers.setVisible(True)

            unsupported_layers_text = '<b>{}</b><br>'.format(self.tr('Warning'))
            unsupported_layers_text += self.tr("There are unsupported layers in your project. They will not be available on QField.")

            unsupported_layers_text += '<ul>'
            for layer in self.unsupportedLayersList:
                unsupported_layers_text += '<li>' + '<b>' + layer.name + ':</b> ' + layer.warning
            unsupported_layers_text += '<ul>'

            self.unsupportedLayers.setText(unsupported_layers_text)

    def onAccepted(self):
        """
        Update layer configuration in project
        """
        for i in range(self.layersTable.rowCount()):
            item = self.layersTable.item(i, 0)
            layer_source = item.data(Qt.UserRole)
            cbx = self.layersTable.cellWidget(i, 1).layout().itemAt(0).widget()
            cmb = self.layersTable.cellWidget(i, 2)

            old_action = layer_source.action
            old_is_geometry_locked = layer_source.can_lock_geometry and layer_source.is_geometry_locked

            layer_source.action = cmb.itemData(cmb.currentIndex())
            layer_source.is_geometry_locked = cbx.isChecked()

            if layer_source.action != old_action or layer_source.is_geometry_locked != old_is_geometry_locked:
                self.project.setDirty(True)
                layer_source.apply()

        # apply always the photo_namings (to store default values on first apply as well)
        self.photoNamingTable.syncLayerSourceValues(should_apply=True)
        if self.photoNamingTable.rowCount() > 0:
            self.project.setDirty(True)

        self.__project_configuration.create_base_map = self.createBaseMapGroupBox.isChecked()
        self.__project_configuration.base_map_theme = self.mapThemeComboBox.currentText()
        try:
            self.__project_configuration.base_map_layer = self.layerComboBox.currentLayer().id()
        except AttributeError:
            pass
        if self.singleLayerRadioButton.isChecked():
            self.__project_configuration.base_map_type = ProjectProperties.BaseMapType.SINGLE_LAYER
        else:
            self.__project_configuration.base_map_type = ProjectProperties.BaseMapType.MAP_THEME

        self.__project_configuration.base_map_mupp = float(self.mapUnitsPerPixel.text())
        self.__project_configuration.base_map_tile_size = int(self.tileSize.text())

        self.__project_configuration.offline_copy_only_aoi = self.onlyOfflineCopyFeaturesInAoi.isChecked()

    def baseMapTypeChanged(self):
        if self.singleLayerRadioButton.isChecked():
            self.baseMapTypeStack.setCurrentWidget(self.singleLayerPage)
        else:
            self.baseMapTypeStack.setCurrentWidget(self.mapThemePage)

    def toggle_menu_triggered(self, action):
        """
        Toggles usage of layers
        :param action: the menu action that triggered this
        """
        sync_action = SyncAction.NO_ACTION
        if action in (self.remove_hidden_action, self.remove_all_action):
            sync_action = SyncAction.REMOVE
        elif action in (self.add_all_offline_action, self.add_visible_offline_action):
            sync_action = SyncAction.OFFLINE

        # all layers
        if action in (self.remove_all_action, self.add_all_copy_action, self.add_all_offline_action):
            for i in range(self.layersTable.rowCount()):
                item = self.layersTable.item(i, 0)
                layer_source = item.data(Qt.UserRole)
                old_action = layer_source.action
                available_actions, _ = zip(*layer_source.available_actions)
                if sync_action in available_actions:
                    layer_source.action = sync_action
                    if layer_source.action != old_action:
                        self.project.setDirty(True)
                    layer_source.apply()
        # based on visibility
        elif action in (self.remove_hidden_action, self.add_visible_copy_action, self.add_visible_offline_action):
            visible = Qt.Unchecked if action == self.remove_hidden_action else Qt.Checked
            root = QgsProject.instance().layerTreeRoot()
            for layer in QgsProject.instance().mapLayers().values():
                node = root.findLayer(layer.id())
                if node and node.isVisible() == visible:
                    layer_source = LayerSource(layer)
                    old_action = layer_source.action
                    available_actions, _ = zip(*layer_source.available_actions)
                    if sync_action in available_actions:
                        layer_source.action = sync_action
                        if layer_source.action != old_action:
                            self.project.setDirty(True)
                        layer_source.apply()

        self.reloadProject()


    def onLoginButtonClicked(self):
        self.loginButton.setEnabled(False)
        self.logoutButton.setEnabled(False)
        self.cloudSyncButton.setEnabled(False)
        self.loginFeedbackLabel.setVisible(False)

        username = self.usernameLineEdit.text()
        password = self.passwordLineEdit.text()

        try:
            resp = login(username, password)
            
            if self.rememberMeCheckBox.isChecked():
                # TODO permanently store the token
                # resp['token']
                pass

            self.usernameLineEdit.setEnabled(False)
            self.passwordLineEdit.setEnabled(False)
            self.loginButton.setEnabled(False)
            self.logoutButton.setEnabled(True)
            self.cloudSyncButton.setEnabled(True)
        except HTTPError as error:
            self.loginFeedbackLabel.setText("Login failed: {}".format(get_error_reason(error.response)))
            self.loginFeedbackLabel.setVisible(True)
            self.loginButton.setEnabled(True)


    def onLogoutButtonClicked(self):
        self.logoutButton.setEnabled(False)
        self.loginFeedbackLabel.setVisible(False)
        self.cloudSyncButton.setEnabled(False)

        try:
            logout()
            
            self.usernameLineEdit.setEnabled(True)
            self.passwordLineEdit.setText("")
            self.passwordLineEdit.setEnabled(True)
            self.loginButton.setEnabled(True)
        except HTTPError as error:
            self.loginFeedbackLabel.setText("Login failed: {}".format(get_error_reason(error.response)))
            self.loginFeedbackLabel.setVisible(True)
            self.logoutButton.setEnabled(True)


    def onCloudSyncButtonClicked(self):
        self.cloudSyncButton.setEnabled(False)
        self.syncFeedbackLabel.setText('')
        self.syncFeedbackLabel.setVisible(True)

        (project_id, _) = self.project.readEntry("qfieldcloud", "projectId")
        is_new_project = False

        if not project_id:
            is_new_project = True

            self.syncFeedbackLabel.setText(self.tr("Creating cloud project..."))

            try:
                title = self.project.title() 
                title = title if title else self.project.fileName()
                title = title if title else self.tr('Untitled Project')
                resp = create_project(to_cloud_title(title), self.usernameLineEdit.text(), title)
                project_id = resp['id']

                self.project.writeEntry("qfieldcloud", "projectId", project_id)
                self.project.setDirty(True)
            except HTTPError as error:
                self.syncFeedbackLabel.setText(self.tr("Failed to create project: {}".format(get_error_reason(error.response))))
                return

        export_dir = QTemporaryDir().path()

        offline_convertor = OfflineConverter(self.project, export_dir, self.iface.mapCanvas().extent(),
                                             QgsOfflineEditing())
        offline_convertor.total_progress_updated.connect(self.on_offline_convertor_total_progress_updated)
        offline_convertor.convert()

        project_uploader = ProjectUploader(project_id, export_dir, is_new_project)
        project_uploader.progress_uploaded.connect(self.on_project_progress_uploaded)

        try:
            project_uploader.upload()
        except HTTPError as error:
            self.syncFeedbackLabel.setText(self.tr("Failed to upload project: {}".format(get_error_reason(error.response))))
            return

        self.cloudSyncButton.setEnabled(True)
        self.syncFeedbackLabel.setVisible(False)


    def on_offline_convertor_total_progress_updated(self, progress, total, msg):
        self.syncFeedbackLabel.setText(self.tr("{}% {} ".format(int(progress/total), msg)))


    def on_project_progress_uploaded(self, progress, total, filename):
        self.syncFeedbackLabel.setText(self.tr("{}% Uploading {}...".format(int(progress / total), filename)))
