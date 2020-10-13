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
from qgis.gui import (
    QgsOptionsWidgetFactory,
    QgsOptionsPageWidget,
)

from qfieldsync.core import ProjectConfiguration, OfflineConverter
from qfieldsync.core.layer import LayerSource, SyncAction
from qfieldsync.core.project import ProjectProperties
from qfieldsync.gui.photo_naming_widget import PhotoNamingTableWidget
from qfieldsync.gui.layers_config_widget import LayersConfigWidget
from qfieldsync.gui.utils import set_available_actions
from qfieldsync.utils.cloud_utils import to_cloud_title


WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), '../ui/project_configuration_widget.ui'),
    import_from='..'
)


class ProjectConfigurationWidget(WidgetUi, QgsOptionsPageWidget):
    """
    Configuration widget for QFieldSync on a particular project.
    """

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self.project = QgsProject.instance()
        self.__project_configuration = ProjectConfiguration(self.project)


        self.singleLayerRadioButton.toggled.connect(self.baseMapTypeChanged)

        self.photoNamingTable = PhotoNamingTableWidget()
        self.photoNamingTab.layout().addWidget(self.photoNamingTable)

        self.reloadProject()

    def reloadProject(self):
        """
        Load all layers from the map layer registry into the table.
        """
        self.unsupportedLayersList = list()

        self.photoNamingTable = PhotoNamingTableWidget()
        self.photoNamingGroup.layout().addWidget(self.photoNamingTable)
        self.cloudLayersConfigWidget = LayersConfigWidget(self.project)
        self.cableLayersConfigWidget = LayersConfigWidget(self.project)
        self.cloudAdvancedSettings.layout().addWidget(self.cloudLayersConfigWidget)
        self.cableExportTab.layout().addWidget(self.cableLayersConfigWidget)


        # Remove the tab when not yet suported in QGIS
        if Qgis.QGIS_VERSION_INT < 31300:
            self.photoNamingGroup.setVisible(False)

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
            self.unsupportedLayersLabel.setVisible(True)

            unsupported_layers_text = '<b>{}: </b>'.format(self.tr('Warning'))
            unsupported_layers_text += self.tr("There are unsupported layers in your project which will not be available in QField.")
            unsupported_layers_text += self.tr(" If needed, you can create a Base Map to include those layers in your packaged project.")
            self.unsupportedLayersLabel.setText(unsupported_layers_text)

    def apply(self):
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

