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

import unittest

from qgis.core import QgsOfflineEditing
from qgis.testing import start_app
from qgis.testing.mocked import get_iface

from qfieldsync.gui.project_configuration_dialog import ProjectConfigurationDialog

start_app()


class ProjectConfigurationDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iface = get_iface()

    def test_open_dialog(self):
        QgsOfflineEditing()

        dlg = ProjectConfigurationDialog()
        dlg.show()
