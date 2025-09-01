"""
/***************************************************************************
 MapThemesConfigWidget
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2024-07-22
        git sha              : $Format:%H$
        copyright            : (C) 2024 by OPENGIS.ch
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

from qgis.core import Qgis, QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem


class MapThemesConfigWidget(QTableWidget):
    def __init__(self, project, configuration, parent=None):
        """Constructor."""
        super(QTableWidget, self).__init__(parent=parent)

        self.project = project

        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setMinimumHeight(200)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(
            [self.tr("Map Theme"), self.tr("Default Active Layer")]
        )

        self.reload(configuration)

    def reload(self, configuration):
        """Load map themes into table."""
        self.setRowCount(0)
        self.setSortingEnabled(False)
        map_themes = self.project.mapThemeCollection().mapThemes()
        for map_theme in map_themes:
            count = self.rowCount()
            self.insertRow(count)
            item = QTableWidgetItem(map_theme)
            item.setData(Qt.ItemDataRole.EditRole, map_theme)
            self.setItem(count, 0, item)

            cmb = QgsMapLayerComboBox()
            cmb.setAllowEmptyLayer(True)
            if Qgis.versionInt() >= 32400:  # noqa: PLR2004
                cmb.setProject(self.project)
            cmb.setFilters(QgsMapLayerProxyModel.VectorLayer)
            if map_theme in configuration:
                cmb.setLayer(self.project.mapLayer(configuration[map_theme]))
            self.setCellWidget(count, 1, cmb)

        self.setColumnWidth(0, int(self.width() * 0.2))
        self.setColumnWidth(1, int(self.width() * 0.75))
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.setSortingEnabled(True)

    def create_configuration(self):
        configuration = {}
        for i in range(self.rowCount()):
            item = self.item(i, 0)
            map_theme = item.data(Qt.ItemDataRole.EditRole)
            cmb = self.cellWidget(i, 1)
            layer_id = cmb.currentLayer().id() if cmb.currentLayer() else ""
            configuration[map_theme] = layer_id

        return configuration
