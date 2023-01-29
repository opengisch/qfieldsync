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
import os

from qgis.core import QgsMapLayer, QgsProject
from qgis.gui import QgsMapLayerConfigWidget, QgsMapLayerConfigWidgetFactory
from qgis.PyQt.QtWidgets import QLabel
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.message_bus import message_bus
from qfieldsync.gui.attachment_naming_widget import AttachmentNamingTableWidget
from qfieldsync.gui.relationship_configuration_widget import (
    RelationshipConfigurationTableWidget,
)
from qfieldsync.gui.utils import set_available_actions
from qfieldsync.libqfieldsync.layer import LayerSource

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/map_layer_config_widget.ui")
)


class MapLayerConfigWidgetFactory(QgsMapLayerConfigWidgetFactory):
    def __init__(self, title, icon):
        super(MapLayerConfigWidgetFactory, self).__init__(title, icon)

    def createWidget(self, layer, canvas, dock_widget, parent):
        return MapLayerConfigWidget(layer, canvas, parent)

    def supportsLayer(self, layer):
        return LayerSource(layer).is_supported

    def supportLayerPropertiesDialog(self):
        return True


class MapLayerConfigWidget(QgsMapLayerConfigWidget, WidgetUi):
    def __init__(self, layer, canvas, parent):
        super(MapLayerConfigWidget, self).__init__(layer, canvas, parent)
        self.setupUi(self)
        self.layer_source = LayerSource(layer)
        self.project = QgsProject.instance()

        set_available_actions(
            self.cloudLayerActionComboBox,
            self.layer_source.available_cloud_actions,
            self.layer_source.cloud_action,
        )
        set_available_actions(
            self.cableLayerActionComboBox,
            self.layer_source.available_actions,
            self.layer_source.action,
        )

        self.isGeometryLockedCheckBox.setEnabled(self.layer_source.can_lock_geometry)
        self.isGeometryLockedCheckBox.setChecked(self.layer_source.is_geometry_locked)

        self.attachmentNamingTable = AttachmentNamingTableWidget()
        self.attachmentNamingTable.addLayerFields(self.layer_source)
        self.attachmentNamingTable.setLayerColumnHidden(True)

        # append the attachment naming table to the layout
        if layer.type() == QgsMapLayer.VectorLayer:
            self.layout().insertRow(
                -1, self.tr("Attachment\nnaming"), self.attachmentNamingTable
            )
            tip = QLabel(
                self.tr(
                    "In your expressions, use {filename} and {extension} tags to refer to attachment filenames and extensions."
                )
            )
            tip.setWordWrap(True)
            self.layout().insertRow(-1, "", tip)
            self.attachmentNamingTable.setEnabled(
                self.attachmentNamingTable.rowCount() > 0
            )

        self.relationshipConfigurationTable = RelationshipConfigurationTableWidget()
        self.relationshipConfigurationTable.addLayerFields(self.layer_source)
        self.relationshipConfigurationTable.setLayerColumnHidden(True)

        # append the relationship configuration table to the layout
        if layer.type() == QgsMapLayer.VectorLayer:
            self.layout().insertRow(
                -1,
                self.tr("Relationship\nconfiguration"),
                self.relationshipConfigurationTable,
            )
            self.relationshipConfigurationTable.setEnabled(
                self.relationshipConfigurationTable.rowCount() > 0
            )

    def apply(self):
        old_layer_action = self.layer_source.action
        old_layer_cloud_action = self.layer_source.cloud_action
        old_is_geometry_locked = self.layer_source.is_geometry_locked

        self.layer_source.cloud_action = self.cloudLayerActionComboBox.itemData(
            self.cloudLayerActionComboBox.currentIndex()
        )
        self.layer_source.action = self.cableLayerActionComboBox.itemData(
            self.cableLayerActionComboBox.currentIndex()
        )
        self.layer_source.is_geometry_locked = self.isGeometryLockedCheckBox.isChecked()
        self.attachmentNamingTable.syncLayerSourceValues()
        self.relationshipConfigurationTable.syncLayerSourceValues()

        # apply always the attachment naming (to store default values on first apply as well)
        if (
            self.layer_source.action != old_layer_action
            or self.layer_source.cloud_action != old_layer_cloud_action
            or self.layer_source.is_geometry_locked != old_is_geometry_locked
            or self.attachmentNamingTable.rowCount() > 0
            or self.relationshipConfigurationTable.rowCount() > 0
        ):
            self.layer_source.apply()
            self.project.setDirty(True)

            message_bus.messaged.emit("layer_config_saved")
