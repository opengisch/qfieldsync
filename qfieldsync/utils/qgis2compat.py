import qgis.core
import qgis.utils

# Dealing with a QGIS 2 version, monkey patch some things
if hasattr(qgis.utils, 'QGis'):
    def QgsVectorLayer_writeLayerXML(self, XMLMapLayer, XMLDocument):
        self.writeLayerXML(XMLMapLayer, XMLDocument)

    qgis.core.QgsVectorLayer.writeLayerXml = QgsVectorLayer_writeLayerXML

    def QgsVectorLayer_readLayerXML(self, XMLMapLayer):
        self.readLayerXML(XMLMapLayer)

    qgis.core.QgsVectorLayer.readLayerXml = QgsVectorLayer_readLayerXML
