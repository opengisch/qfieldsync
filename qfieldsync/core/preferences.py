from pathlib import Path

from qfieldsync.setting_manager import (
    Bool,
    Dictionary,
    Scope,
    SettingManager,
    String,
    Stringlist,
)

pluginName = "QFieldSync"


class Preferences(SettingManager):
    def __init__(self):
        SettingManager.__init__(self, pluginName, False)
        home = Path.home()
        self.add_setting(
            String("exportDirectory", Scope.Global, str(home.joinpath("QField/export")))
        )
        self.add_setting(String("exportDirectoryProject", Scope.Project, None))
        self.add_setting(
            String("importDirectory", Scope.Global, str(home.joinpath("QField/import")))
        )
        self.add_setting(Bool("showPackagingActions", Scope.Global, True))
        self.add_setting(String("importDirectoryProject", Scope.Project, None))
        self.add_setting(Dictionary("dirsToCopy", Scope.Project, {}))
        self.add_setting(Stringlist("attachmentDirs", Scope.Project, ["DCIM"]))
        self.add_setting(Dictionary("qfieldCloudProjectLocalDirs", Scope.Global, {}))
        self.add_setting(Dictionary("qfieldCloudLastProjectFiles", Scope.Global, {}))
        self.add_setting(String("qfieldCloudServerUrl", Scope.Global, ""))
        self.add_setting(String("qfieldCloudAuthcfg", Scope.Global, ""))
        self.add_setting(Bool("qfieldCloudRememberMe", Scope.Global, True))
        self.add_setting(
            String("cloudDirectory", Scope.Global, str(home.joinpath("QField/cloud")))
        )
        self.add_setting(Bool("firstRun", Scope.Global, True))
