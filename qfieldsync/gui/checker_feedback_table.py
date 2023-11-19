# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2023-04-11
        git sha              : $Format:%H$
        copyright            : (C) 2015 by OPENGIS.ch
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

from libqfieldsync.project_checker import ProjectCheckerFeedback
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel, QTableWidget, QTableWidgetItem


class CheckerFeedbackTable(QTableWidget):
    def __init__(self, checker_feedback: ProjectCheckerFeedback, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(
            [self.tr("Level"), self.tr("Source"), self.tr("Message")]
        )
        self.horizontalHeader().setStretchLastSection(True)
        self.setRowCount(0)
        self.setMinimumHeight(100)

        for layer_id in checker_feedback.feedbacks.keys():
            for feedback in checker_feedback.feedbacks[layer_id]:
                row = self.rowCount()

                self.insertRow(row)

                # first column
                item = QTableWidgetItem(str(feedback.level.name))
                item.setFlags(Qt.ItemIsEnabled)
                self.setItem(row, 0, item)

                # second column
                if feedback.layer_id:
                    source = self.tr('Layer "{}"').format(feedback.layer_name)
                else:
                    source = self.tr("Project")

                item = QTableWidgetItem(source)
                item.setFlags(Qt.ItemIsEnabled)
                self.setItem(row, 1, item)

                # third column
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsEnabled)
                self.setItem(row, 2, item)

                label = QLabel(feedback.message)
                label.setWordWrap(True)
                label.setMargin(5)
                label.setTextFormat(Qt.MarkdownText)
                label.setTextInteractionFlags(
                    Qt.TextSelectableByMouse
                    | Qt.TextSelectableByKeyboard
                    | Qt.LinksAccessibleByMouse
                    | Qt.LinksAccessibleByKeyboard
                )
                label.setOpenExternalLinks(True)
                # label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                self.setCellWidget(row, 2, label)

        self.verticalHeader().hide()
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.horizontalHeader().sectionResized.connect(self.resizeRowsToContents)
        self.setWordWrap(True)
