import os
import tempfile

import processing

from qfieldsync.core.layer import LayerSource, SyncAction
from qfieldsync.core.project import ProjectProperties, ProjectConfiguration
from qgis.PyQt.QtCore import (
    QFileInfo,
    Qt,
    QObject,
    pyqtSignal,
    QTimer
)
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import (
    QgsProject,
    QgsMapLayerRegistry,
    QgsRasterLayer
)


class OfflineConverter(QObject):
    progressStopped = pyqtSignal()
    layerProgressUpdated = pyqtSignal(int, int)
    progressModeSet = pyqtSignal('QgsOfflineEditing::ProgressMode', int)
    progressUpdated = pyqtSignal(int)
    progressJob = pyqtSignal(str)
    __offline_layers = list()
    __convertor_progress = None  # for processing feedback

    def __init__(self, project, export_folder, extent, offline_editing):
        super(OfflineConverter, self).__init__(parent=None)
        self.export_folder = export_folder
        self.extent = extent
        self.offline_editing = offline_editing
        self.project_configuration = ProjectConfiguration(project)

        offline_editing.progressStopped.connect(self.progressStopped)
        offline_editing.layerProgressUpdated.connect(self.onLayerProgressUpdated)
        offline_editing.progressModeSet.connect(self.progressModeSet)
        offline_editing.progressUpdated.connect(self.progressUpdated)

    def convert(self):
        """
        Convert the project to a portable project.

        :param offline_editing: The offline editing instance
        :param export_folder:   The folder to export to
        """

        original_project_path = QgsProject.instance().fileName()
        project_filename, _ = os.path.splitext(os.path.basename(original_project_path))

        # Write a backup of the current project to a temporary file
        project_backup_folder = tempfile.mkdtemp()
        backup_project_path = os.path.join(project_backup_folder, project_filename + '.qgs')
        QgsProject.instance().write(QFileInfo(backup_project_path))

        try:
            if not os.path.exists(self.export_folder):
                os.makedirs(self.export_folder)

            QApplication.setOverrideCursor(Qt.WaitCursor)

            layers = QgsMapLayerRegistry.instance().mapLayers().values()

            self.progressJob.emit(self.tr('Creating base map'))
            # Create the base map before layers are removed
            if self.project_configuration.create_base_map:
                if self.project_configuration.base_map_type == ProjectProperties.BaseMapType.SINGLE_LAYER:
                    self.createBaseMapLayer(None, self.project_configuration.base_map_layer, self.project_configuration.base_map_tile_size, self.project_configuration.base_map_mupp)
                else:
                    self.createBaseMapLayer(self.project_configuration.base_map_theme, None, self.project_configuration.base_map_tile_size, self.project_configuration.base_map_mupp)

            self.progressJob.emit(self.tr('Copying layers'))
            # Loop through all layers and copy/remove/offline them
            self.__offline_layers = list()
            for layer in layers:
                layer_source = LayerSource(layer)

                if layer_source.action == SyncAction.OFFLINE:
                    if self.project_configuration.offline_copy_only_aoi:
                        layer.selectByRect(self.extent)
                    self.__offline_layers.append(layer)
                elif layer_source.action == SyncAction.NO_ACTION:
                    layer_source.copy(self.export_folder)
                elif layer_source.action == SyncAction.REMOVE:
                    QgsMapLayerRegistry.instance().removeMapLayer(layer)

            project_path = os.path.join(self.export_folder, project_filename + "_qfield.qgs")

            # save the offline project twice so that the offline plugin can "know" that it's a relative path
            QgsProject.instance().write(QFileInfo(project_path))

            self.progressJob.emit(self.tr('Copying offline layers'))
            # Run the offline plugin
            spatialite_filename = "data.sqlite"
            if self.__offline_layers:
                offline_layer_ids = [l.id() for l in self.__offline_layers]
                if not self.offline_editing.convertToOfflineProject(self.export_folder, spatialite_filename,
                                                                    offline_layer_ids, self.project_configuration.offline_copy_only_aoi):
                    self.progressJob.emit(self.tr('Failure'))
                    raise Exception(self.tr("Error trying to convert layers to offline layers"))

            # Now we have a project state which can be saved as offline project
            QgsProject.instance().write(QFileInfo(project_path))
        finally:
            def reload_original_project():
                QgsProject.instance().read(QFileInfo(backup_project_path))
                QgsProject.instance().setFileName(original_project_path)

            # Calling this directly crashes QGIS 2.18 when loading WMS layers
            QTimer.singleShot(100, lambda: reload_original_project())
            QApplication.restoreOverrideCursor()

        self.progressJob.emit(self.tr('Finished'))

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
        QgsMapLayerRegistry.instance().addMapLayer(new_layer, False)
        layer_tree = QgsProject.instance().layerTreeRoot()
        layer_tree.insertLayer(len(layer_tree.children()), new_layer)

    def onLayerProgressUpdated(self, layer_index, layer_count):
        print(self.tr('Preparing layer {layer_name} ({layer_index}/{layer_count})'.format(
            layer_name=self.__offline_layers[layer_index - 1].name(), layer_index=layer_index,
            layer_count=layer_count)))
        self.progressJob.emit(self.tr('Preparing layer {layer_name} ({layer_index}/{layer_count})'.format(
            layer_name=self.__offline_layers[layer_index - 1].name(), layer_index=layer_index,
            layer_count=layer_count)))

    def convertorProcessingProgress(self):
        """
        Will create a new progress object for processing to get feedback from the basemap
        algorithm.
        """

        class ConverterProgress(QObject):
            progressUpdated = pyqtSignal(int, int)

            def __init__(self):
                QObject.__init__(self)

            def error(self, msg):
                pass

            def setText(self, msg):
                pass

            def setPercentage(self, i):
                self.progressUpdated.emit(i, 100)

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
            self.__convertor_progress.progressUpdated.connect(self.layerProgressUpdated)

        return self.__convertor_progress
