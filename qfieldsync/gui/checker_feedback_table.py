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

from libqfieldsync.project_checker import (
    Feedback,
    FeedbackTypeId,
    ProjectCheckerFeedback,
)
from qgis.core import QgsApplication, QgsProject
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from qfieldsync.utils.qt_utils import make_icon


class CheckerFeedbackTable(QTableWidget):
    feedback_fixed = pyqtSignal()

    def __init__(self, checker_feedback: ProjectCheckerFeedback, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # dictionary mapping FeedbackTypeId to fix action callbacks
        self._fix_handlers = {
            FeedbackTypeId.PROJECT_IS_DIRTY: self._fix_project_is_dirty,
        }

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["", self.tr("Message")])
        self.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.setRowCount(0)
        self.setMinimumHeight(100)
        self.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )

        self.verticalHeader().hide()
        self.horizontalHeader().sectionResized.connect(self.resizeRowsToContents)
        self.setWordWrap(True)

        self.set_feedback(checker_feedback)

    def set_feedback(self, checker_feedback: ProjectCheckerFeedback) -> None:
        self.setRowCount(0)

        for layer_id in checker_feedback.feedbacks:
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
                cell_widget = QWidget()
                cell_layout = QHBoxLayout(cell_widget)
                cell_layout.setContentsMargins(0, 0, 8, 0)

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
                cell_layout.addWidget(label, stretch=1)

                fix_action = self._fix_handlers.get(feedback.type_id)
                if fix_action:
                    fix_button = QPushButton(self.tr("Fix!"))

                    def on_fix_clicked(
                        _checked: bool,
                        action=fix_action,
                        target_feedback=feedback,
                    ) -> None:
                        action(target_feedback)

                        self.feedback_fixed.emit()

                    fix_button.clicked.connect(on_fix_clicked)
                    cell_layout.addWidget(
                        fix_button,
                        alignment=Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter,
                    )

                self.setCellWidget(row, 1, cell_widget)

        self.resizeRowsToContents()

    def _fix_project_is_dirty(self, _feedbackfeedback: Feedback) -> None:
        QgsProject.instance().write()
