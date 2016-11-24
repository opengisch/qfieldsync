from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsProject

from qfieldsync.utils.file_utils import fileparts


def tr(message):
    return QCoreApplication.translate('QFieldSync', message)


def get_project_title(proj):
    """ Gets project title, or if non available, the basename of the filename"""
    title = proj.title()
    if not title: # if title is empty, get basename
        fn = proj.fileName()
        _, title, _ = fileparts(fn)
    return title


def open_project(fn):
    QgsProject.instance().clear()
    QgsProject.instance().setFileName(fn)
    QgsProject.instance().read()
