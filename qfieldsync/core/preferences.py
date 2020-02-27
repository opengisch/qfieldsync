import os

from qgis.PyQt.QtCore import QSettings

LOG_TAG = "QFieldSync"
MSG_DURATION_SECS = 10


class Preferences(object):
    __EXPORT_DIRECTORY_SETTING = "QFieldSync/exportDirectory"
    __IMPORT_DIRECTORY_SETTING = "QFieldSync/importDirectory"
    __QFIELDCLOUD_USERNAME_SETTING = "QFieldSync/qfieldCloudUsername"
    __QFIELDCLOUD_PASSWORD_SETTING = "QFieldSync/qfieldCloudPassword"
    __QFIELDCLOUD_BASE_URL_SETTING = "QFieldSync/qfieldCloudBaseUrl"

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
        print('setting new directory import')
        QSettings().setValue(self.__IMPORT_DIRECTORY_SETTING, value)

    @property
    def qfieldcloud_username(self):
        return QSettings().value(self.__QFIELDCLOUD_USERNAME_SETTING)

    @qfieldcloud_username.setter
    def qfieldcloud_username(self, value):
        QSettings().setValue(self.__QFIELDCLOUD_USERNAME_SETTING, value)

    @property
    def qfieldcloud_password(self):
        return QSettings().value(self.__QFIELDCLOUD_PASSWORD_SETTING)

    @qfieldcloud_password.setter
    def qfieldcloud_password(self, value):
        QSettings().setValue(self.__QFIELDCLOUD_PASSWORD_SETTING, value)

    @property
    def qfieldcloud_base_url(self):
        return QSettings().value(
            self.__QFIELDCLOUD_BASE_URL_SETTING, 'https://dev.qfield.cloud')

    @qfieldcloud_base_url.setter
    def qfieldcloud_base_url(self, value):
        QSettings().setValue(self.__QFIELDCLOUD_BASE_URL_SETTING, value)
