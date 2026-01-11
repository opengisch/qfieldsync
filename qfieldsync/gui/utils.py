"""
/***************************************************************************
 QFieldSyncDialog
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2020-06-15
        git sha              : $Format:%H$
        copyright            : (C) 2020 by OPENGIS.ch
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

from typing import Literal

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QPalette
from qgis.PyQt.QtWidgets import QWidget

MID_COLOR_SUM_THRESHOLD = 120


def set_available_actions(combobox, actions, default_action):
    """Sets available actions on a checkbox and selects the current one."""
    for action, description in actions:
        combobox.addItem(description)
        combobox.setItemData(combobox.count() - 1, action)

        if action == default_action:
            combobox.setCurrentIndex(combobox.count() - 1)


def extract_theme_from_qgis_settings() -> Literal["light", "dark"]:
    """
    Finds if the current QGIS theme should use "light" or "dark" theme.
    Return the most accurate possible "dark" or "light" key.
    Typically used for styling SSO logins buttons.

    Returns:
        "light" or "dark", based on user's current QGIS settings.
    """
    qgis_theme = QgsApplication.instance().themeName()

    if qgis_theme == "Night Mapping":
        return "dark"

    if qgis_theme == "Blend of Gray":
        return "light"

    color = QWidget().palette().color(QPalette.ColorRole.Window)

    if (color.red() + color.green() + color.blue()) / 3 < MID_COLOR_SUM_THRESHOLD:
        return "dark"

    return "light"
