from PyQt4.QtXml import *
from qgis.core import QgsMapLayerRegistry, QgsProject, QgsOfflineEditing, QgsRasterLayer


SHP_EXTENSIONS = ['.shp','.shx','.dbf','.sbx','.sbn', '.shp.xml']

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
    layer.writeLayerXML(XMLMapLayer,XMLDocument)

    # modify DOM element with new layer reference
    XMLMapLayer.firstChildElement("datasource").firstChild().setNodeValue(new_data_source)
    #XMLMapLayer.firstChildElement("provider").firstChild().setNodeValue(newDatasourceProvider)
    XMLMapLayers.appendChild(XMLMapLayer)
    XMLDocument.appendChild(XMLMapLayers)

    # reload layer definition
    layer.readLayerXML(XMLMapLayer)
    layer.reload()



def project_get_raster_layers():
    return project_filter_layers(lambda layer: isinstance(layer, QgsRasterLayer))


def project_get_shp_layers():
    return project_filter_layers(is_shapefile_layer)


def project_get_layers_of_given_types(types):
    # can see all types via
    # QgsProviderRegistry.instance().providerList()
    map_layers = QgsMapLayerRegistry.instance().mapLayers()
    return [layer for name, layer in map_layers.items() if layer.providerType() in \
                types and not isinstance(layer, QgsRasterLayer)]


def project_get_always_online_layers():
    """ Layers that can't be made offline by the offline plugin """
    online_types = ["WFS", "wcs", "wms", "mssql", "ows"]
    return project_get_layers_of_given_types(online_types)


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