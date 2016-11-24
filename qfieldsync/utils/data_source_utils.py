import os

from qgis.PyQt.QtXml import *
from qgis.core import (
    QgsMapLayerRegistry,
    QgsProject,
    QgsOfflineEditing,
    QgsRasterLayer,
    QgsDataSourceUri
)


SHP_EXTENSIONS = ['.shp', '.shx', '.dbf', '.sbx', '.sbn', '.shp.xml']


def is_shapefile_layer(layer):
    source = layer.source()
    for ext in SHP_EXTENSIONS:
        if source.endswith(ext): #.shp.xml is not handled correctly as an extension by
        # os.path.splitext
            return True
    return False


def change_layer_data_source(layer, new_data_source):
    # read layer DOM definition
    XMLDocument = QDomDocument("style")
    XMLMapLayers = QDomElement()
    XMLMapLayers = XMLDocument.createElement("maplayers")
    XMLMapLayer = QDomElement()
    XMLMapLayer = XMLDocument.createElement("maplayer")
    layer.writeLayerXml(XMLMapLayer, XMLDocument)

    # modify DOM element with new layer reference
    XMLMapLayer.firstChildElement("datasource").firstChild().setNodeValue(new_data_source)
    #XMLMapLayer.firstChildElement("provider").firstChild().setNodeValue(newDatasourceProvider)
    XMLMapLayers.appendChild(XMLMapLayer)
    XMLDocument.appendChild(XMLMapLayers)

    # reload layer definition
    layer.readLayerXml(XMLMapLayer)
    layer.reload()


def project_get_raster_layers():
    return project_filter_layers(lambda layer: isinstance(layer, QgsRasterLayer))


def project_get_shp_layers():
    return project_filter_layers(is_shapefile_layer)


def project_get_layers_of_given_types(types):
    # can see all types via
    # QgsProviderRegistry.instance().providerList()
    map_layers = QgsMapLayerRegistry.instance().mapLayers()
    return [layer for name, layer in map_layers.items() if
            hasattr(layer, 'providerType')
            and layer.providerType() in types
            and not isinstance(layer, QgsRasterLayer)]


def layer_is_jpeg2000(layer):
    # those have providerType() gdal, so we can't detect them by looking at the providerType
    return layer.source().endswith(('jp2', 'jpx'))


def layer_is_ecw_raster(layer):
    return layer.source().endswith('ecw')


def project_get_qfield_unsupported_layers():
    return project_filter_layers(layer_is_jpeg2000) + project_filter_layers(layer_is_ecw_raster)


def project_get_remote_layers():
    """ Remote layers are layers that can either be converted to offline or kept in a realtime or hybrid mode"""
    return project_get_layers_of_given_types(types=["postgres"])


def project_get_always_offline_layers():
    """ Layers that are file based and hence can always be handled by the offline plugin"""
    types = ['delimitedtext', u'gdal', u'gpx', u'memory', u'ogr', u'spatialite']
    return project_get_layers_of_given_types(types=types)


def project_filter_layers(filter_func):
    map_layers = QgsMapLayerRegistry.instance().mapLayers()
    return [layer for name, layer in map_layers.items() if filter_func(layer)]

def file_path_for_layer(layer, new_folder):
    """
    Checks if the layer is file based and returns the original file path as well
    as an updated data source string for the new location.
    """
    file_path = layer.source()
    # Shapefiles have a simple path in the source
    if os.path.isfile(file_path):
        _, file_name = os.path.split(file_path)
        return (file_path, os.path.join(new_folder, file_name))
    # Spatialite files have a uri
    else:
        uri = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
        file_path = uri.database()
        if os.path.isfile(file_path):
            _, file_name = os.path.split(file_path)
            uri.setDatabase(os.path.join(new_folder, file_name))
            return (file_path, uri.uri())
        # It's a non-file-based format (WMS...)
        else:
            return (None, None)
