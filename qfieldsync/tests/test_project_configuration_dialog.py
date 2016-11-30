import os

from qfieldsync.core import Preferences
from qfieldsync.dialogs.project_configuration_dialog import ProjectConfigurationDialog
from qgis.testing import start_app, unittest
from qgis.testing.mocked import get_iface
from qgis.core import QgsOfflineEditing

start_app()

class ProjectConfigurationDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.iface = get_iface()

    def test_open_dialog(self):
        preferences = Preferences()
        offline_editing = QgsOfflineEditing()

        dlg = ProjectConfigurationDialog(self.iface)
        dlg.show()
