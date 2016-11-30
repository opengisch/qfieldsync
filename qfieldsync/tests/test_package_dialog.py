import os

from qfieldsync.core import Preferences
from qfieldsync.dialogs.package_dialog import PackageDialog
from qgis.testing import start_app, unittest
from qgis.testing.mocked import get_iface
from qgis.core import QgsOfflineEditing, QgsProject

start_app()

class PackageDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.iface = get_iface()

    def test_open_dialog(self):
        preferences = Preferences()
        offline_editing = QgsOfflineEditing()

        dlg = PackageDialog(self.iface, preferences, QgsProject.instance(), offline_editing)
        dlg.show()
