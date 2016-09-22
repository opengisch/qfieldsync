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


def warn_project_is_dirty(text=None):
    if (QgsProject.instance().isDirty()):
        title = tr('Continue?')
        default_text = tr('The currently open project is not saved. '
                         '\nQFieldSync will overwrite it. \nContinue?')
        if text is None:
            text = default_text
        answer = QMessageBox.question(None, title, text,
                                      QMessageBox.Yes,
                                      QMessageBox.No,
                                      QMessageBox.Save)
        if answer == QMessageBox.No:
            return False
        if answer == QMessageBox.Save:
            QgsProject.instance().write()
    return True
