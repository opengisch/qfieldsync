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

from typing import List

from libqfieldsync.project import ProjectConfiguration
from libqfieldsync.utils.file_utils import get_project_in_folder
from libqfieldsync.utils.qgis import open_project
from qgis.core import QgsProject


def import_checksums_of_project(dirname: str) -> List[str]:
    project = QgsProject.instance()
    qgs_file = get_project_in_folder(dirname)
    open_project(qgs_file)
    original_project_path = ProjectConfiguration(project).original_project_path
    open_project(original_project_path)
    return ProjectConfiguration(project).imported_files_checksums
