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
