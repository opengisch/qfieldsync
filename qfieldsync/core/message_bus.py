# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
                             -------------------
        begin                : 2022-08-09
        git sha              : $Format:%H$
        copyright            : (C) 2022 by OPENGIS.ch
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


from qgis.PyQt.QtCore import QObject, pyqtSignal


class MessageBus(QObject):
    """Super minimal implementation of a message bus.

    Allows communication between unrelated parts of the plugin.
    """

    """The signal that passes the message."""
    messaged = pyqtSignal(str)


# Modules are evaluated only once, therefore it works as a poor man version of singleton.
message_bus = MessageBus()
