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

from qgis.core import QgsProject

from qfieldsync.libqfieldsync.utils.file_utils import fileparts, get_project_in_folder
from qfieldsync.libqfieldsync import ProjectConfiguration


def get_project_title(proj):
    """ Gets project title, or if non available, the basename of the filename"""
    title = proj.title()
    if not title:  # if title is empty, get basename
        fn = proj.fileName()
        _, title, _ = fileparts(fn)
    return title


def open_project(fn):
    QgsProject.instance().clear()
    QgsProject.instance().setFileName(fn)
    return QgsProject.instance().read()


def import_checksums_of_project(folder):
    qgs_file = get_project_in_folder(folder)
    open_project(qgs_file)
    original_project_path = ProjectConfiguration(QgsProject.instance()).original_project_path
    open_project(original_project_path)
    return ProjectConfiguration(QgsProject.instance()).imported_files_checksums
