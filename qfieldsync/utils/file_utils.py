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
import stat
from enum import Enum
from pathlib import Path
from typing import List, TypedDict, Union

PathLike = Union[Path, str]


class DirectoryTreeType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


class DirectoryTreeDict(TypedDict):
    type: DirectoryTreeType
    path: Path
    content: List["DirectoryTreeDict"]


def path_to_dict(path: PathLike, dirs_only: bool = False) -> DirectoryTreeDict:
    path = Path(path)
    node: DirectoryTreeDict = {
        "path": path,
        "content": [],
    }

    if path.is_dir():
        node["type"] = DirectoryTreeType.DIRECTORY

        glob_pattern = "*/" if dirs_only else "*"
        for subpath in path.glob(glob_pattern):
            if dirs_only and not subpath.is_dir():
                continue

            if ".qfieldsync" in str(subpath):
                continue

            node["content"].append(path_to_dict(subpath, dirs_only=dirs_only))
    elif not dirs_only:
        node["type"] = DirectoryTreeType.FILE

    node["content"].sort(key=lambda node: node["path"].name)

    return node


def mkdir(
    path: Union[str, Path],
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
) -> None:
    """
    Create a directory at a given path and explicitly assign write permissions to make Windows happy.

    This function mimics the API of `Path.mkdir`.

    Apparently the passed `mode` value on `os.mkdir` and `Path.mkdir` is not respected by Windows prior to 3.13.
    What is more, in 3.13 Windows will handle only 0o700, the rest of the values will be ignored.

    See: https://docs.python.org/3/library/os.html#os.mkdir

    Args:
        path: the path to be created
        mode: The mode to be applied on the directory at the time of creation. Defaults to 0o777.
        parents: Whether to create directories recursively if missing. Defaults to False.
        exist_ok: Whether to not throw if the directory already exists. Defaults to False.
    """
    path = Path(path)
    # calling `mkdir` might trigger a `PermissionError` and other. The caller must handle the error.
    path.mkdir(mode)

    current_permission = stat.S_IMODE(path.stat().st_mode)
    WRITE = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    # calling `chmod` might trigger a `PermissionError`. The parent must handle the error.
    path.chmod(current_permission | WRITE)
