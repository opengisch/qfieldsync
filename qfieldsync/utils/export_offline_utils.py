import os
import shutil

from processing import ProcessingConfig
from processing.gui import RenderingStyles
from qgis.PyQt.QtCore import (
    QFileInfo,
    Qt,
    QObject,
    pyqtSignal)
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import (
    QgsProject,
    QgsOfflineEditing,
    QgsMapLayerRegistry,
    QgsRasterLayer
)
import processing

from qfieldsync.utils.data_source_utils import SHP_EXTENSIONS, change_layer_data_source
from qfieldsync.utils.file_utils import fileparts

from qfieldsync.config import (
    OFFLINE,
    LAYER_ACTION,
    NO_ACTION,
    REMOVE,
    BASE_MAP_TYPE,
    BASE_MAP_TYPE_SINGLE_LAYER,
    CREATE_BASE_MAP,
    BASE_MAP_THEME,
    BASE_MAP_LAYER, BASE_MAP_TILE_SIZE, BASE_MAP_MUPP)


class OfflineConvertor(QObject):
    progressStopped = pyqtSignal()
    layerProgressUpdated = pyqtSignal(int, int)
    progressModeSet = pyqtSignal('QgsOfflineEditing::ProgressMode', int)
    progressUpdated = pyqtSignal(int)
    progressJob = pyqtSignal(str)
    __offline_layers = list()
    __convertor_progress = None  # for processing feedback

    def __init__(self, export_folder, extent, offline_editing):
        super(OfflineConvertor, self).__init__(parent=None)
        self.export_folder = export_folder
        self.extent = extent
        self.offline_editing = offline_editing

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

        existing_filepath = QgsProject.instance().fileName()
        existing_fn, _ = os.path.splitext(os.path.basename(existing_filepath))

        if not os.path.exists(self.export_folder):
            os.mkdir(self.export_folder)

        QApplication.setOverrideCursor(Qt.WaitCursor)

        self.progressJob.emit(self.tr('Creating base map'))
        # Create the base map before layers are removed
        createBaseMap = QgsProject.instance().readBoolEntry('qfieldsync', CREATE_BASE_MAP, False)
        if createBaseMap:
            baseMapType, _ = QgsProject.instance().readEntry('qfieldsync', BASE_MAP_TYPE)
            tile_size, _ = QgsProject.instance().readNumEntry('qfieldsync', BASE_MAP_TILE_SIZE, 1024)
            map_units_per_pixel, _ = QgsProject.instance().readNumEntry('qfieldsync', BASE_MAP_MUPP, 100)

            if baseMapType == BASE_MAP_TYPE_SINGLE_LAYER:
                baseMapLayer, _ = QgsProject.instance().readEntry('qfieldsync', BASE_MAP_LAYER)
                self.createBaseMapLayer(None, baseMapLayer, tile_size, map_units_per_pixel)
            else:
                baseMapTheme, _ = QgsProject.instance().readEntry('qfieldsync', BASE_MAP_THEME)
                self.createBaseMapLayer(baseMapTheme, None, tile_size, map_units_per_pixel)

        self.progressJob.emit(self.tr('Copying layers'))
        # Loop through all layers and copy/remove/offline them
        self.__offline_layers = list()
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if layer.customProperty(LAYER_ACTION) == OFFLINE:
                layer.selectByRect(self.extent)
                self.__offline_layers.append(layer)
            elif layer.customProperty(LAYER_ACTION) == NO_ACTION:
                self.copy_layer(layer)
            elif layer.customProperty(LAYER_ACTION) == REMOVE:
                QgsMapLayerRegistry.instance().removeMapLayer(layer)

        project_filename = os.path.join(self.export_folder, existing_fn + "_qfield.qgs")

        # save the offline project twice so that the offline plugin can "know" that it's a relative path
        QgsProject.instance().write(QFileInfo(project_filename))

        self.progressJob.emit(self.tr('Copying offline layers'))
        # Run the offline plugin
        spatialite_filename = "data.sqlite"
        success = self.offline_editing.convertToOfflineProject(self.export_folder, spatialite_filename,
                                                               [l.id() for l in self.__offline_layers])

        QApplication.restoreOverrideCursor()
        # Now we have a project state which can be saved as offline project
        QgsProject.instance().write(QFileInfo(project_filename))

        if not success:
            self.progressJob.emit(self.tr('Failure'))
            raise Exception(self.tr("Error trying to convert layers to offline layers"))

        self.progressJob.emit(self.tr('Finished'))

    def extensionlist_for_layer(self, file_path):
        """
        Returns a list of extensions that should be copied for the
        provided file_path. This is required for shapefiles because they
        consist of a multitude of files that need to be copied.
        For most layer types this will return a list with a single entry
        """
        parent, fn, ext = fileparts(file_path)

        if ext == '.shp':
            return SHP_EXTENSIONS
        else:
            return [ext]

    def copy_layer(self, layer):
        """
        Copy a layer to the qfield project.
        We might get a file, in this case we copy it.
        We might also get something else like a WMS. In this case we just don't do anything at all.

        :param dataPath: The target folder
        :param layer: The layer to copy
        """
        file_path = layer.source()
        if os.path.isfile(file_path):
            parent, fn, ext = fileparts(file_path)
            new_file_path = os.path.join(self.export_folder, fn + ext)

            for extra_ext in self.extensionlist_for_layer(file_path):
                source_file_path = os.path.join(parent, fn + extra_ext)
                if os.path.exists(source_file_path):
                    shutil.copy(source_file_path, self.export_folder)

            change_layer_data_source(layer, new_file_path)

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

        class ConvertorProgress(QObject):
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
            self.__convertor_progress = ConvertorProgress()
            self.__convertor_progress.progressUpdated.connect(self.layerProgressUpdated)

        return self.__convertor_progress
