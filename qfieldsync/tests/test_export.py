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

import shutil
import tempfile
from pathlib import Path
from typing import List

from qgis.core import Qgis, QgsOfflineEditing, QgsProject
from qgis.testing import start_app, unittest
from qgis.testing.mocked import get_iface

from qfieldsync.libqfieldsync.offline_converter import ExportType, OfflineConverter

start_app()


class OfflineConverterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iface = get_iface()

    def setUp(self):
        QgsProject.instance().clear()
        self.source_dir = Path(tempfile.mkdtemp())
        self.target_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.source_dir)
        shutil.rmtree(self.target_dir)

    def _path_contents(self, dir_path: Path) -> List[str]:
        return list(map(lambda p: str(p.relative_to(dir_path)), dir_path.iterdir()))

    @property
    def data_dir(self) -> Path:
        return Path(__file__).parent.joinpath("data")

    def load_project(self, path):
        project = QgsProject.instance()
        self.assertTrue(project.read(str(path)))
        return project

    def test_copy(self):
        shutil.copytree(
            self.data_dir.joinpath("simple_project"),
            self.source_dir.joinpath("simple_project"),
        )

        project = self.load_project(
            self.source_dir.joinpath("simple_project", "project.qgs")
        )
        offline_editing = QgsOfflineEditing()
        offline_converter = OfflineConverter(
            project,
            str(self.target_dir),
            "POLYGON((1 1, 5 0, 5 5, 0 5, 1 1))",
            QgsProject.instance().crs().authid(),
            ["DCIM"],
            offline_editing,
            ExportType.Cable,
        )
        offline_converter.convert()

        files = self._path_contents(self.target_dir)

        self.assertIn("project_qfield.qgs", files)
        self.assertIn("france_parts_shape.shp", files)
        self.assertIn("france_parts_shape.dbf", files)
        self.assertIn("curved_polys.gpkg", files)
        self.assertIn("spatialite.db", files)

        dcim_files = self._path_contents(self.target_dir.joinpath("DCIM"))
        self.assertIn("qfield-photo_1.jpg", dcim_files)
        self.assertIn("qfield-photo_2.jpg", dcim_files)
        self.assertIn("qfield-photo_3.jpg", dcim_files)
        dcim_subfiles = self._path_contents(
            self.target_dir.joinpath("DCIM", "subfolder")
        )
        self.assertIn("qfield-photo_sub_1.jpg", dcim_subfiles)
        self.assertIn("qfield-photo_sub_2.jpg", dcim_subfiles)
        self.assertIn("qfield-photo_sub_3.jpg", dcim_subfiles)

    def test_primary_keys_custom_property(self):
        shutil.copytree(
            self.data_dir.joinpath("simple_project"),
            self.source_dir.joinpath("simple_project"),
        )

        project = self.load_project(
            self.source_dir.joinpath("simple_project", "project.qgs")
        )
        offline_editing = QgsOfflineEditing()
        offline_converter = OfflineConverter(
            project,
            str(self.target_dir),
            "POLYGON((1 1, 5 0, 5 5, 0 5, 1 1))",
            QgsProject.instance().crs().authid(),
            ["DCIM"],
            offline_editing,
            ExportType.Cable,
        )
        offline_converter.convert()

        exported_project = self.load_project(
            self.target_dir.joinpath("project_qfield.qgs")
        )
        if Qgis.QGIS_VERSION_INT < 31601:
            layer = exported_project.mapLayersByName("somedata (offline)")[0]
        else:
            layer = exported_project.mapLayersByName("somedata")[0]
        self.assertEqual(layer.customProperty("QFieldSync/sourceDataPrimaryKeys"), "pk")
