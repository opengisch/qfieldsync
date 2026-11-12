# ruff: noqa: SIM103, PLR0911

from pathlib import PurePath
from typing import Optional

from qgis.PyQt.QtCore import QCoreApplication

from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.core.errors import CannotUploadFileError


def can_delete_project(project: CloudProject) -> bool:
    return project.user_role == "admin"


def can_update_project(project: CloudProject) -> bool:
    return project.user_role in {"admin", "manager"}


def is_qgis_project_file(filename: str) -> bool:
    """Whether the filename seems to be a QGIS project file by checking the file extension."""
    path = PurePath(filename)

    if path.suffix.lower() in (".qgs", ".qgz"):
        return True

    return False


def is_admin_restricted_file(
    filename: str, projectfile_filename: Optional[str]
) -> bool:
    """
    Whether the file has modifications restricted only to users with elevated permissions.

    Such files are the QGIS project file, QField extensions and QGIS sidecar filed (e.g. `_attachments.zip`).

    NOTE If no `projectfile_filename` is passed, then the function always returns `False`.

    NOTE Keep in sync with QFieldCloud (`QFieldCloud/docker-app/qfieldcloud/filestorage/utils.py`)

    Args:
        filename: the filename being checked
        projectfile_filename: the filename of the QGIS projectfile. If not provided, the function always returns `False`.

    Returns:
        whether the file is restricted file

    """
    if not projectfile_filename:
        return False

    path = PurePath(filename)
    projectfile_path = PurePath(projectfile_filename)

    # the qgis file itself
    if is_qgis_project_file(filename):
        if projectfile_path.stem == path.stem:
            return True
        else:
            return False

    # attachments
    if f"{projectfile_path.stem}_attachments.zip" == path.name:
        return True

    # label coordinates
    if f"{projectfile_path.stem}.qgd" == path.name:
        return True

    # QField plugins
    if f"{projectfile_path.stem}.qml" == path.name:
        return True

    return False


def check_can_upload_file(project: CloudProject, filename: PurePath) -> None:
    """
    Check whether the current user can upload the file to the project.

    Raises:
        CannotUploadFileError: if the upload is not allowed to upload files with its current role.

    """
    if project.user_role == "reader":
        raise CannotUploadFileError(
            QCoreApplication.translate(
                "QFieldSync", "Readers cannot upload files to this project."
            )
        )

    if not project.has_restricted_projectfiles or can_update_project(project):
        return

    # NOTE QFieldCloud rejects any `.qgs`/`.qgz` from non-managers, even when
    # `the_qgis_file_name` is not set and `is_admin_restricted_file` returns False
    name = str(filename)
    if is_qgis_project_file(name) or is_admin_restricted_file(
        name, project.the_qgis_file_name
    ):
        raise CannotUploadFileError(
            QCoreApplication.translate(
                "QFieldSync",
                "This project restricts modifications of the QGIS project files.",
            )
        )
