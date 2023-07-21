# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RelationshipConfigurationWidget
                                 A QGIS plugin
 Sync your projects to QField
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
            layer_name_item = QTableWidgetItem(layer.name())
            layer_name_item.setData(Qt.UserRole, layer_source)
            layer_name_item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 0, layer_name_item)
            relation_id_item = QTableWidgetItem(relation.id())
            relation_id_item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 1, relation_id_item)
            relation_name_item = QTableWidgetItem(relation.name())
            relation_name_item.setFlags(Qt.ItemIsEnabled)
            self.setItem(row, 2, relation_name_item)
            spin_item = QgsSpinBox()
            spin_item.setMinimum(0)
            spin_item.setMaximum(100)
            spin_item.setSingleStep(1)
            spin_item.setClearValue(0, self.tr("unlimited"))
            spin_item.setShowClearButton(True)
            spin_item.setValue(layer_source.relationship_maximum_visible(relation.id()))
            self.setCellWidget(row, 3, spin_item)
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
