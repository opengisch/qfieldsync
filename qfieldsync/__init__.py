"""
/***************************************************************************
 QFieldSync
                                 A QGIS plugin
 Sync your projects to QField on android
                             -------------------
        begin                : 2015-05-20
        copyright            : (C) 2015 by OPENGIS.ch
        email                : info@opengis.ch
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

from __future__ import absolute_import

import importlib
import pathlib
import re
import sys

src_dir = pathlib.Path(__file__).parent.resolve()

# remove previously loaded `libqfieldsync.whl` from the python import path
for python_path in sys.path:
    if re.search(r"libqfieldsync.*\.whl$", python_path):
        sys.path.remove(python_path)

# add the new `libqfieldsync.whl` file to the python import path
for libqfieldsync_whl in src_dir.glob("libqfieldsync*.whl"):
    sys.path.append(str(libqfieldsync_whl))

# force reload all the `libqfieldsync` modules from the new path
module_names = list(sys.modules.keys())
for module_name in module_names:
    if module_name.startswith("libqfieldsync"):
        importlib.reload(sys.modules[module_name])


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """
    Load QFieldSync class from file QFieldSync.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from qfieldsync.qfield_sync import QFieldSync

    return QFieldSync(iface)
