# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
                             -------------------
        begin                : 2020-07-13
        git sha              : $Format:%H$
        copyright            : (C) 2020 by OPENGIS.ch
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


import re
from enum import Enum
from pathlib import Path
from typing import Tuple

from libqfieldsync.utils.qgis import get_qgis_files_within_dir
from qgis.PyQt.QtCore import QObject


class LocalDirFeedback(Enum):
    Error = "error"
    Warning = "warning"
    Success = "success"


def to_cloud_title(title):
    return re.sub("[^A-Za-z0-9-_]", "_", title)


def closure(cb):
    def wrapper(*closure_args, **closure_kwargs):
        def call(*args, **kwargs):
            return cb(*closure_args, *args, **closure_kwargs, **kwargs)

        return call

    return wrapper


def local_dir_feedback(
    local_dir: str,
    no_path_status: LocalDirFeedback = LocalDirFeedback.Error,
    not_dir_status: LocalDirFeedback = LocalDirFeedback.Error,
    not_existing_status: LocalDirFeedback = LocalDirFeedback.Warning,
    no_project_status: LocalDirFeedback = LocalDirFeedback.Success,
    single_project_status: LocalDirFeedback = LocalDirFeedback.Success,
    multiple_projects_status: LocalDirFeedback = LocalDirFeedback.Error,
    relative_status: LocalDirFeedback = LocalDirFeedback.Error,
) -> Tuple[LocalDirFeedback, str]:
    dummy = QObject()
    if not local_dir:
        return no_path_status, dummy.tr(
            "Please select local directory where the project to be stored."
        )
    elif not Path(local_dir).is_absolute():
        return relative_status, dummy.tr(
            "The entered path is a relative path. Please enter an absolute directory path."
        )
    elif Path(local_dir).exists() and not Path(local_dir).is_dir():
        return not_dir_status, dummy.tr(
            "The entered path is not an directory. Please enter a valid directory path."
        )
    elif not Path(local_dir).exists():
        return not_existing_status, dummy.tr(
            "The entered path is not an existing directory. It will be created after you submit this form."
        )
    elif len(get_qgis_files_within_dir(Path(local_dir))) == 0:
        message = dummy.tr("The entered path does not contain a QGIS project file yet.")
        status = no_project_status

        if single_project_status == LocalDirFeedback.Success:
            message += " "
            message += dummy.tr("You can always add one later.")

        return status, message
    elif len(get_qgis_files_within_dir(Path(local_dir))) == 1:
        message = dummy.tr("The entered path contains one QGIS project file.")
        status = single_project_status

        if single_project_status == LocalDirFeedback.Success:
            message += " "
            message += dummy.tr("Exactly as it should be.")

        return status, message
    else:
        return multiple_projects_status, dummy.tr(
            "Multiple project files have been found in the directory. Please leave exactly one QGIS project in the root directory."
        )
