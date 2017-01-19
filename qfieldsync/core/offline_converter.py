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

import processing

from qfieldsync.core.layer import LayerSource, SyncAction
from qfieldsync.core.project import ProjectProperties, ProjectConfiguration
from qgis.PyQt.QtCore import (
    Qt,
    QObject,
    pyqtSignal,
    pyqtSlot,
    QCoreApplication
)
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsCubicRasterResampler,
    QgsBilinearRasterResampler
)


class OfflineConverter(QObject):
    progressStopped = pyqtSignal()
    task_progress_updated = pyqtSignal(int, int)
    total_progress_updated = pyqtSignal(int, int, str)

    def __init__(self, project, export_folder, extent, offline_editing):
        super(OfflineConverter, self).__init__(parent=None)
        self.__max_task_progress = 0
        self.__offline_layers = list()
        self.__convertor_progress = None  # for processing feedback
        self.__layers = list()

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

        original_project_path = project.fileName()
        project_filename, _ = os.path.splitext(os.path.basename(original_project_path))

        # Write a backup of the current project to a temporary file
        project_backup_folder = tempfile.mkdtemp()
        backup_project_path = os.path.join(project_backup_folder, project_filename + '.qgs')
        QgsProject.instance().write(backup_project_path)

        try:
            if not os.path.exists(self.export_folder):
                os.makedirs(self.export_folder)

            QApplication.setOverrideCursor(Qt.WaitCursor)

            self.__offline_layers = list()
            self.__layers = project.mapLayers().values()

            self.total_progress_updated.emit(0, 1, self.tr('Creating base map'))
            # Create the base map before layers are removed
            if self.project_configuration.create_base_map:
                if self.project_configuration.base_map_type == ProjectProperties.BaseMapType.SINGLE_LAYER:
                    self.createBaseMapLayer(None, self.project_configuration.base_map_layer,
                                            self.project_configuration.base_map_tile_size,
                                            self.project_configuration.base_map_mupp)
                else:
                    self.createBaseMapLayer(self.project_configuration.base_map_theme, None,
                                            self.project_configuration.base_map_tile_size,
                                            self.project_configuration.base_map_mupp)

            # Loop through all layers and copy/remove/offline them
            for current_layer_index, layer in enumerate(self.__layers):
                self.total_progress_updated.emit(current_layer_index - len(self.__offline_layers), len(self.__layers),
                                                 self.tr('Copying layers'))
                layer_source = LayerSource(layer)

                if layer_source.action == SyncAction.OFFLINE:
                    if self.project_configuration.offline_copy_only_aoi:
                        layer.selectByRect(self.extent)
                    self.__offline_layers.append(layer)
                elif layer_source.action == SyncAction.NO_ACTION:
                    layer_source.copy(self.export_folder)
                elif layer_source.action == SyncAction.REMOVE:
                    project.removeMapLayer(layer)

            project_path = os.path.join(self.export_folder, project_filename + "_qfield.qgs")

            # save the offline project twice so that the offline plugin can "know" that it's a relative path
            QgsProject.instance().write(project_path)

            # Run the offline plugin
            spatialite_filename = "data.sqlite"
            if self.__offline_layers:
                offline_layer_ids = [l.id() for l in self.__offline_layers]
                if not self.offline_editing.convertToOfflineProject(self.export_folder, spatialite_filename,
                                                                    offline_layer_ids,
                                                                    self.project_configuration.offline_copy_only_aoi):
                    raise Exception(self.tr("Error trying to convert layers to offline layers"))

            # Now we have a project state which can be saved as offline project
            QgsProject.instance().write(project_path)
        finally:
            # We need to let the app handle events before loading the next project or QGIS will crash with rasters
            QCoreApplication.processEvents()
            QgsProject.instance().read(backup_project_path)
            QgsProject.instance().setFileName(original_project_path)
            QApplication.restoreOverrideCursor()

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

        alg = processing.Processing.getAlgorithm('qfieldsync:basemap').getCopy()

        alg.setParameterValue('EXTENT', extent_string)
        alg.setParameterValue('MAP_THEME', map_theme)
        alg.setParameterValue('LAYER', layer)
        alg.setParameterValue('MAP_UNITS_PER_PIXEL', map_units_per_pixel)
        alg.setParameterValue('TILE_SIZE', tile_size)
        alg.setOutputValue('OUTPUT_LAYER', os.path.join(self.export_folder, 'basemap.gpkg'))
        alg.execute(progress=self.convertorProcessingProgress())

        out = alg.outputs[0]
        new_layer = QgsRasterLayer(out.value, self.tr('Basemap'))

        resample_filter = new_layer.resampleFilter()
        resample_filter.setZoomedInResampler(QgsCubicRasterResampler())
        resample_filter.setZoomedOutResampler(QgsBilinearRasterResampler())
        self.project_configuration.project.addMapLayer(new_layer, False)
        layer_tree = QgsProject.instance().layerTreeRoot()
        layer_tree.insertLayer(len(layer_tree.children()), new_layer)

    @pyqtSlot(int, int)
    def on_offline_editing_next_layer(self, layer_index, layer_count):
        self.total_progress_updated.emit(layer_index, layer_count, self.tr(u'Packaging layer {layer_name}'.format(
            layer_name=self.__offline_layers[layer_index - 1].name(), layer_index=layer_index,
            layer_count=layer_count)))

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
