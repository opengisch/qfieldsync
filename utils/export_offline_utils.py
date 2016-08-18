import os
import shutil

from PyQt4 import QtCore
from qgis.core import QgsProject, QgsOfflineEditing

from QFieldSync.utils.data_source_utils import SHP_EXTENSIONS, change_layer_data_source, \
    project_get_always_offline_layers
from QFieldSync.utils.file_utils import fileparts
from QFieldSync.config import OFFLINE


def get_layer_ids_to_offline_convert(remote_layers, remote_save_mode):
    layer_ids = []
    if remote_save_mode == OFFLINE:
        for layer in remote_layers:
            layer_ids.append(layer.id())

    for layer in project_get_always_offline_layers():
        layer_ids.append(layer.id())
    return layer_ids


def handle_shpfiles(dataPath, shpfile_layers):
    for shpfile_layer in shpfile_layers:
        shpfile = shpfile_layer.source()
        parent, fn, ext = fileparts(shpfile)
        new_file_path = os.path.join(dataPath, fn + ext)
        # copy surrounding files as well
        for ext in SHP_EXTENSIONS:
            file_path = os.path.join(parent, fn + ext)
            if os.path.exists(file_path):
                shutil.copy(file_path, dataPath)
        change_layer_data_source(shpfile_layer, new_file_path)


def handle_rasters(dataPath, raster_layers):
    for raster_layer in raster_layers:
        file_path = raster_layer.source()
        new_file_path = os.path.join(dataPath, os.path.basename(file_path))
        shutil.copy(file_path, new_file_path)
        change_layer_data_source(raster_layer, new_file_path)


def offline_convert(vector_layer_ids, raster_layers, shpfile_layers, export_folder):
    existing_filepath = QgsProject.instance().fileName()
    existing_fn, ext = os.path.splitext(os.path.basename(existing_filepath))
    dataPath = export_folder
    if not os.path.exists(dataPath):
        os.mkdir(dataPath)
    dbPath = "data.sqlite"
    success = QgsOfflineEditing().convertToOfflineProject(dataPath, dbPath, vector_layer_ids)
    if not success:
        raise Exception("Converting to offline project did not succeed")
        # Now we have a project state which can be saved as offline project
    # TODO more file-based vectors ??
    handle_rasters(dataPath, raster_layers)
    handle_shpfiles(dataPath, shpfile_layers)
    # Now we have a project state which can be saved as offline project
    QgsProject.instance().write(QtCore.QFileInfo(os.path.join(dataPath, existing_fn + "_offline" + ext)))
    return dataPath
