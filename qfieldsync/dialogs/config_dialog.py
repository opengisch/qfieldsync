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

FORM_CLASS = get_ui_class('config_dialog_base.ui')

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
            count = self.layersTable.rowCount()
            self.layersTable.insertRow(count)
            item = QTableWidgetItem(layer.name())
            item.setData(Qt.UserRole, layer)
            self.layersTable.setItem(count, 0, item)

            action = layer.customProperty("qfieldsync/action", 'NoAction')

            cbx = QComboBox()
            cbx.addItem(self.tr('No action'))
            cbx.addItem(self.tr('Offline copy'))
            cbx.addItem(self.tr('Remove'))

            if action == 'OfflineCopy':
                cbx.setCurrentIndex(1)
            elif action == 'Remove':
                cbx.setCurrentIndex(2)

            self.layersTable.setCellWidget(count, 1, cbx)

        # Load Map Themes
        for theme in self.project.mapThemeCollection().mapThemes():
            self.mapThemeComboBox.addItem(theme)

        createBaseMap, _ = self.project.readBoolEntry('qfieldsync', '/createBaseMap', False)
        self.createBaseMapGroupBox.setChecked(createBaseMap)

        baseMapType, _ = self.project.readEntry('qfieldsync', '/baseMapType')

        if baseMapType == 'SingleLayer':
            self.singleLayerRadioButton.setChecked(True)
        else:
            self.mapThemeRadioButton.setChecked(True)

        baseMapTheme, _ = self.project.readEntry('qfieldsync', '/baseMapTheme')
        self.mapThemeComboBox.setCurrentIndex(self.mapThemeComboBox.findText(baseMapTheme))

    def onAccepted(self):
        """
        Update layer configuration in project
        """
        for i in range(self.layersTable.rowCount()):
            item = self.layersTable.item(i, 0)
            layer = item.data(Qt.UserRole)
            cbx = self.layersTable.cellWidget(i, 1)
            oldConfiguration = layer.customProperty("qfieldsync/action", 'NoAction')
            if cbx.currentIndex() == 1:
                layer.setCustomProperty('qfieldsync/action', 'OfflineCopy')
            elif cbx.currentIndex() == 2:
                layer.setCustomProperty('qfieldsync/action', 'Remove')
            else:
                layer.setCustomProperty('qfieldsync/action', 'NoAction')

            if layer.customProperty('qfieldsync/action') != oldConfiguration:
                self.project.setDirty()

        self.project.writeEntry('qfieldsync', '/createBaseMap', self.createBaseMapGroupBox.isChecked())
        self.project.writeEntry('qfieldsync', '/baseMapTheme', self.mapThemeComboBox.currentText())
        if self.singleLayerRadioButton.isChecked():
            self.project.writeEntry('qfieldsync', '/baseMapType', 'SingleLayer')
        else:
            self.project.writeEntry('qfieldsync', '/baseMapType', 'MapTheme')

    def baseMapTypeChanged(self):
        if self.singleLayerRadioButton.isChecked():
            self.baseMapTypeStack.setCurrentWidget(self.singleLayerPage)
        else:
            self.baseMapTypeStack.setCurrentWidget(self.mapThemePage)