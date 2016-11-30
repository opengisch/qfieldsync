# GUI messages options
import os

from qgis.PyQt.QtCore import QSettings

LOG_TAG = "QFieldSync"
MSG_DURATION_SECS = 10


class Preferences(object):
    __EXPORT_DIRECTORY_SETTING = "QFieldSync/exportDirectory"
    __IMPORT_DIRECTORY_SETTING = "QFieldSync/importDirectory"

    @property
    def export_directory(self):
        return QSettings().value(self.__EXPORT_DIRECTORY_SETTING, os.path.expanduser("~"))

    @export_directory.setter
    def export_directory(self, value):
        QSettings().setValue(self.__EXPORT_DIRECTORY_SETTING, value)

    @property
    def import_directory(self):
        return QSettings().value(self.__IMPORT_DIRECTORY_SETTING, os.path.expanduser("~"))

    @import_directory.setter
    def import_directory(self, value):
        QSettings().setValue(self.__IMPORT_DIRECTORY_SETTING, value)
