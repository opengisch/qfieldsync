# -*- coding: utf-8 -*-
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

import os
import qgis.utils

qgis2compat_min_version = '0.4.2'


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load QFieldSync class from file QFieldSync.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    plugin_name = os.path.dirname(__file__).split(os.path.sep)[-1]
    plugin_name = qgis.utils.pluginMetadata(plugin_name, 'name')

    def qgis2compat_version_check():
        if not qgis.utils.pluginMetadata('qgis2compat', 'version') >= qgis2compat_min_version:
            raise RuntimeError('The plugin {plugin_name} requires at least version {qgis2compat_min_version} of the '
                               '`qgis2compat` plugin. Please update it with the plugin manager.'
                               .format(plugin_name=plugin_name, qgis2compat_min_version=qgis2compat_min_version))

    try:
        # qgis.PyQt is available in QGIS >=2.14
        from qgis.PyQt.QtCore import qVersion  # NOQA
        # qgis.utils.QGis is available in QGIS < 3
        if hasattr(qgis.utils, 'QGis'):
            import qgis2compat.apicompat
            qgis2compat_version_check()
            qgis2compat.log('apicompat used in {}'.format(plugin_name))
    except ImportError:
        try:
            # we are in QGIS < 2.14
            import qgis2compat.apicompat
            qgis2compat_version_check()
            qgis2compat.log('PyQt and apicompat used in {}'.format(plugin_name))
        except ImportError:
            import traceback
            traceback.print_exc()
            raise ImportError('The Plugin {} requires the `qgis2compat` plugin. Please install it with the plugin '
                              'manager. For more information visit http://opengis.ch/qgis2compat'.format(plugin_name))

    from qfieldsync.qfield_sync import QFieldSync
    return QFieldSync(iface)
