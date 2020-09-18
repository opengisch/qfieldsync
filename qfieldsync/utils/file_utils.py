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
import shutil

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
    if not os.path.isdir(parent):
        raise QFieldSyncError(
            "The directory {} could not be found".format(parent))

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
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', slug).strip('-')
    slug = re.sub(r'[-]+', '-', slug)
    slug = slug.lower()
    return slug


def copy_images(source_folder, destination_folder):
    if os.path.isdir(source_folder):
        if not os.path.isdir(destination_folder):
            os.mkdir(destination_folder)
    for root, dirs, files in os.walk(source_folder):
        for name in dirs:
            dir_path = os.path.join(root, name)
            destination_dir_path = os.path.join(destination_folder, os.path.relpath(dir_path, source_folder))
            # create the folder if it does not exists
            if not os.path.isdir(destination_dir_path):
                os.mkdir(destination_dir_path)
        for name in files:
            file_path = os.path.join(root, name)
            destination_file_path = os.path.join(destination_folder, os.path.relpath(file_path, source_folder))
            # copy the file no matter if it exists or not
            shutil.copyfile(os.path.join(root, name), destination_file_path)

