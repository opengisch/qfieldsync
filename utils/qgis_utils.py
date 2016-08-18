from QFieldSync.utils.file_utils import fileparts


def get_project_title(proj):
    """ Gets project title, or if non available, the basename of the filename"""
    title = proj.title()
    if not title: # if title is empty, get basename
        fn = proj.fileName()
        _, title, _ = fileparts(fn)
    return title
