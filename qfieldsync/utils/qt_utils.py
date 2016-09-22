import os
from qgis.PyQt import QtGui, uic
from functools import partial


def selectFolder(lineEditWidget):
    lineEditWidget.setText(QtGui.QFileDialog.getExistingDirectory(directory=lineEditWidget.text()))


def make_folder_selector(widget):
    return partial(selectFolder, lineEditWidget=widget)


def get_ui_class(ui_file):
    """Get UI Python class from .ui file.
       Can be filename.ui or subdirectory/filename.ui
    :param ui_file: The file of the ui in safe.gui.ui
    :type ui_file: str
    """
    os.path.sep.join(ui_file.split('/'))
    ui_file_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            'ui',
            ui_file
        )
    )
    return uic.loadUiType(ui_file_path)[0]
