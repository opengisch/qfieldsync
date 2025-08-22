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

from libqfieldsync.layer import LayerSource
from libqfieldsync.project import ProjectConfiguration, ProjectProperties
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsMapLayerProxyModel,
    QgsPolygon,
    QgsProject,
)
from qgis.gui import (
    QgsExtentWidget,
    QgsOptionsPageWidget,
    QgsPanelWidget,
    QgsPanelWidgetStack,
    QgsSpinBox,
)
from qgis.PyQt.QtCore import QEvent, QObject
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import QLineEdit, QVBoxLayout
from qgis.PyQt.uic import loadUiType
from qgis.utils import iface

from qfieldsync.core.preferences import Preferences
from qfieldsync.gui.directories_configuration_widget import (
    DirectoriesConfigurationWidget,
)
from qfieldsync.gui.image_stamping_configuration_widget import (
    ImageStampingConfigurationWidget,
)
from qfieldsync.gui.layers_config_widget import LayersConfigWidget
from qfieldsync.gui.mapthemes_config_widget import MapThemesConfigWidget

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/project_configuration_widget.ui")
)


class EventEater(QObject):
    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.Backspace) or event.matches(
                QKeySequence.StandardKey.Delete
            ):
                widget.takeItem(widget.currentRow())

        return super().eventFilter(widget, event)


class ProjectConfigurationStackWidget(QgsOptionsPageWidget):
    """
    Configuration widget for QFieldSync on a particular project.
    """

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)

        self.panel_stack = QgsPanelWidgetStack(self)
        self.project_configuration_widget = ProjectConfigurationWidget(self)
        self.panel_stack.setMainPanel(self.project_configuration_widget)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.panel_stack)
        self.setLayout(self.layout)

    def apply(self):
        self.panel_stack.acceptAllPanels()
        self.project_configuration_widget.apply()


class ProjectConfigurationWidget(WidgetUi, QgsPanelWidget):
    """
    Configuration widget for QFieldSync on a particular project.
    """

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self.setDockMode(True)

        self.project = QgsProject.instance()
        self.preferences = Preferences()
        self.__project_configuration = ProjectConfiguration(self.project)

        self.stamping_font_style = self.__project_configuration.stamping_font_style
        self.stamping_horizontal_alignment = (
            self.__project_configuration.stamping_horizontal_alignment
        )
        self.stamping_image_decoration = (
            self.__project_configuration.stamping_image_decoration
        )
        if self.__project_configuration.stamping_image_decoration:
            self.stamping_image_decoration = (
                QgsProject.instance()
                .pathResolver()
                .readPath(self.__project_configuration.stamping_image_decoration)
            )
        else:
            self.stamping_image_decoration = ""
        self.stamping_details_template = (
            self.__project_configuration.stamping_details_template
        )
        self.force_stamping = self.__project_configuration.force_stamping
        self.customizeImageStampingButton.clicked.connect(
            self.show_image_stamping_settings
        )

        self.areaOfInterestExtentWidget = QgsExtentWidget(self)
        self.areaOfInterestExtentWidget.setToolTip(
            self.tr("Leave empty to use the full project extent")
        )
        # A bit of a hack to deliver a nice instructive placeholder text to users
        line_edits = self.areaOfInterestExtentWidget.findChildren(QLineEdit)
        for line_edit in line_edits:
            line_edit.setPlaceholderText(
                self.tr("Leave empty to use the full project extent")
            )
        self.areaOfInterestExtentWidget.setNullValueAllowed(True)

        if iface:
            self.areaOfInterestExtentWidget.setMapCanvas(iface.mapCanvas())

        if self.__project_configuration.area_of_interest_crs:
            self.areaOfInterestExtentWidget.setOutputCrs(
                QgsCoordinateReferenceSystem(
                    self.__project_configuration.area_of_interest_crs
                )
            )

        geom = QgsPolygon()
        if self.__project_configuration.area_of_interest and geom.fromWkt(
            self.__project_configuration.area_of_interest,
        ):
            self.areaOfInterestExtentWidget.setOutputExtentFromUser(
                geom.boundingBox(),
                self.areaOfInterestExtentWidget.outputCrs(),
            )

        self.areaOfInterestBaseMapLayout.layout().addWidget(
            self.areaOfInterestExtentWidget, 1, 1
        )

        self.singleLayerRadioButton.toggled.connect(self.baseMapTypeChanged)

        self.forceAutoPush.clicked.connect(self.onForceAutoPushClicked)

        self.directoriesConfigurationWidget = DirectoriesConfigurationWidget(self)
        self.attachmentsDirectoriesTab.layout().addWidget(
            self.directoriesConfigurationWidget, 1, 0, 1, 2
        )

        self.geofencingBehaviorComboBox.addItem(
            self.tr("Alert users when inside an area"),
            ProjectProperties.GeofencingBehavior.ALERT_INSIDE_AREAS,
        )
        self.geofencingBehaviorComboBox.addItem(
            self.tr("Alert users when outside all areas"),
            ProjectProperties.GeofencingBehavior.ALERT_OUTSIDE_AREAS,
        )
        self.geofencingBehaviorComboBox.addItem(
            self.tr("Inform users when entering and leaving an area"),
            ProjectProperties.GeofencingBehavior.INFORM_ENTER_LEAVE_AREAS,
        )

        self.reloadProject()

    def reloadProject(self):
        """
        Load all layers from the map layer registry into the table.
        """
        self.unsupportedLayersList = list()

        layer_sources = [
            LayerSource(layer) for layer in QgsProject.instance().mapLayers().values()
        ]
        self.cloudLayersConfigWidget = LayersConfigWidget(
            self.project, True, layer_sources
        )
        self.cableLayersConfigWidget = LayersConfigWidget(
            self.project, False, layer_sources
        )

        self.cloudExportTab.layout().addWidget(self.cloudLayersConfigWidget, 2, 0, 1, 2)
        self.cableExportTab.layout().addWidget(self.cableLayersConfigWidget)

        # Map Themes configuration widgets
        for theme in self.project.mapThemeCollection().mapThemes():
            self.mapThemeComboBox.addItem(theme)

        self.layerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)

        self.geofencingLayerComboBox.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.geofencingLayerComboBox.setAllowEmptyLayer(True)

        self.digitizingLogsLayerComboBox.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.digitizingLogsLayerComboBox.setAllowEmptyLayer(True)

        if Qgis.QGIS_VERSION_INT >= 32400:
            self.layerComboBox.setProject(self.project)
            self.geofencingLayerComboBox.setProject(self.project)
            self.digitizingLogsLayerComboBox.setProject(self.project)

        self.__project_configuration = ProjectConfiguration(self.project)

        self.mapThemesConfigWidget = MapThemesConfigWidget(
            self.project, self.__project_configuration.map_themes_active_layer
        )
        self.mapThemesGroupBox.layout().addWidget(self.mapThemesConfigWidget)

        # Base map settings
        self.createBaseMapGroupBox.setChecked(
            self.__project_configuration.create_base_map
        )

        if (
            self.__project_configuration.base_map_type
            == ProjectProperties.BaseMapType.SINGLE_LAYER
        ):
            self.singleLayerRadioButton.setChecked(True)
        else:
            self.mapThemeRadioButton.setChecked(True)

        self.baseMapLayerLabel.setVisible(self.singleLayerRadioButton.isChecked())
        self.layerComboBox.setVisible(self.singleLayerRadioButton.isChecked())
        self.baseMapMapThemeLabel.setVisible(
            not self.singleLayerRadioButton.isChecked()
        )
        self.mapThemeComboBox.setVisible(not self.singleLayerRadioButton.isChecked())

        self.mapThemeComboBox.setCurrentIndex(
            self.mapThemeComboBox.findText(self.__project_configuration.base_map_theme)
        )

        layer = QgsProject.instance().mapLayer(
            self.__project_configuration.base_map_layer
        )
        self.layerComboBox.setLayer(layer)

        # Geofencing settings
        self.geofencingGroupBox.setChecked(
            self.__project_configuration.geofencing_is_active
        )

        geofencingLayer = QgsProject.instance().mapLayer(
            self.__project_configuration.geofencing_layer
        )
        self.geofencingLayerComboBox.setLayer(geofencingLayer)

        self.geofencingBehaviorComboBox.setCurrentIndex(
            self.geofencingBehaviorComboBox.findData(
                self.__project_configuration.geofencing_behavior
            )
        )

        self.geofencingShouldPreventDigitizingCheckBox.setChecked(
            self.__project_configuration.geofencing_should_prevent_digitizing
        )

        # Advanced settings
        digitizingLogsLayer = QgsProject.instance().mapLayer(
            self.__project_configuration.digitizing_logs_layer
        )
        self.digitizingLogsLayerComboBox.setLayer(digitizingLogsLayer)

        self.maximumImageWidthHeight.setClearValueMode(
            QgsSpinBox.CustomValue, self.tr("No restriction")
        )
        self.maximumImageWidthHeight.setValue(
            self.__project_configuration.maximum_image_width_height
        )

        tiles_size_index = self.baseMapTileSizeComboBox.findText(
            str(self.__project_configuration.base_map_tile_size)
        )
        if tiles_size_index >= 0:
            self.baseMapTileSizeComboBox.setCurrentIndex(tiles_size_index)

        self.baseMapTilesMinZoomLevelSpinBox.setValue(
            self.__project_configuration.base_map_tiles_min_zoom_level
        )
        self.baseMapTilesMaxZoomLevelSpinBox.setValue(
            self.__project_configuration.base_map_tiles_max_zoom_level
        )

        self.onlyOfflineCopyFeaturesInAoi.setChecked(
            self.__project_configuration.offline_copy_only_aoi
        )

        self.forceAutoPush.setChecked(self.__project_configuration.force_auto_push)
        self.forceAutoPushInterval.setEnabled(
            self.__project_configuration.force_auto_push
        )
        self.forceAutoPushInterval.setValue(
            self.__project_configuration.force_auto_push_interval_mins
        )

        self.directoriesConfigurationWidget.reload(
            {
                "attachment_dirs": [*self.preferences.value("attachmentDirs")],
                "data_dirs": [*self.preferences.value("dataDirs")],
            }
        )

        if self.unsupportedLayersList:
            self.unsupportedLayersLabel.setVisible(True)

            unsupported_layers_text = "<b>{}: </b>".format(self.tr("Warning"))
            unsupported_layers_text += self.tr(
                "There are unsupported layers in your project which will not be available in QField."
            )
            unsupported_layers_text += self.tr(
                " If needed, you can create a Base Map to include those layers in your packaged project."
            )
            self.unsupportedLayersLabel.setText(unsupported_layers_text)

    def apply(self):
        """
        Update layer configuration in project
        """
        self.cloudLayersConfigWidget.apply()
        self.cableLayersConfigWidget.apply()

        # Base map settings
        self.__project_configuration.create_base_map = (
            self.createBaseMapGroupBox.isChecked()
        )

        if self.singleLayerRadioButton.isChecked():
            self.__project_configuration.base_map_type = (
                ProjectProperties.BaseMapType.SINGLE_LAYER
            )
        else:
            self.__project_configuration.base_map_type = (
                ProjectProperties.BaseMapType.MAP_THEME
            )

        self.__project_configuration.base_map_theme = (
            self.mapThemeComboBox.currentText()
        )

        # try/pass layer ID fetching because the save button is global for all
        # project settings, not only QField
        try:
            self.__project_configuration.base_map_layer = (
                self.layerComboBox.currentLayer().id()
            )
        except AttributeError:
            pass

        # Geofencing settings
        self.__project_configuration.geofencing_is_active = (
            self.geofencingGroupBox.isChecked()
        )

        try:
            self.__project_configuration.geofencing_layer = (
                self.geofencingLayerComboBox.currentLayer().id()
                if self.geofencingLayerComboBox.currentLayer()
                else ""
            )
        except AttributeError:
            pass

        self.__project_configuration.geofencing_behavior = (
            self.geofencingBehaviorComboBox.currentData()
        )

        self.__project_configuration.geofencing_should_prevent_digitizing = (
            self.geofencingShouldPreventDigitizingCheckBox.isChecked()
        )

        # Advanced settings
        try:
            self.__project_configuration.digitizing_logs_layer = (
                self.digitizingLogsLayerComboBox.currentLayer().id()
                if self.digitizingLogsLayerComboBox.currentLayer()
                else ""
            )
        except AttributeError:
            pass

        self.__project_configuration.base_map_tile_size = int(
            self.baseMapTileSizeComboBox.currentText()
        )

        self.__project_configuration.base_map_tiles_min_zoom_level = (
            self.baseMapTilesMinZoomLevelSpinBox.value()
        )
        self.__project_configuration.base_map_tiles_max_zoom_level = (
            self.baseMapTilesMaxZoomLevelSpinBox.value()
        )

        self.__project_configuration.maximum_image_width_height = (
            self.maximumImageWidthHeight.value()
        )

        self.__project_configuration.offline_copy_only_aoi = (
            self.onlyOfflineCopyFeaturesInAoi.isChecked()
        )
        if self.areaOfInterestExtentWidget.isValid():
            self.__project_configuration.area_of_interest = (
                self.areaOfInterestExtentWidget.outputExtent().asWktPolygon()
            )
            self.__project_configuration.area_of_interest_crs = (
                self.areaOfInterestExtentWidget.outputCrs().authid()
            )
        else:
            self.__project_configuration.area_of_interest = ""
            self.__project_configuration.area_of_interest_crs = ""

        self.__project_configuration.force_auto_push = self.forceAutoPush.isChecked()
        self.__project_configuration.force_auto_push_interval_mins = (
            self.forceAutoPushInterval.value()
        )

        configuration = self.directoriesConfigurationWidget.createConfiguration()
        self.preferences.set_value("attachmentDirs", configuration["attachment_dirs"])
        self.preferences.set_value("dataDirs", configuration["data_dirs"])

        self.__project_configuration.map_themes_active_layer = (
            self.mapThemesConfigWidget.createConfiguration()
        )

        self.__project_configuration.stamping_font_style = self.stamping_font_style
        self.__project_configuration.stamping_horizontal_alignment = (
            self.stamping_horizontal_alignment
        )
        if self.stamping_image_decoration:
            self.__project_configuration.stamping_image_decoration = (
                QgsProject.instance()
                .pathResolver()
                .writePath(self.stamping_image_decoration)
            )
        else:
            self.__project_configuration.stamping_image_decoration = ""
        self.__project_configuration.stamping_details_template = (
            self.stamping_details_template
        )
        self.__project_configuration.force_stamping = self.force_stamping

    def show_image_stamping_settings(self):
        self.image_stamping_panel = ImageStampingConfigurationWidget(self)
        self.image_stamping_panel.set_font_style(self.stamping_font_style)
        self.image_stamping_panel.set_horizontal_alignment(
            self.stamping_horizontal_alignment
        )
        self.image_stamping_panel.set_image_decoration(self.stamping_image_decoration)
        self.image_stamping_panel.set_details_template(self.stamping_details_template)
        self.image_stamping_panel.set_force_stamping(self.force_stamping)
        self.image_stamping_panel.panelAccepted.connect(
            self.apply_image_stamping_settings
        )
        self.openPanel(self.image_stamping_panel)

    def apply_image_stamping_settings(self, panel):
        self.stamping_font_style = self.image_stamping_panel.font_style()
        self.stamping_horizontal_alignment = (
            self.image_stamping_panel.horizontal_alignment()
        )
        self.stamping_image_decoration = self.image_stamping_panel.image_decoration()
        self.stamping_details_template = self.image_stamping_panel.details_template()
        self.force_stamping = self.image_stamping_panel.force_stamping()
        self.image_stamping_panel = None

    def onForceAutoPushClicked(self, checked):
        self.forceAutoPushInterval.setEnabled(checked)

    def baseMapTypeChanged(self):
        self.baseMapLayerLabel.setVisible(self.singleLayerRadioButton.isChecked())
        self.layerComboBox.setVisible(self.singleLayerRadioButton.isChecked())
        self.baseMapMapThemeLabel.setVisible(
            not self.singleLayerRadioButton.isChecked()
        )
        self.mapThemeComboBox.setVisible(not self.singleLayerRadioButton.isChecked())
