# -*- coding: utf-8 -*-

"""
/***************************************************************************
 QFieldSync processing provider
                              -------------------
        begin                : 2016-10-05
        copyright            : (C) 2016 by OPENGIS.ch
        email                : matthias@opengis.ch
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

from builtins import str
from builtins import range
from builtins import object
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterExtent, ParameterString, ParameterNumber, ParameterRaster
from processing.core.outputs import OutputRaster
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException

from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtCore import QSize
from qgis.core import (
    QgsMapSettings,
    QgsMapRendererCustomPainterJob,
    QgsRectangle,
    QgsProject
)

import qgis
import osgeo.gdal
import os
import tempfile
import math

__author__ = 'Matthias Kuhn'
__date__ = '2016-10-05'
__copyright__ = '(C) 2016 by OPENGIS.ch'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


class BasemapAlgorithm(GeoAlgorithm):
    """
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    OUTPUT_LAYER = 'OUTPUT_LAYER'
    MAP_THEME = 'MAP_THEME'
    LAYER = 'LAYER'
    EXTENT = 'EXTENT'
    TILE_SIZE = 'TILE_SIZE'
    MAP_UNITS_PER_PIXEL = 'MAP_UNITS_PER_PIXEL'

    def defineCharacteristics(self):
        """Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # The name that the user will see in the toolbox
        self.name = 'basemap'

        # The branch of the toolbox under which the algorithm will appear
        self.group = 'raster'

        # The parameters
        self.addParameter(
            ParameterString(self.MAP_THEME, description=self.tr('Map theme to render.'), default=None, optional=True))
        self.addParameter(ParameterRaster(self.LAYER, description=self.tr(
            'Layer to render. Will only be used if the map theme is not set. If both, map theme and layer are not '
            'set, the current map content will be rendered.'),
            optional=True))
        self.addParameter(ParameterExtent(self.EXTENT, description=self.tr(
            'The minimum extent to render. Will internally be extended to be a multiple of the tile sizes.')))
        self.addParameter(ParameterNumber(self.TILE_SIZE, self.tr('Tile size'), default=1024))
        self.addParameter(ParameterNumber(self.MAP_UNITS_PER_PIXEL, self.tr('Map units per pixel'), default=100))

        # We add a raster layer as output
        self.addOutput(OutputRaster(self.OUTPUT_LAYER, self.tr('Output layer')))

    def processAlgorithm(self, progress):
        """Here is where the processing itself takes place."""

        # The first thing to do is retrieve the values of the parameters
        # entered by the user
        map_theme = self.getParameterValue(self.MAP_THEME)
        layer = self.getParameterValue(self.LAYER)
        raw_extent = self.getParameterValue(self.EXTENT)
        split_extent = [float(c) for c in raw_extent.split(',')]
        extent = QgsRectangle(split_extent[0], split_extent[2], split_extent[1], split_extent[3])
        tile_size = self.getParameterValue(self.TILE_SIZE)
        mupp = self.getParameterValue(self.MAP_UNITS_PER_PIXEL)

        output = self.getOutputValue(self.OUTPUT_LAYER)

        # This probably affects the whole system but it's a lot nicer
        osgeo.gdal.UseExceptions()

        tile_set = TileSet(map_theme, layer, extent, tile_size, mupp, output,
                           qgis.utils.iface.mapCanvas().mapSettings())
        tile_set.render(progress)


class TileSet(object):
    """
    A set of tiles
    """

    def __init__(self, map_theme, layer, extent, tile_size, mupp, output, map_settings):
        """

        :param map_theme:
        :param extent:
        :param layer:
        :param tile_size:
        :param mupp:
        :param output:
        :param map_settings: Map canvas map settings used for some fallback values and CRS
        """

        self.extent = extent
        self.mupp = mupp
        self.tile_size = tile_size

        # TODO: Check if file exists and update instead?
        driver = self.getDriverForFile(output)

        if not driver:
            raise GeoAlgorithmExecutionException(u'Could not load GDAL driver for file {}'.format(output))

        crs = map_settings.destinationCrs()

        self.x_tile_count = math.ceil(extent.width() / mupp / tile_size)
        self.y_tile_count = math.ceil(extent.height() / mupp / tile_size)

        xsize = self.x_tile_count * tile_size
        ysize = self.y_tile_count * tile_size

        self.dataset = driver.Create(output, xsize, ysize, 3)  # 3 bands
        self.dataset.SetProjection(str(crs.toWkt()))
        self.dataset.SetGeoTransform([extent.xMinimum(), mupp, 0, extent.yMaximum(), 0, -mupp])

        self.image = QImage(QSize(tile_size, tile_size), QImage.Format_RGB32)

        self.settings = QgsMapSettings()
        self.settings.setCrsTransformEnabled(True)
        self.settings.setOutputDpi(self.image.logicalDpiX())
        self.settings.setOutputImageFormat(QImage.Format_RGB32)
        self.settings.setDestinationCrs(crs)
        self.settings.setOutputSize(self.image.size())
        self.settings.setMapUnits(crs.mapUnits())
        self.settings.setFlag(QgsMapSettings.Antialiasing, True)
        self.settings.setFlag(QgsMapSettings.RenderMapTile, True)

        if QgsProject.instance().mapThemeCollection().hasMapTheme(map_theme):
            self.settings.setLayers(QgsProject.instance().mapThemeCollection().mapThemeVisibleLayers(map_theme))
            self.settings.setLayerStyleOverrides(
                QgsProject.instance().mapThemeCollection().mapThemeStyleOverrides(map_theme))
        elif layer:
            self.settings.setLayers([layer])
        else:
            self.settings.setLayers(map_settings.layers())

    def render(self, progress):
        for x in range(self.x_tile_count):
            for y in range(self.y_tile_count):
                cur_tile = x * self.y_tile_count + y
                num_tiles = self.x_tile_count * self.y_tile_count
                progress.setPercentage(cur_tile * 100 / num_tiles)
                self.renderTile(x, y)

    def renderTile(self, x, y):
        """
        Render one tile

        :param x: The x index of the current tile
        :param y: The y index of the current tile
        """
        painter = QPainter(self.image)

        self.settings.setExtent(QgsRectangle(self.extent.xMinimum() + x * self.mupp * self.tile_size,
                                             self.extent.yMaximum() - (y + 1) * self.mupp * self.tile_size,
                                             self.extent.xMinimum() + (x + 1) * self.mupp * self.tile_size,
                                             self.extent.yMaximum() - y * self.mupp * self.tile_size))

        job = QgsMapRendererCustomPainterJob(self.settings, painter)
        job.renderSynchronously()
        painter.end()

        # Needs not to be deleted or Windows will kill it too early...
        tmpfile = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        try:
            self.image.save(tmpfile.name)

            src_ds = osgeo.gdal.Open(tmpfile.name)

            self.dataset.WriteRaster(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size,
                                     src_ds.ReadRaster(0, 0, self.tile_size, self.tile_size))
        finally:
            del src_ds
            tmpfile.close()
            os.unlink(tmpfile.name)

    def getDriverForFile(self, filename):
        """
        Get the GDAL driver for a filename, based on its extension. (.gpkg, .mbtiles...)
        """
        _, extension = os.path.splitext(filename)

        for i in range(osgeo.gdal.GetDriverCount()):
            driver = osgeo.gdal.GetDriver(i)
            if driver.GetMetadataItem('DMD_EXTENSION') == extension[1:]:
                return driver
