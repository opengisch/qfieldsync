# -*- coding: utf-8 -*-

"""
/***************************************************************************
 QFieldSync
                              -------------------
        begin                : 2016
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
import tempfile

from qfieldsync.core.layer import LayerSource, SyncAction
from qfieldsync.core.project import ProjectProperties, ProjectConfiguration
from qfieldsync.utils.file_utils import copy_images
from qgis.PyQt.QtCore import (
    Qt,
    QObject,
    pyqtSignal,
    pyqtSlot,
    QCoreApplication
)
from qgis.PyQt.QtWidgets import (
    QApplication,
    QMessageBox
)
from qgis.core import (
    Qgis,
    QgsProject,
    QgsRasterLayer,
    QgsCubicRasterResampler,
    QgsBilinearRasterResampler,
    QgsApplication,
    QgsProcessingFeedback,
    QgsProcessingContext,
    QgsMapLayer,
    QgsProviderRegistry,
    QgsProviderMetadata,
    QgsEditorWidgetSetup,
    QgsValueRelationFieldFormatter,
)

import qgis


class OfflineConverter(QObject):
    progressStopped = pyqtSignal()
    task_progress_updated = pyqtSignal(int, int)
    total_progress_updated = pyqtSignal(int, int, str)
    message_emitted = pyqtSignal(str, Qgis.MessageLevel)

    def __init__(self, project, export_folder, extent, offline_editing):
        super(OfflineConverter, self).__init__(parent=None)
        self.__max_task_progress = 0
        self.__offline_layers = list()
        self.__offline_layer_names = list()
        self.__convertor_progress = None  # for processing feedback
        self.__layers = list()

        # elipsis workaround
        self.trUtf8 = self.tr

        self.export_folder = export_folder
        self.extent = extent
        self.offline_editing = offline_editing
        self.project_configuration = ProjectConfiguration(project)

        offline_editing.layerProgressUpdated.connect(self.on_offline_editing_next_layer)
        offline_editing.progressModeSet.connect(self.on_offline_editing_max_changed)
        offline_editing.progressUpdated.connect(self.offline_editing_task_progress)

    def convert(self):
        """
        Convert the project to a portable project.

        :param offline_editing: The offline editing instance
        :param export_folder:   The folder to export to
        """

        project = QgsProject.instance()
        original_project = project

        original_project_path = project.fileName()
        project_filename = project.baseName()

        # Write a backup of the current project to a temporary file
        project_backup_folder = tempfile.mkdtemp()
        backup_project_path = os.path.join(project_backup_folder, project_filename + '.qgs')
        QgsProject.instance().write(backup_project_path)

        try:
            if not os.path.exists(self.export_folder):
                os.makedirs(self.export_folder)

            QApplication.setOverrideCursor(Qt.WaitCursor)

            self.__offline_layers = list()
            self.__offline_layer_names = list()
            self.__layers = list(project.mapLayers().values())

            original_layer_info = {}
            for layer in self.__layers:
                original_layer_info[layer.id()] = (
                    layer.source(),
                    layer.name(),
                    layer.fields() if hasattr(layer, 'fields') else None
                )

            # We store the pks of the original vector layers
            # and we check that the primary key fields names don't
            # have a comma in the name
            original_pk_fields_by_layer_name = {}
            for layer in self.__layers:
                if layer.type() == QgsMapLayer.VectorLayer:
                    keys = []
                    for idx in layer.primaryKeyAttributes():
                        key = layer.fields()[idx].name()
                        assert (',' not in key), 'Comma in field names not allowed'
                        keys.append(key)
                    original_pk_fields_by_layer_name[layer.name()] = ','.join(keys)

            self.total_progress_updated.emit(0, 1, self.trUtf8('Creating base map…'))
            # Create the base map before layers are removed
            if self.project_configuration.create_base_map:
                if 'processing' not in qgis.utils.plugins:
                    QMessageBox.warning(None, self.tr('QFieldSync requires processing'), self.tr('Creating a basemap with QFieldSync requires the processing plugin to be enabled. Processing is not enabled on your system. Please go to Plugins > Manage and Install Plugins and enable processing.'))
                    return

                if self.project_configuration.base_map_type == ProjectProperties.BaseMapType.SINGLE_LAYER:
                    self.createBaseMapLayer(None, self.project_configuration.base_map_layer,
                                            self.project_configuration.base_map_tile_size,
                                            self.project_configuration.base_map_mupp)
                else:
                    self.createBaseMapLayer(self.project_configuration.base_map_theme, None,
                                            self.project_configuration.base_map_tile_size,
                                            self.project_configuration.base_map_mupp)

            # Loop through all layers and copy/remove/offline them
            pathResolver = QgsProject.instance().pathResolver()
            copied_files = list()
            for current_layer_index, layer in enumerate(self.__layers):
                self.total_progress_updated.emit(current_layer_index - len(self.__offline_layers), len(self.__layers),
                                                 self.trUtf8('Copying layers…'))

                layer_source = LayerSource(layer)
                if not layer_source.is_supported:
                     project.removeMapLayer(layer)
                     continue

                if layer.dataProvider() is not None:
                    md = QgsProviderRegistry.instance().providerMetadata(layer.dataProvider().name())
                    if md is not None:
                        decoded = md.decodeUri(layer.source())
                        if "path" in decoded:
                            path = pathResolver.writePath(decoded["path"])
                            if path.startswith("localized:"):
                                # Layer stored in localized data path, skip
                                continue

                if layer_source.action == SyncAction.OFFLINE:
                    if self.project_configuration.offline_copy_only_aoi and not self.project_configuration.offline_copy_only_selected_features:
                        layer.selectByRect(self.extent)
                    elif self.project_configuration.offline_copy_only_aoi and self.project_configuration.offline_copy_only_selected_features:
                        # This option is only possible via API
                        QgsApplication.instance().messageLog().logMessage(self.tr(
                            'Both "Area of Interest" and "only selected features" options were enabled, tha latter takes precedence.'),
                            'QFieldSync')
                    self.__offline_layers.append(layer)
                    self.__offline_layer_names.append(layer.name())

                    # Store the primary key field name(s) as comma separated custom property
                    if layer.type() == QgsMapLayer.VectorLayer:
                        key_fields = ','.join([layer.fields()[x].name() for x in layer.primaryKeyAttributes()])
                        layer.setCustomProperty('QFieldSync/sourceDataPrimaryKeys', key_fields)

                elif layer_source.action == SyncAction.NO_ACTION:
                    copied_files = layer_source.copy(self.export_folder, copied_files)
                elif layer_source.action == SyncAction.KEEP_EXISTENT:
                    layer_source.copy(self.export_folder, copied_files, True)
                elif layer_source.action == SyncAction.REMOVE:
                    project.removeMapLayer(layer)

            project_path = os.path.join(self.export_folder, project_filename + "_qfield.qgs")

            # save the original project path
            ProjectConfiguration(project).original_project_path = original_project_path

            # save the offline project twice so that the offline plugin can "know" that it's a relative path
            QgsProject.instance().write(project_path)

            # export the DCIM folder
            copy_images(os.path.join(os.path.dirname(original_project_path), "DCIM"),
                        os.path.join(os.path.dirname(project_path), "DCIM"))
            try:
                # Run the offline plugin for gpkg
                gpkg_filename = "data.gpkg"
                if self.__offline_layers:
                    offline_layer_ids = [l.id() for l in self.__offline_layers]
                    only_selected = self.project_configuration.offline_copy_only_aoi or self.project_configuration.offline_copy_only_selected_features
                    if Qgis.QGIS_VERSION_INT < 31601:
                        if not self.offline_editing.convertToOfflineProject(self.export_folder, gpkg_filename,
                                                                            offline_layer_ids,
                                                                            only_selected,
                                                                            self.offline_editing.GPKG):
                            raise Exception(self.tr("Error trying to convert layers to offline layers"))
                    else:
                        if not self.offline_editing.convertToOfflineProject(self.export_folder, gpkg_filename,
                                                                            offline_layer_ids,
                                                                            only_selected,
                                                                            self.offline_editing.GPKG,
                                                                            None):
                            raise Exception(self.tr("Error trying to convert layers to offline layers"))
            except AttributeError:
                # Run the offline plugin for spatialite
                spatialite_filename = "data.sqlite"
                if self.__offline_layers:
                    offline_layer_ids = [l.id() for l in self.__offline_layers]
                    only_selected = self.project_configuration.offline_copy_only_aoi or self.project_configuration.offline_copy_only_selected_features
                    if Qgis.QGIS_VERSION_INT < 31601:
                        if not self.offline_editing.convertToOfflineProject(self.export_folder, spatialite_filename,
                                                                            offline_layer_ids,
                                                                            only_selected,
                                                                            self.offline_editing.SpatiaLite):
                            raise Exception(self.tr("Error trying to convert layers to offline layers"))
                    else:
                        if not self.offline_editing.convertToOfflineProject(self.export_folder, spatialite_filename,
                                                                            offline_layer_ids,
                                                                            only_selected,
                                                                            self.offline_editing.SpatiaLite,
                                                                            None):
                            raise Exception(self.tr("Error trying to convert layers to offline layers"))

            # Disable project options that could create problems on a portable
            # project with offline layers
            if self.__offline_layers:
                QgsProject.instance().setEvaluateDefaultValues(False)
                QgsProject.instance().setAutoTransaction(False)

                # check if value relations point to offline layers and adjust if necessary
                for layer in project.mapLayers().values():
                    layer_source = LayerSource(layer)

                    if layer.type() == QgsMapLayer.VectorLayer:

                        # Before QGIS 3.14 the custom properties of a layer are not
                        # kept into the new layer during the conversion to offline project
                        # So we try to identify the new created layer by its name and
                        # we set the custom properties again.
                        if not layer.customProperty('QFieldSync/cloudPrimaryKeys'):
                            original_layer_name = layer.name().rsplit(' ', 1)[0]
                            stored_fields = original_pk_fields_by_layer_name.get(original_layer_name, None)
                            if stored_fields:
                                layer.setCustomProperty(
                                    'QFieldSync/sourceDataPrimaryKeys',
                                    stored_fields)
                            original_layer_fields = layer.fields()
                        else:
                            (
                                original_layer_source,
                                original_layer_name,
                                original_layer_fields,
                            ) = original_layer_info[layer.customProperty("remoteLayerId")]

                        for field_name in layer_source.visible_fields_names():
                            if field_name not in original_layer_fields.names():
                                # handles the `fid` column, that is present only for gpkg
                                continue

                            field = original_layer_fields.field(field_name)
                            ews = field.editorWidgetSetup()

                            if ews.type() == 'ValueRelation':
                                widget_config = ews.config()
                                online_layer_id = widget_config['Layer']

                                if online_layer_id not in original_layer_info:
                                    offline_referenced_layer = QgsValueRelationFieldFormatter.resolveLayer(widget_config, project)

                                    if offline_referenced_layer:
                                        online_layer_id = offline_referenced_layer.customProperty("remoteLayerId")

                                if online_layer_id not in original_layer_info:
                                    self.message_emitted.emit(
                                        self.tr('Field "{}" in layer "{}" has no configured layer in the value relation widget.').format(field.name(), layer.name()),
                                        Qgis.MessageLevel.Warning
                                    )
                                    continue
                                if project.mapLayer(online_layer_id):
                                    continue

                                layer_id = None
                                loose_layer_id = None
                                for offline_layer in project.mapLayers().values():
                                    if offline_layer.customProperty('remoteSource') == original_layer_info[online_layer_id][0]:
                                        #  First try strict matching: the offline layer should have a "remoteSource" property
                                        layer_id = offline_layer.id()
                                        break
                                    elif Qgis.QGIS_VERSION_INT < 31601 and offline_layer.name().startswith(original_layer_info[online_layer_id][1] + ' ') or \
                                            Qgis.QGIS_VERSION_INT >= 31601 and offline_layer.name() == original_layer_info[online_layer_id][1]:
                                        #  If that did not work, go with loose matching
                                        #  On older versions (<31601) the offline layer should start with the online layer name + a translated version of " (offline)"
                                        loose_layer_id = offline_layer.id()
                                widget_config['Layer'] = layer_id or loose_layer_id
                                offline_ews = QgsEditorWidgetSetup(ews.type(), widget_config)
                                layer.setEditorWidgetSetup(layer.fields().indexOf(field.name()), offline_ews)

            # Now we have a project state which can be saved as offline project
            QgsProject.instance().write(project_path)
        finally:
            # We need to let the app handle events before loading the next project or QGIS will crash with rasters
            QCoreApplication.processEvents()
            QgsProject.instance().clear()
            QCoreApplication.processEvents()
            QgsProject.instance().read(backup_project_path)
            QgsProject.instance().setFileName(original_project_path)
            QApplication.restoreOverrideCursor()

        self.offline_editing.layerProgressUpdated.disconnect(self.on_offline_editing_next_layer)
        self.offline_editing.progressModeSet.disconnect(self.on_offline_editing_max_changed)
        self.offline_editing.progressUpdated.disconnect(self.offline_editing_task_progress)

        self.total_progress_updated.emit(100, 100, self.tr('Finished'))

    def createBaseMapLayer(self, map_theme, layer, tile_size, map_units_per_pixel):
        """
        Create a basemap from map layer(s)

        :param dataPath:             The path where the basemap should be writtent to
        :param extent:               The extent rectangle in which data shall be fetched
        :param map_theme:            The name of the map theme to be rendered
        :param layer:                A layer id to be rendered. Will only be used if map_theme is None.
        :param tile_size:            The extent rectangle in which data shall be fetched
        :param map_units_per_pixel:  Number of map units per pixel (1: 1 m per pixel, 10: 10 m per pixel...)
        """
        extent_string = '{},{},{},{}'.format(self.extent.xMinimum(), self.extent.xMaximum(), self.extent.yMinimum(),
                                             self.extent.yMaximum())

        alg = QgsApplication.instance().processingRegistry().createAlgorithmById('qgis:rasterize')
        
        # passing the LAYER and LAYERS parameters since QGIS 3.10 uses the LAYER parameter and 3.16+ uses the LAYERS parameter instead
        # keeping both ensures backward compatibility
        params = {
            'EXTENT': extent_string,
            'MAP_THEME': map_theme,
            'LAYER': layer,
            'LAYERS': [layer],
            'MAP_UNITS_PER_PIXEL': map_units_per_pixel,
            'TILE_SIZE': tile_size,
            'MAKE_BACKGROUND_TRANSPARENT': False,

            'OUTPUT': os.path.join(self.export_folder, 'basemap.gpkg')
        }

        feedback = QgsProcessingFeedback()
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())

        results, ok = alg.run(params, context, feedback)

        new_layer = QgsRasterLayer(results['OUTPUT'], self.tr('Basemap'))

        resample_filter = new_layer.resampleFilter()
        resample_filter.setZoomedInResampler(QgsCubicRasterResampler())
        resample_filter.setZoomedOutResampler(QgsBilinearRasterResampler())
        self.project_configuration.project.addMapLayer(new_layer, False)
        layer_tree = QgsProject.instance().layerTreeRoot()
        layer_tree.insertLayer(len(layer_tree.children()), new_layer)

    @pyqtSlot(int, int)
    def on_offline_editing_next_layer(self, layer_index, layer_count):
        msg = self.trUtf8('Packaging layer {layer_name}…').format(layer_name=self.__offline_layer_names[layer_index - 1])
        self.total_progress_updated.emit(layer_index, layer_count, msg)

    @pyqtSlot('QgsOfflineEditing::ProgressMode', int)
    def on_offline_editing_max_changed(self, _, mode_count):
        self.__max_task_progress = mode_count

    @pyqtSlot(int)
    def offline_editing_task_progress(self, progress):
        self.task_progress_updated.emit(progress, self.__max_task_progress)

    def convertorProcessingProgress(self):
        """
        Will create a new progress object for processing to get feedback from the basemap
        algorithm.
        """

        class ConverterProgress(QObject):
            progress_updated = pyqtSignal(int, int)

            def __init__(self):
                QObject.__init__(self)

            def error(self, msg):
                pass

            def setText(self, msg):
                pass

            def setPercentage(self, i):
                self.progress_updated.emit(i, 100)
                QCoreApplication.processEvents()

            def setInfo(self, msg):
                pass

            def setCommand(self, msg):
                pass

            def setDebugInfo(self, msg):
                pass

            def setConsoleInfo(self, msg):
                pass

            def close(self):
                pass

        if not self.__convertor_progress:
            self.__convertor_progress = ConverterProgress()
            self.__convertor_progress.progress_updated.connect(self.task_progress_updated)

        return self.__convertor_progress
