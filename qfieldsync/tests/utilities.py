import inspect
import os


def test_data_folder():
    this_filename = inspect.stack()[0][1]
    basepath,_ = os.path.split(this_filename)
    return os.path.join(basepath, 'data')
