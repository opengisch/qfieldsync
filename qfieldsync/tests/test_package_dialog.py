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


from qgis.testing import start_app, unittest
from qgis.testing.mocked import get_iface
from qgis.core import QgsOfflineEditing, QgsProject
from qfieldsync.gui.package_dialog import PackageDialog

start_app()

class PackageDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.iface = get_iface()

    def test_open_dialog(self):
        offline_editing = QgsOfflineEditing()

        dlg = PackageDialog(self.iface, QgsProject.instance(), offline_editing)
        dlg.show()
