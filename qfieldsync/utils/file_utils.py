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
