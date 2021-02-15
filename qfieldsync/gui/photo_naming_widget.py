# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSyncDialog
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

from qgis.core import QgsMapLayer
from qgis.gui import QgsFieldExpressionWidget

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractScrollArea


class PhotoNamingTableWidget(QTableWidget):
    def __init__(self):
        super(PhotoNamingTableWidget, self).__init__()

        self.setColumnCount(3)
        self.setHorizontalHeaderLabels([self.tr('Layer'), self.tr('Field'), self.tr('Naming Expression')])
        self.horizontalHeaderItem(2).setToolTip(self.tr('Enter expression for a file path with the extension .jpg'))
        self.horizontalHeader().setStretchLastSection(True)
        self.setRowCount(0)
        self.resizeColumnsToContents()
        self.setMinimumHeight(100)
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)


    def addLayerFields(self, layer_source):
        layer = layer_source.layer

        if layer.type() != QgsMapLayer.VectorLayer:
            return

        for i, field in enumerate(layer.fields()):
            row = self.rowCount()
            ews = layer.editorWidgetSetup(i)

            if ews.type() == 'ExternalResource':
                # for later: if ews.config().get('DocumentViewer', QgsExternalResourceWidget.NoContent) == QgsExternalResourceWidget.Image:
                self.insertRow(row)
                item = QTableWidgetItem(layer.name())
                item.setData(Qt.UserRole, layer_source)
                item.setFlags(Qt.ItemIsEnabled)
                self.setItem(row, 0, item)
                item = QTableWidgetItem(field.name())
                item.setFlags(Qt.ItemIsEnabled)
                self.setItem(row, 1, item)
                ew = QgsFieldExpressionWidget()
                ew.setLayer(layer)
                expression = layer_source.photo_naming(field.name())
                ew.setExpression(expression)
                self.setCellWidget(row, 2, ew)

        self.resizeColumnsToContents()


    def setLayerColumnHidden(self, is_hidden):
        self.setColumnHidden(0, is_hidden)


    def syncLayerSourceValues(self, should_apply=False):
        for i in range(self.rowCount()):
            layer_source = self.item(i, 0).data(Qt.UserRole)
            field_name = self.item(i, 1).text()
            new_expression = self.cellWidget(i, 2).currentText()
            layer_source.set_photo_naming(field_name, new_expression)

            if should_apply:
                layer_source.apply()
