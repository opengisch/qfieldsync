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
from enum import Enum
from pathlib import Path
from typing import List, TypedDict, Union
import re

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


def is_valid_filename(filename: str) -> bool:
    """
    Check if the filename is valid.
    """
    pattern = re.compile(
        r'^(?!.*[<>:"/\\|?*])'
        r"(?!(?:COM[0-9]|CON|LPT[0-9]|NUL|PRN|AUX|com[0-9]|con|lpt[0-9]|nul|prn|aux)$)"
        r'[^\\\/:*"?<>|]{1,254}'
        r"(?<![\s\.])$"
    )
    return bool(pattern.match(filename))


def is_valid_filepath(path: str) -> bool:
    """
    Check if the entire path is valid.
    """
    try:
        path_obj = Path(path)
        for part in path_obj.parts:
            if not is_valid_filename(part):
                return False
        return True
    except Exception:
        return False
