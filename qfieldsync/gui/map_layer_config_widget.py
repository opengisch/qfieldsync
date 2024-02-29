# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSyncDialog
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
import os

from libqfieldsync.layer import LayerSource
from qgis.core import QgsMapLayer, QgsProject, QgsProperty, QgsPropertyDefinition
from qgis.gui import QgsMapLayerConfigWidget, QgsMapLayerConfigWidgetFactory
from qgis.PyQt.QtWidgets import QLabel
from qgis.PyQt.uic import loadUiType

from qfieldsync.core.message_bus import message_bus
from qfieldsync.gui.attachment_naming_widget import AttachmentNamingTableWidget
from qfieldsync.gui.relationship_configuration_widget import (
    RelationshipConfigurationTableWidget,
)
from qfieldsync.gui.utils import set_available_actions

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
    PROPERTY_GEOMETRY_LOCKED = 1

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

        self.attachmentNamingTable = AttachmentNamingTableWidget()
        self.attachmentNamingTable.addLayerFields(self.layer_source)
        self.attachmentNamingTable.setLayerColumnHidden(True)

        self.relationshipConfigurationTable = RelationshipConfigurationTableWidget()
        self.relationshipConfigurationTable.addLayerFields(self.layer_source)
        self.relationshipConfigurationTable.setLayerColumnHidden(True)

        self.measurementTypeComboBox.addItem(
            "Elapsed time (seconds since start of tracking)"
        )
        self.measurementTypeComboBox.addItem(
            self.tr("Timestamp (milliseconds since epoch)")
        )
        self.measurementTypeComboBox.addItem(self.tr("Ground speed"))
        self.measurementTypeComboBox.addItem(self.tr("Bearing"))
        self.measurementTypeComboBox.addItem(self.tr("Horizontal accuracy"))
        self.measurementTypeComboBox.addItem(self.tr("Vertical accuracy"))
        self.measurementTypeComboBox.addItem(self.tr("PDOP"))
        self.measurementTypeComboBox.addItem(self.tr("HDOP"))
        self.measurementTypeComboBox.addItem(self.tr("VDOP"))

        if layer.type() == QgsMapLayer.VectorLayer:
            prop = QgsProperty.fromExpression(
                self.layer_source.geometry_locked_expression
            )
            prop.setActive(self.layer_source.is_geometry_locked_expression_active)
            prop_definition = QgsPropertyDefinition(
                "is_geometry_locked",
                QgsPropertyDefinition.DataType.DataTypeBoolean,
                "Geometry Locked",
                "",
            )
            self.isGeometryLockedDDButton.init(
                MapLayerConfigWidget.PROPERTY_GEOMETRY_LOCKED,
                prop,
                prop_definition,
                None,
                False,
            )
            self.isGeometryLockedDDButton.setVectorLayer(layer)

            self.isGeometryLockedCheckBox.setEnabled(
                self.layer_source.can_lock_geometry
            )
            self.isGeometryLockedCheckBox.setChecked(
                self.layer_source.is_geometry_locked
            )

            # append the attachment naming table to the layout
            self.attachmentsRelationsLayout.insertRow(
                -1, self.tr("Attachment\nnaming"), self.attachmentNamingTable
            )
            tip = QLabel(
                self.tr(
                    "In your expressions, use {filename} and {extension} tags to refer to attachment filenames and extensions."
                )
            )
            tip.setWordWrap(True)
            self.attachmentsRelationsLayout.insertRow(-1, "", tip)
            self.attachmentNamingTable.setEnabled(
                self.attachmentNamingTable.rowCount() > 0
            )

            # append the relationship configuration table to the layout
            self.attachmentsRelationsLayout.insertRow(
                -1,
                self.tr("Relationship\nconfiguration"),
                self.relationshipConfigurationTable,
            )
            self.relationshipConfigurationTable.setEnabled(
                self.relationshipConfigurationTable.rowCount() > 0
            )

            self.trackingSessionGroupBox.setChecked(
                self.layer_source.tracking_session_active
            )
            self.timeRequirementCheckBox.setChecked(
                self.layer_source.tracking_time_requirement_active
            )
            self.timeRequirementIntervalSecondsSpinBox.setValue(
                self.layer_source.tracking_time_requirement_interval_seconds
            )
            self.distanceRequirementCheckBox.setChecked(
                self.layer_source.tracking_distance_requirement_active
            )
            self.distanceRequirementMinimumMetersSpinBox.setValue(
                self.layer_source.tracking_distance_requirement_minimum_meters
            )
            self.sensorDataRequirementCheckBox.setChecked(
                self.layer_source.tracking_sensor_data_requirement_active
            )
            self.allRequirementsCheckBox.setChecked(
                self.layer_source.tracking_all_requirements_active
            )
            self.erroneousDistanceSafeguardCheckBox.setChecked(
                self.layer_source.tracking_erroneous_distance_safeguard_active
            )
            self.erroneousDistanceSafeguardMaximumMetersSpinBox.setValue(
                self.layer_source.tracking_erroneous_distance_safeguard_maximum_meters
            )
            self.measurementTypeComboBox.setCurrentIndex(
                self.layer_source.tracking_measurement_type
            )
        else:
            self.isGeometryLockedDDButton.setVisible(False)
            self.isGeometryLockedCheckBox.setVisible(False)

            self.attachmentsRelationsGroupBox.setVisible(False)
            self.trackingSessionGroupBox.setVisible(False)

    def apply(self):
        self.layer_source.action
        self.layer_source.cloud_action
        self.layer_source.is_geometry_locked

        self.layer_source.cloud_action = self.cloudLayerActionComboBox.itemData(
            self.cloudLayerActionComboBox.currentIndex()
        )
        self.layer_source.action = self.cableLayerActionComboBox.itemData(
            self.cableLayerActionComboBox.currentIndex()
        )
        self.layer_source.is_geometry_locked = self.isGeometryLockedCheckBox.isChecked()
        prop = self.isGeometryLockedDDButton.toProperty()
        self.layer_source.is_geometry_locked_expression_active = prop.isActive()
        self.layer_source.geometry_locked_expression = prop.asExpression()
        self.attachmentNamingTable.syncLayerSourceValues()
        self.relationshipConfigurationTable.syncLayerSourceValues()

        self.layer_source.tracking_session_active = (
            self.trackingSessionGroupBox.isChecked()
        )
        self.layer_source.tracking_time_requirement_active = (
            self.timeRequirementCheckBox.isChecked()
        )
        self.layer_source.tracking_time_requirement_interval_seconds = (
            self.timeRequirementIntervalSecondsSpinBox.value()
        )
        self.layer_source.tracking_distance_requirement_active = (
            self.distanceRequirementCheckBox.isChecked()
        )
        self.layer_source.tracking_distance_requirement_minimum_meters = (
            self.distanceRequirementMinimumMetersSpinBox.value()
        )
        self.layer_source.tracking_sensor_data_requirement_active = (
            self.sensorDataRequirementCheckBox.isChecked()
        )
        self.layer_source.tracking_all_requirements_active = (
            self.allRequirementsCheckBox.isChecked()
        )
        self.layer_source.tracking_erroneous_distance_safeguard_active = (
            self.erroneousDistanceSafeguardCheckBox.isChecked()
        )
        self.layer_source.tracking_erroneous_distance_safeguard_maximum_meters = (
            self.erroneousDistanceSafeguardMaximumMetersSpinBox.value()
        )
        self.layer_source.tracking_measurement_type = (
            self.measurementTypeComboBox.currentIndex()
        )

        if self.layer_source.apply():
            self.project.setDirty(True)
            message_bus.messaged.emit("layer_config_saved")
