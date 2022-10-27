# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RelationshipConfigurationWidget
                                 A QGIS plugin
 Sync your projects to QField on android
                             -------------------
        begin                : 2020-06-15
        git sha              : $Format:%H$
        copyright            : (C) 2020 by OPENGIS.ch
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

from qgis.core import QgsMapLayer, QgsProject
from qgis.gui import QgsSpinBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem


class RelationshipConfigurationTableWidget(QTableWidget):
    def __init__(self):
        super(RelationshipConfigurationTableWidget, self).__init__()

        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(
            [
                self.tr("Layer"),
                "",
                self.tr("Relationship"),
                self.tr("Maximum number of items visible"),
            ]
        )
        self.horizontalHeader().setStretchLastSection(True)
        self.setRowCount(0)
        self.resizeColumnsToContents()
        self.setMinimumHeight(100)

    def addLayerFields(self, layer_source):
        layer = layer_source.layer

        if layer.type() != QgsMapLayer.VectorLayer:
            return

        for relation in (
            QgsProject.instance().relationManager().referencedRelations(layer)
        ):
            row = self.rowCount()
            self.insertRow(row)
            item = QTableWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer_source)
            item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 0, item)
            item = QTableWidgetItem(relation.id())
            item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 1, item)
            item = QTableWidgetItem(relation.name())
            item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 2, item)
            spin = QgsSpinBox()
            spin.setMinimum(1)
            spin.setMaximum(100)
            spin.setSingleStep(1)
            spin.setValue(layer_source.relationship_maximum_visible(relation.id()))
            self.setCellWidget(row, 3, spin)
            self.setColumnHidden(1, True)

        self.resizeColumnsToContents()

    def setLayerColumnHidden(self, is_hidden):
        self.setColumnHidden(0, is_hidden)

    def syncLayerSourceValues(self, should_apply=False):
        for i in range(self.rowCount()):
            layer_source = self.item(i, 0).data(Qt.UserRole)
            relation_id = self.item(i, 1).text()
            relationship_maximum_visible = self.cellWidget(i, 3).value()
            layer_source.set_relationship_maximum_visible(
                relation_id, relationship_maximum_visible
            )

            if should_apply:
                layer_source.apply()
