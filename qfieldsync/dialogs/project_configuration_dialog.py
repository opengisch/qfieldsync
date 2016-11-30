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
from qfieldsync.core import ProjectConfiguration
from qfieldsync.core.layer import LayerSource
from qfieldsync.core.project import ProjectProperties
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QTableWidgetItem,
    QComboBox
)
from qgis.core import (
    QgsMapLayerRegistry,
    QgsProject
)
from ..utils.qt_utils import get_ui_class

FORM_CLASS = get_ui_class('project_configuration_dialog')

class ProjectConfigurationDialog(QDialog, FORM_CLASS):
    """
    Configuration dialog for QFieldSync on a particular project.
    """

    def __init__(self, iface, parent):
        """Constructor."""
        super(ProjectConfigurationDialog, self).__init__(parent=parent)
        self.iface = iface

        self.accepted.connect(self.onAccepted)
        self.project = QgsProject.instance()

        self.setupUi(self)

        self.singleLayerRadioButton.toggled.connect(self.baseMapTypeChanged)

        self.reloadProject()

    def reloadProject(self):
        """
        Load all layers from the map layer registry into the table.
        """
        self.layersTable.setRowCount(0)
        self.layersTable.setSortingEnabled(False)
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            layer_source = LayerSource(layer)
            count = self.layersTable.rowCount()
            self.layersTable.insertRow(count)
            item = QTableWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer_source)
            item.setData(Qt.EditRole, layer.name())
            self.layersTable.setItem(count, 0, item)

            cbx = QComboBox()
            for action, description in layer_source.available_actions:
                cbx.addItem(description)
                cbx.setItemData(cbx.count() - 1, action)
                if layer_source.action == action:
                    cbx.setCurrentIndex(cbx.count() - 1)

            self.layersTable.setCellWidget(count, 1, cbx)
        self.layersTable.resizeColumnsToContents()
        self.layersTable.sortByColumn(0, Qt.AscendingOrder)
        self.layersTable.setSortingEnabled(True)

        # Load Map Themes
        for theme in self.project.mapThemeCollection().mapThemes():
            self.mapThemeComboBox.addItem(theme)

        self.project_configuration = ProjectConfiguration(self.project)
        self.createBaseMapGroupBox.setChecked(self.project_configuration.create_base_map)

        if self.project_configuration.base_map_type == ProjectProperties.BaseMapType.SINGLE_LAYER:
            self.singleLayerRadioButton.setChecked(True)
        else:
            self.mapThemeRadioButton.setChecked(True)

        self.mapThemeComboBox.setCurrentIndex(self.mapThemeComboBox.findText(self.project_configuration.base_map_theme))
        layer = QgsMapLayerRegistry.instance().mapLayer(self.project_configuration.base_map_layer)
        self.layerComboBox.setLayer(layer)
        self.mapUnitsPerPixel.setText(str(self.project_configuration.base_map_tile_size))
        self.tileSize.setText(str(self.project_configuration.base_map_mupp))
        self.onlyOfflineCopyFeaturesInAoi.setChecked(self.project_configuration.offline_copy_only_aoi)

    def onAccepted(self):
        """
        Update layer configuration in project
        """
        for i in range(self.layersTable.rowCount()):
            item = self.layersTable.item(i, 0)
            layer_source = item.data(Qt.UserRole)
            cbx = self.layersTable.cellWidget(i, 1)

            old_action = layer_source.action
            layer_source.action = cbx.itemData(cbx.currentIndex())
            print('Apply action {} <- {}'.format(layer_source.layer.name(), layer_source.action))
            if layer_source.action != old_action:
                self.project.setDirty()

            layer_source.apply()

        self.project_configuration.create_base_map = self.createBaseMapGroupBox.isChecked()
        self.project_configuration.base_map_theme = self.mapThemeComboBox.currentText()
        try:
            self.project_configuration.base_map_layer = self.layerComboBox.currentLayer().id()
        except AttributeError:
            pass
        if self.singleLayerRadioButton.isChecked():
            self.project_configuration.base_map_type = ProjectProperties.BaseMapType.SINGLE_LAYER
        else:
            self.project_configuration.base_map_type = ProjectProperties.BaseMapType.MAP_THEME

        self.project_configuration.base_map_mupp = float(self.mapUnitsPerPixel.text())
        self.project_configuration.base_map_tile_size = int(self.tileSize.text())

        self.project_configuration.offline_copy_only_aoi = self.onlyOfflineCopyFeaturesInAoi.isChecked()

    def baseMapTypeChanged(self):
        if self.singleLayerRadioButton.isChecked():
            self.baseMapTypeStack.setCurrentWidget(self.singleLayerPage)
        else:
            self.baseMapTypeStack.setCurrentWidget(self.mapThemePage)
