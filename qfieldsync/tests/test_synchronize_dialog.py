import os

from qfieldsync.core import Preferences
from qfieldsync.dialogs.synchronize_dialog import SynchronizeDialog
from qgis.testing import start_app, unittest
from qgis.testing.mocked import get_iface
from qgis.core import QgsOfflineEditing

start_app()

class SynchronizeDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.iface = get_iface()

    def test_open_dialog(self):
        preferences = Preferences()
        offline_editing = QgsOfflineEditing()

        dlg = SynchronizeDialog(self.iface, preferences, offline_editing)
        dlg.show()
