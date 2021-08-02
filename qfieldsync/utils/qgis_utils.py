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

import os
import tempfile
from pathlib import Path

from qgis.core import QgsProject

from qfieldsync.libqfieldsync import ProjectConfiguration
from qfieldsync.libqfieldsync.utils.file_utils import get_project_in_folder


def get_project_title(project: QgsProject) -> str:
    """ Gets project title, or if non available, the basename of the filename"""
    if project.title():
        return project.title()
    else:
        return Path(project.fileName()).stem


def open_project(filename: str, filename_to_read: str = None) -> bool:
    project = QgsProject.instance()
    project.clear()

    is_success = project.read(filename_to_read or filename)
    project.setFileName(filename)

    return is_success


def make_temp_qgis_file(project: QgsProject) -> str:
    project_backup_folder = tempfile.mkdtemp()
    original_filename = project.fileName()
    backup_project_path = os.path.join(
        project_backup_folder, project.baseName() + ".qgs"
    )
    project.write(backup_project_path)
    project.setFileName(original_filename)

    return backup_project_path


def import_checksums_of_project(folder):
    project = QgsProject.instance()
    qgs_file = get_project_in_folder(folder)
    open_project(qgs_file)
    original_project_path = ProjectConfiguration(project).original_project_path
    open_project(original_project_path)
    return ProjectConfiguration(project).imported_files_checksums
