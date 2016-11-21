import os
import shutil

from qgis.PyQt.QtCore import QFileInfo, Qt
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import (
    QgsProject,
    QgsOfflineEditing,
    QgsMapLayerRegistry
)

from qfieldsync.utils.data_source_utils import SHP_EXTENSIONS, change_layer_data_source, \
    project_get_always_offline_layers, is_shapefile_layer
from qfieldsync.utils.file_utils import fileparts

from qfieldsync.config import (
    OFFLINE,
    LAYER_ACTION, NO_ACTION, REMOVE)

def get_layer_ids_to_offline_convert(remote_layers, remote_save_mode):
    layer_ids = []
    if remote_save_mode == OFFLINE:
        for layer in remote_layers:
            layer_ids.append(layer.id())

    for layer in project_get_always_offline_layers():
        if not is_shapefile_layer(layer):
            # Ignore shapefiles because they should be copied over as files rather
            # than getting converted to spatialite
            layer_ids.append(layer.id())
    return layer_ids


def extensionlist_for_layer(file_path):
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

def copy_layer(dataPath, layer):
    file_path = layer.source()
    parent, fn, ext = fileparts(file_path)
    new_file_path = os.path.join(dataPath, fn + ext)

    for extra_ext in extensionlist_for_layer(file_path):
        source_file_path = os.path.join(parent, fn + extra_ext)
        if os.path.exists(source_file_path):
            shutil.copy(source_file_path, dataPath)

    change_layer_data_source(layer, new_file_path)


def offline_convert(offline_editing, export_folder):

    existing_filepath = QgsProject.instance().fileName()
    existing_fn, _ = os.path.splitext(os.path.basename(existing_filepath))
    dataPath = export_folder
    if not os.path.exists(dataPath):
        os.mkdir(dataPath)

    offline_layers = list()
    for layer in QgsMapLayerRegistry.instance().mapLayers().values():
        if layer.customProperty(LAYER_ACTION) == OFFLINE:
            offline_layers.append(layer.id())
        elif layer.customProperty(LAYER_ACTION) == NO_ACTION:
            copy_layer(dataPath, layer)
        elif layer.customProperty(LAYER_ACTION) == REMOVE:
            QgsMapLayerRegistry.instance().removeMapLayer(layer)

    # Run the offline plugin
    dbPath = "data.sqlite"

    # save the offline project twice so that the offline plugin can "know" that it's a relative path
    QgsProject.instance().write(QFileInfo(os.path.join(dataPath, existing_fn + "_qfield.qgs")))

    QApplication.setOverrideCursor(Qt.WaitCursor)
    success = offline_editing.convertToOfflineProject(dataPath, dbPath, offline_layers)

    QApplication.restoreOverrideCursor()
    if not success:
        raise Exception("Converting to offline project did not succeed")
    # Now we have a project state which can be saved as offline project
    QgsProject.instance().write(QFileInfo(os.path.join(dataPath, existing_fn + "_qfield.qgs")))
    return dataPath
