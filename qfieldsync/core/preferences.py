import os
from qfieldsync.setting_manager import SettingManager, Scope, String

pluginName = "QFieldSync"


class Preferences(SettingManager):
    def __init__(self):
        SettingManager.__init__(self, pluginName, False)
        self.add_setting(String('exportDirectory', Scope.Global, os.path.expanduser("~/QField/export")))
        self.add_setting(String('exportDirectoryProject', Scope.Project, None))
        self.add_setting(String('importDirectory', Scope.Global, os.path.expanduser("~/QField/import")))
        self.add_setting(String('importDirectoryProject', Scope.Project, None))
        self.add_setting(String('qfieldcloud_username', Scope.Global, None))
        self.add_setting(String('qfieldcloud_password', Scope.Global, None))
        self.add_setting(String('qfieldcloud_base_url', Scope.Global, "https://dev.qfield.cloud"))
