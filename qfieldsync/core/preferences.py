# GUI messages options
import os

from qgis.PyQt.QtCore import QSettings

LOG_TAG = "QFieldSync"
MSG_DURATION_SECS = 10


class Preferences(object):
    __EXPORT_DIRECTORY_SETTING = "QFieldSync/exportDirectory"
    __IMPORT_DIRECTORY_SETTING = "QFieldSync/importDirectory"
    __TEMP_DIRECTORY_SETTING = "QFieldSync/tempDirectory"

    @property
    def export_directory(self):
        return QSettings().value(self.__EXPORT_DIRECTORY_SETTING, os.path.expanduser("~/QField/export"))

    @export_directory.setter
    def export_directory(self, value):
        QSettings().setValue(self.__EXPORT_DIRECTORY_SETTING, value)

    @property
    def import_directory(self):
        return QSettings().value(self.__IMPORT_DIRECTORY_SETTING, os.path.expanduser("~/QField/import"))

    @import_directory.setter
    def import_directory(self, value):
        QSettings().setValue(self.__IMPORT_DIRECTORY_SETTING, value)

    @property
    def temporary_files_directory(self):
        return QSettings().value(self.__TEMP_DIRECTORY_SETTING)

    @temporary_files_directory.setter
    def temporary_files_directory(self, value):
        if value:
            QSettings().setValue(self.__TEMP_DIRECTORY_SETTING, value)
        else:
            QSettings().setValue(self.__TEMP_DIRECTORY_SETTING, None)

