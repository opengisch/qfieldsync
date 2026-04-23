import os

from libqfieldsync.project import ProjectProperties
from qgis.gui import QgsPanelWidget
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.uic import loadUiType

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/navigation_configuration_widget.ui")
)


class NavigationConfigurationWidget(WidgetUi, QgsPanelWidget):
    """Configuration widget for location arrow and coordinate cursor customization."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self.setPanelTitle(self.tr("Map Overlay Elements"))

        size_options = [
            (self.tr("Tiny"), ProjectProperties.QFieldItemSize.TINY),
            (self.tr("Normal"), ProjectProperties.QFieldItemSize.NORMAL),
            (self.tr("Big"), ProjectProperties.QFieldItemSize.BIG),
            (self.tr("Biggest"), ProjectProperties.QFieldItemSize.BIGGEST),
        ]

        for label, value in size_options:
            self.locationArrowSizeComboBox.addItem(label, value)
            self.coordinateCursorSizeComboBox.addItem(label, value)

        self.locationArrowFillColorButton.setAllowOpacity(True)
        self.locationArrowFillColorButton.setShowNull(True)
        self.locationArrowFillColorButton.setColorDialogTitle(
            self.tr("Location Arrow Fill Color")
        )

        self.locationArrowOutlineColorButton.setAllowOpacity(True)
        self.locationArrowOutlineColorButton.setShowNull(True)
        self.locationArrowOutlineColorButton.setColorDialogTitle(
            self.tr("Location Arrow Outline Color")
        )

        self.coordinateCursorFillColorButton.setAllowOpacity(True)
        self.coordinateCursorFillColorButton.setShowNull(True)
        self.coordinateCursorFillColorButton.setColorDialogTitle(
            self.tr("Coordinate Cursor Fill Color")
        )

        self.coordinateCursorOutlineColorButton.setAllowOpacity(True)
        self.coordinateCursorOutlineColorButton.setShowNull(True)
        self.coordinateCursorOutlineColorButton.setColorDialogTitle(
            self.tr("Coordinate Cursor Outline Color")
        )

    def location_arrow_fill_color(self):
        if self.locationArrowFillColorButton.isNull():
            return ""
        return self.locationArrowFillColorButton.color().name(QColor.NameFormat.HexArgb)

    def set_location_arrow_fill_color(self, color_str):
        if color_str:
            self.locationArrowFillColorButton.setColor(QColor(color_str))
        else:
            self.locationArrowFillColorButton.setToNull()

    def location_arrow_outline_color(self):
        if self.locationArrowOutlineColorButton.isNull():
            return ""
        return self.locationArrowOutlineColorButton.color().name(
            QColor.NameFormat.HexArgb
        )

    def set_location_arrow_outline_color(self, color_str):
        if color_str:
            self.locationArrowOutlineColorButton.setColor(QColor(color_str))
        else:
            self.locationArrowOutlineColorButton.setToNull()

    def location_arrow_size(self):
        return self.locationArrowSizeComboBox.currentData()

    def set_location_arrow_size(self, size):
        index = self.locationArrowSizeComboBox.findData(size)
        if index == -1:
            index = self.locationArrowSizeComboBox.findData(
                ProjectProperties.QFieldItemSize.NORMAL
            )
        self.locationArrowSizeComboBox.setCurrentIndex(index)

    def coordinate_cursor_fill_color(self):
        if self.coordinateCursorFillColorButton.isNull():
            return ""
        return self.coordinateCursorFillColorButton.color().name(
            QColor.NameFormat.HexArgb
        )

    def set_coordinate_cursor_fill_color(self, color_str):
        if color_str:
            self.coordinateCursorFillColorButton.setColor(QColor(color_str))
        else:
            self.coordinateCursorFillColorButton.setToNull()

    def coordinate_cursor_outline_color(self):
        if self.coordinateCursorOutlineColorButton.isNull():
            return ""
        return self.coordinateCursorOutlineColorButton.color().name(
            QColor.NameFormat.HexArgb
        )

    def set_coordinate_cursor_outline_color(self, color_str):
        if color_str:
            self.coordinateCursorOutlineColorButton.setColor(QColor(color_str))
        else:
            self.coordinateCursorOutlineColorButton.setToNull()

    def coordinate_cursor_size(self):
        return self.coordinateCursorSizeComboBox.currentData()

    def set_coordinate_cursor_size(self, size):
        index = self.coordinateCursorSizeComboBox.findData(size)
        if index == -1:
            index = self.coordinateCursorSizeComboBox.findData(
                ProjectProperties.QFieldItemSize.NORMAL
            )
        self.coordinateCursorSizeComboBox.setCurrentIndex(index)
