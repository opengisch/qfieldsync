from PyQt4 import QtGui
from functools import partial


def selectFolder(lineEditWidget):
    lineEditWidget.setText(QtGui.QFileDialog.getExistingDirectory(directory=lineEditWidget.text()))


def make_folder_selector(widget):
    return partial(selectFolder, lineEditWidget=widget)
