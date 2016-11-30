import os

from qfieldsync.core import Preferences
from qfieldsync.dialogs.preferences_dialog import PreferencesDialog
from qgis.testing import start_app, unittest
from qgis.testing.mocked import get_iface

start_app()

class PreferencesDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.iface = get_iface()

    def test_open_dialog(self):
        preferences = Preferences()

        dlg = PreferencesDialog(preferences)
        dlg.show()
