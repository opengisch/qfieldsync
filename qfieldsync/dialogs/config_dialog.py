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

from qfieldsync.utils.data_source_utils import LayerSource
from ..utils.qt_utils import get_ui_class

from qgis.PyQt.QtWidgets import (
    QDialog,
    QTableWidgetItem,
    QComboBox
)

from qgis.PyQt.QtCore import Qt

from qgis.core import (
    QgsMapLayerRegistry,
    QgsProject
)

from qfieldsync.config import (
    BASE_MAP_TYPE,
    CREATE_BASE_MAP,
    BASE_MAP_THEME,
    BASE_MAP_TYPE_MAP_THEME,
    BASE_MAP_TYPE_SINGLE_LAYER,
    BASE_MAP_LAYER, BASE_MAP_MUPP,
    BASE_MAP_TILE_SIZE,
    OFFLINE_COPY_ONLY_AOI)

FORM_CLASS = get_ui_class('config_dialog_base')

class ConfigDialog(QDialog, FORM_CLASS):
    """
    Configuration dialog for QFieldSync on a particular project.
    """

    def __init__(self, iface, parent):
        """Constructor."""
        super(ConfigDialog, self).__init__(parent=parent)
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
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            layer_source = LayerSource(layer)
            count = self.layersTable.rowCount()
            self.layersTable.insertRow(count)
            item = QTableWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer_source)
            self.layersTable.setItem(count, 0, item)

            cbx = QComboBox()
            for action, description in layer_source.available_actions:
                cbx.addItem(description)
                cbx.setItemData(Qt.UserRole, action)
                if layer_source.action == action:
                    cbx.setCurrentIndex(cbx.count() - 1)

            self.layersTable.setCellWidget(count, 1, cbx)

        # Load Map Themes
        for theme in self.project.mapThemeCollection().mapThemes():
            self.mapThemeComboBox.addItem(theme)

        createBaseMap, _ = self.project.readBoolEntry('qfieldsync', CREATE_BASE_MAP, False)
        self.createBaseMapGroupBox.setChecked(createBaseMap)

        baseMapType, _ = self.project.readEntry('qfieldsync', BASE_MAP_TYPE)

        if baseMapType == BASE_MAP_TYPE_SINGLE_LAYER:
            self.singleLayerRadioButton.setChecked(True)
        else:
            self.mapThemeRadioButton.setChecked(True)

        baseMapTheme, _ = self.project.readEntry('qfieldsync', BASE_MAP_THEME)
        self.mapThemeComboBox.setCurrentIndex(self.mapThemeComboBox.findText(baseMapTheme))

        baseMapLayer, _ = self.project.readEntry('qfieldsync', BASE_MAP_LAYER)
        layer = QgsMapLayerRegistry.instance().mapLayer(baseMapLayer)
        self.layerComboBox.setLayer(layer)

        baseMapTileSize, _ = self.project.readEntry('qfieldsync', BASE_MAP_TILE_SIZE, '1024')
        self.mapUnitsPerPixel.setText(baseMapTileSize)
        baseMapMupp, _ = self.project.readEntry('qfieldsync', BASE_MAP_MUPP, '100')
        self.tileSize.setText(baseMapMupp)

        only_copy_features_in_aoi, _ = self.project.readBoolEntry('qfieldsync', OFFLINE_COPY_ONLY_AOI, False)
        self.onlyOfflineCopyFeaturesInAoi.setChecked(only_copy_features_in_aoi)

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
            if layer_source.action != old_action:
                self.project.setDirty()

            layer_source.apply()

        self.project.writeEntry('qfieldsync', CREATE_BASE_MAP, self.createBaseMapGroupBox.isChecked())
        self.project.writeEntry('qfieldsync', BASE_MAP_THEME, self.mapThemeComboBox.currentText())
        try:
            self.project.writeEntry('qfieldsync', BASE_MAP_LAYER, self.layerComboBox.currentLayer().id())
        except AttributeError:
            pass
        if self.singleLayerRadioButton.isChecked():
            self.project.writeEntry('qfieldsync', BASE_MAP_TYPE, BASE_MAP_TYPE_SINGLE_LAYER)
        else:
            self.project.writeEntry('qfieldsync', BASE_MAP_TYPE, BASE_MAP_TYPE_MAP_THEME)

        self.project.writeEntry('qfieldsync', BASE_MAP_TILE_SIZE, self.mapUnitsPerPixel.text())
        self.project.writeEntry('qfieldsync', BASE_MAP_MUPP, self.tileSize.text())

        self.project.writeEntry('qfieldsync', OFFLINE_COPY_ONLY_AOI, self.onlyOfflineCopyFeaturesInAoi.isChecked())

    def baseMapTypeChanged(self):
        if self.singleLayerRadioButton.isChecked():
            self.baseMapTypeStack.setCurrentWidget(self.singleLayerPage)
        else:
            self.baseMapTypeStack.setCurrentWidget(self.mapThemePage)
