import os

def fileparts(fn, extension_dot = True):
    path = os.path.dirname(fn)
    basename = os.path.basename(fn)
    name,ext = os.path.splitext(basename)
    if extension_dot and not ext.startswith(".") and ext:
        ext = "." + ext
    elif not extension_dot and ext.startswith("."):
        ext = ext[1:]
    return (path,name,ext)

