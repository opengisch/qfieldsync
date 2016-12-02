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

# import qgis libs so that ve set the correct sip api version
import pkgutil

import qgis  # pylint: disable=W0611  # NOQA
import qfieldsync

# On travis, the qgis2compat module is copied into the sourcetree, if it's present, just laod it
try:
    import qgis2compat.apicompat  # NOQA
except ImportError:
    pass

from qgis.core import QgsMessageLog


def debug_log_message(message, tag, level):
    print('{}({}): {}'.format(tag, level, message))


QgsMessageLog.instance().messageReceived.connect(debug_log_message)
