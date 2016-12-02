# -*- coding: utf-8 -*-

"""
/***************************************************************************
 QFieldSync
                              -------------------
        begin                : 2016
        copyright            : (C) 2016 by OPENGIS.ch
        email                : info@opengis.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import inspect
from qgis.PyQt import QtWidgets
from functools import partial
import importlib
from qgis.PyQt.QtCore import qVersion


def selectFolder(line_edit_widget):
    line_edit_widget.setText(QtWidgets.QFileDialog.getExistingDirectory(directory=line_edit_widget.text()))


def make_folder_selector(widget):
    return partial(selectFolder, line_edit_widget=widget)


def get_ui_class(ui_file):
    """Get UI Python class from .ui file.
       Can be filename.ui or subdirectory/filename.ui
    :param ui_file: The file of the ui in safe.gui.ui
    :type ui_file: str
    """
    if qVersion()[0] == '4':
        m = importlib.import_module("qfieldsync.ui." + ui_file + '_ui4')
    else:
        m = importlib.import_module("qfieldsync.ui." + ui_file + '_ui5')
    return [obj for _, obj in inspect.getmembers(m) if inspect.isclass(obj) and obj.__name__[:3] == 'Ui_'][0]
