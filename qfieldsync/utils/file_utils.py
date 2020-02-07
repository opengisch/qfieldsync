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
import platform
import subprocess
import hashlib
import re
import unicodedata

from pathlib import Path

from qfieldsync.utils.exceptions import NoProjectFoundError, QFieldSyncError


def fileparts(fn, extension_dot=True):
    path = os.path.dirname(fn)
    basename = os.path.basename(fn)
    name, ext = os.path.splitext(basename)
    if extension_dot and not ext.startswith(".") and ext:
        ext = "." + ext
    elif not extension_dot and ext.startswith("."):
        ext = ext[1:]
    return (path, name, ext)


def get_children_with_extension(parent, specified_ext, count=1):
    res = []
    extension_dot = specified_ext.startswith(".")
    for fn in os.listdir(parent):
        _, _, ext = fileparts(fn, extension_dot=extension_dot)
        if ext == specified_ext:
            res.append(os.path.join(parent, fn))
    if len(res) != count:
        raise QFieldSyncError(
            "Expected {} children with extension {} under {}, got {}".format(
                count, specified_ext, parent, len(res)))

    return res


def get_full_parent_path(fn):
    return os.path.dirname(os.path.normpath(fn))


def get_project_in_folder(folder):
    try:
        return get_children_with_extension(folder, 'qgs', count=1)[0]
    except QFieldSyncError:
        message = 'No .qgs file found in folder {}'.format(folder)
        raise NoProjectFoundError(message)


def open_folder(path):
    """
    Opens the provided path in a file browser.
    On Windows and Mac, this will open the parent directory
    and pre-select the actual folder.
    """
    path = Path(path)
    if platform.system() == "Windows":
        subprocess.Popen(r'explorer /select,"{}"'.format(path))
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", '-R', path])
    else:
        subprocess.Popen(["xdg-open", path])


def import_file_checksum(folder):
    md5sum = None
    path = os.path.join(folder, "data.gpkg")
    if not os.path.exists(path):
        path = os.path.join(folder, "data.sqlite")
    if os.path.exists(path):
        with open(path, 'rb') as f:
            file_data = f.read()
            md5sum = hashlib.md5(file_data).hexdigest()

    return md5sum


def slugify(text: str) -> str:
    # https://stackoverflow.com/q/5574042/1548052
    slug = unicodedata.normalize('NFKD', text)
    print(slug)
    #slug = slug.encode('ascii', 'ignore').lower()
    print(slug)
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    print(slug)
    slug = re.sub(r'[-]+', '-', slug)
    print(slug)
    return slug
