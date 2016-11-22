import os
import platform
import subprocess

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
    if platform.system() == "Windows":
        subprocess.Popen(r'explorer /select,"{}"'.format(path))
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", '-R', path])
    else:
        subprocess.Popen(["xdg-open", path])