# -*- coding: utf-8 -*-
"""
/***************************************************************************
                             -------------------
        begin                : 2025-06-28
        git sha              : $Format:%H$
        copyright            : (C) 2024 by OPENGIS.ch
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

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QTableWidgetItem,
    QWidget,
)
from qgis.PyQt.uic import loadUiType

WidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/directories_configuration_widget.ui")
)


class DirectoriesConfigurationWidget(WidgetUi, QWidget):
    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.setupUi(self)

        self.setMinimumHeight(120)
        self.directoriesTable.setColumnCount(2)
        self.directoriesTable.setHorizontalHeaderLabels(
            [self.tr("Name"), self.tr("Type")]
        )
        self.directoriesTable.setColumnWidth(1, 160)
        self.directoriesTable.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.directoriesTable.verticalHeader().setVisible(False)
        self.directoriesTable.setAlternatingRowColors(True)
        self.directoriesTable.setSortingEnabled(False)
        self.directoriesTable.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.directoriesTable.itemSelectionChanged.connect(
            lambda: self.removeButton.setEnabled(
                len(self.directoriesTable.selectedItems()) > 0
            )
        )

        self.addButton.setIcon(QgsApplication.getThemeIcon("/symbologyAdd.svg"))
        self.addButton.clicked.connect(self.addDirectory)

        self.removeButton.setIcon(QgsApplication.getThemeIcon("/symbologyRemove.svg"))
        self.removeButton.setEnabled(False)
        self.removeButton.clicked.connect(self.removeDirectory)

    def reload(self, configuration):
        """
        Load directories into table.
        """

        self.directoriesTable.setRowCount(0)
        if "attachment_dirs" in configuration:
            for attachment_dir in configuration["attachment_dirs"]:
                self.addDirectoryRow(attachment_dir, 0)
        if "data_dirs" in configuration:
            for data_dir in configuration["data_dirs"]:
                self.addDirectoryRow(data_dir, 1)

    def createConfiguration(self):
        configuration = {"attachment_dirs": [], "data_dirs": []}

        for i in range(self.directoriesTable.rowCount()):
            item = self.directoriesTable.item(i, 0)
            cmb = self.directoriesTable.cellWidget(i, 1)
            if item.data(Qt.ItemDataRole.EditRole) != "":
                if cmb.currentIndex() == 0:
                    configuration["attachment_dirs"].append(item.data(Qt.ItemDataRole.EditRole))
                elif cmb.currentIndex() == 1:
                    configuration["data_dirs"].append(item.data(Qt.ItemDataRole.EditRole))

        return configuration

    def addDirectoryRow(self, name="", typeIndex=0, editRow=False):
        count = self.directoriesTable.rowCount()
        self.directoriesTable.insertRow(count)

        item = QTableWidgetItem(name)
        item.setData(Qt.ItemDataRole.EditRole, name)
        self.directoriesTable.setItem(count, 0, item)

        cmb = QComboBox()
        cmb.addItem(self.tr("Attachments"))
        cmb.addItem(self.tr("Data"))
        cmb.setCurrentIndex(typeIndex)
        self.directoriesTable.setCellWidget(count, 1, cmb)
        if editRow:
            self.directoriesTable.editItem(item)

    def addDirectory(self):
        self.directoriesTable.setFocus()
        self.addDirectoryRow("", 0, True)

    def removeDirectory(self):
        if self.directoriesTable.selectedItems():
            self.directoriesTable.removeRow(
                self.directoriesTable.selectedItems()[0].row()
            )
