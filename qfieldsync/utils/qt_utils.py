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
import os
from functools import partial

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QIcon, QPainter, QPainterPath, QPixmap


def selectFolder(line_edit_widget):
    line_edit_widget.setText(
        QtWidgets.QFileDialog.getExistingDirectory(directory=line_edit_widget.text())
    )


def make_folder_selector(widget):
    return partial(selectFolder, line_edit_widget=widget)


def make_icon(icon_name):
    return QIcon(os.path.join(os.path.dirname(__file__), "..", "resources", icon_name))


def make_pixmap(icon_name):
    return QPixmap(
        os.path.join(os.path.dirname(__file__), "..", "resources", icon_name)
    )


def rounded_pixmap(img_path: str, diameter: int) -> QPixmap:
    width, height = diameter, diameter
    size = QSize(height, width)

    pixmap = QPixmap()
    if img_path.endswith(".svg"):
        pixmap = QIcon(img_path).pixmap(size)
    else:
        pixmap = QPixmap(img_path)

    pixmap = pixmap.scaled(
        width,
        height,
        Qt.KeepAspectRatioByExpanding,
        Qt.SmoothTransformation,
    )

    target_pixmap = QPixmap(size)
    target_pixmap.fill(Qt.transparent)

    painter = QPainter(target_pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    path = QPainterPath()
    path.addRoundedRect(
        0,
        0,
        width,
        height,
        width / 2,
        height / 2,
    )

    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)

    return target_pixmap
