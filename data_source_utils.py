from PyQt4.QtXml import *


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
