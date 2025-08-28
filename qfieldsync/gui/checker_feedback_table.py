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

from libqfieldsync.project_checker import Feedback, ProjectCheckerFeedback
from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QLabel, QSizePolicy, QTableWidget, QTableWidgetItem

from ..utils.qt_utils import make_icon


class CheckerFeedbackTable(QTableWidget):
    def __init__(self, checker_feedback: ProjectCheckerFeedback, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["", self.tr("Message")])
        self.horizontalHeader().setStretchLastSection(True)
        self.setRowCount(0)
        self.setMinimumHeight(100)
        self.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        for layer_id in checker_feedback.feedbacks.keys():
            for feedback in checker_feedback.feedbacks[layer_id]:
                row = self.rowCount()

                self.insertRow(row)

                # first column
                if feedback.level == Feedback.Level.WARNING:
                    level_icon = make_icon("idea.svg")
                    level_text = self.tr("Warning")
                else:
                    level_icon = QgsApplication.getThemeIcon("/mIconWarning.svg")
                    level_text = self.tr("Error")

                item = QTableWidgetItem(level_icon, "")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(level_text)
                self.setItem(row, 0, item)

                # second column
                if feedback.layer_id:
                    source = self.tr('Layer "{}"').format(feedback.layer_name)
                else:
                    source = self.tr("Project")

                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(level_text)
                self.setItem(row, 1, item)

                # we do not escape the values on purpose to support Markdown/HTML
                label = QLabel("**{}**\n\n{}".format(source, feedback.message))
                label.setWordWrap(True)
                label.setMargin(5)
                label.setTextFormat(Qt.TextFormat.MarkdownText)
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                    | Qt.TextInteractionFlag.TextSelectableByKeyboard
                    | Qt.TextInteractionFlag.LinksAccessibleByMouse
                    | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
                )
                label.setOpenExternalLinks(True)
                self.setCellWidget(row, 1, label)

        self.verticalHeader().hide()
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.horizontalHeader().sectionResized.connect(self.resizeRowsToContents)
        self.setWordWrap(True)
