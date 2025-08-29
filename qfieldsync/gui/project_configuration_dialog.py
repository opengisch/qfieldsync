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

from qgis.gui import QgsGui
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from qfieldsync.gui.project_configuration_widget import ProjectConfigurationStackWidget


class ProjectConfigurationDialog(QDialog):
    """Configuration dialog for QFieldSync on a particular project."""

    def __init__(self, parent=None):
        """Constructor."""
        super().__init__(parent=parent)

        self.setMinimumWidth(500)
        QgsGui.instance().enableAutoGeometryRestore(self)

        self.setWindowTitle("QFieldSync Project Properties")

        self.projectConfigurationStackWidget = ProjectConfigurationStackWidget(self)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(lambda: self._on_accepted())
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.projectConfigurationStackWidget)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def _on_accepted(self):
        self.projectConfigurationWidget.apply()
        self.close()
