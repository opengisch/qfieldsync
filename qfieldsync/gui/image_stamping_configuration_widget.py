# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              -------------------
        begin                : 21.11.2016
        git sha              : :%H$
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

from qgis.core import (
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsGeometry,
    QgsPoint,
    QgsProject,
    QgsReadWriteContext,
    QgsTextFormat,
)
from qgis.gui import QgsExpressionBuilderDialog, QgsPanelWidget
from qgis.PyQt.QtCore import QDateTime
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.uic import loadUiType

WidgetUi, _ = loadUiType(
    os.path.join(
        os.path.dirname(__file__), "../ui/image_stamping_configuration_widget.ui"
    )
)


class ImageStampingConfigurationWidget(WidgetUi, QgsPanelWidget):
    """
    Configuration widget for QFieldSync on a particular project.
    """

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self.setPanelTitle(self.tr("Image Stamping"))

        self.customFontStyleButton.setShowNullFormat(True)
        self.customFontStyleButton.setShowNullFormat(True)
        self.customFontStyleButton.setNoFormatString(self.tr("Default font style"))

        self.customAlignmentComboBox.addItem(self.tr("Left"))
        self.customAlignmentComboBox.addItem(self.tr("Center"))
        self.customAlignmentComboBox.addItem(self.tr("Right"))

        self.expression_context = QgsExpressionContext()
        self.expression_context.appendScopes(
            QgsExpressionContextUtils.globalProjectLayerScopes(None)
        )

        cloud_expression_context_scope = QgsExpressionContextScope(
            self.tr("Cloud User Info")
        )
        cloud_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "cloud_username", "nyuki", True, True
            )
        )
        cloud_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "cloud_useremail", "nyuki@qfield.cloud", True, True
            )
        )
        self.expression_context.appendScope(cloud_expression_context_scope)

        point = QgsGeometry(QgsPoint(0, 0, 0))
        position_expression_context_scope = QgsExpressionContextScope(
            self.tr("Position")
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_coordinate", point, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_timestamp", QDateTime.currentDateTime(), True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_direction", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_ground_speed", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_orientation", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_magnetic_variation", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_horizontal_accuracy", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_vertical_accuracy", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_3d_accuracy", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_vertical_speed", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_source_name", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_pdop", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_hdop", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_vdop", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_number_of_used_satellites", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_used_satellites", [], True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_quality_description", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_fix_status_description", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_fix_mode", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_averaged_count", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable(
                "gnss_imu_correction", 0, True, True
            )
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_imu_roll", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_imu_pitch", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_imu_heading", 0, True, True)
        )
        position_expression_context_scope.addVariable(
            QgsExpressionContextScope.StaticVariable("gnss_imu_steering", 0, True, True)
        )
        self.expression_context.appendScope(position_expression_context_scope)

        self.expression_context.setHighlightedVariables(
            position_expression_context_scope.variableNames()
            + cloud_expression_context_scope.variableNames()
        )

        self.expression_builder_dialog = QgsExpressionBuilderDialog(
            None, "", self, "generic", self.expression_context
        )
        self.insertExpressionButton.clicked.connect(self.show_builder)

        # self.customDetailsTextEdit.setWordWrapMode(QTextOption.WordWrap)
        # self.customDetailsTextEdit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.customDetailsTextEdit.textChanged.connect(self.update_preview)

        self.update_preview()

    def show_builder(self):
        if self.customDetailsTextEdit.textCursor().selectedText():
            self.expression_builder_dialog.setExpressionText(
                self.customDetailsTextEdit.textCursor().selectedText()
            )
        else:
            self.expression_builder_dialog.setExpressionText("")

        if self.expression_builder_dialog.exec():
            if self.expression_builder_dialog.expressionText():
                self.customDetailsTextEdit.textCursor().removeSelectedText()
                self.customDetailsTextEdit.insertPlainText(
                    f"[% {self.expression_builder_dialog.expressionText()} %]"
                )
            self.update_preview()

    def update_preview(self):
        if self.customDetailsTextEdit.toPlainText():
            preview_text = QgsExpression.replaceExpressionText(
                self.customDetailsTextEdit.toPlainText(), self.expression_context
            )
        else:
            preview_text = QgsExpression.replaceExpressionText(
                "[% format_date(now(), 'yyyy-MM-dd @ HH:mm') || if(@gnss_coordinate is not null, format('\n"
                + self.tr("Latitude")
                + " %1 | "
                + self.tr("Longitude")
                + " %2 | "
                + self.tr("Altitude")
                + " %3\n"
                + self.tr("Speed")
                + " %4 | "
                + self.tr("Orientation")
                + " %5', coalesce(format_number(y(@gnss_coordinate), 7), 'N/A'), coalesce(format_number(x(@gnss_coordinate), 7), 'N/A'), coalesce(format_number(z(@gnss_coordinate), 3) || ' m', 'N/A'), if(@gnss_ground_speed != 'nan', format_number(@gnss_ground_speed, 3) || ' m/s', 'N/A'), if(@gnss_orientation != 'nan', format_number(@gnss_orientation, 1) || ' °', 'N/A')), '') %]",
                self.expression_context,
            )

        self.previewLabel.setText(preview_text)

    def font_style(self):
        text_format = self.customFontStyleButton.textFormat()
        if text_format.isValid():
            rw_context = QgsReadWriteContext()
            document = QDomDocument()
            element = text_format.writeXml(document, rw_context)
            document.appendChild(element)
            return document.toString()

        return ""

    def set_font_style(self, xml_string):
        text_format = QgsTextFormat()
        if xml_string:
            rw_context = QgsReadWriteContext()
            rw_context.setPathResolver(QgsProject.instance().pathResolver())
            document = QDomDocument()
            document.setContent(xml_string)
            text_format.readXml(document.documentElement(), rw_context)

        self.customFontStyleButton.setTextFormat(text_format)

    def horizontal_alignment(self):
        return self.customAlignmentComboBox.currentIndex()

    def set_horizontal_alignment(self, horizontal_alignment):
        self.customAlignmentComboBox.setCurrentIndex(horizontal_alignment)

    def image_decoration(self):
        return self.customImageDecorationFile.filePath()

    def set_image_decoration(self, file_path):
        self.customImageDecorationFile.setFilePath(file_path)

    def details_expression(self):
        return self.customDetailsTextEdit.toPlainText()

    def set_details_expression(self, details_expression):
        self.customDetailsTextEdit.setPlainText(details_expression)

    def force_stamping(self):
        return self.forceStampingCheckBox.isChecked()

    def set_force_stamping(self, force_stamping):
        self.forceStampingCheckBox.setChecked(force_stamping)
