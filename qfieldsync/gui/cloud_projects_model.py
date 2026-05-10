"""
/***************************************************************************
 CloudProjectsModel
                                 A QGIS plugin
 Sync your projects to QField
                             -------------------
        begin                : 2026-05-10
        git sha              : $Format:%H$
        copyright            : (C) 2026 by OPENGIS.ch
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

from pathlib import Path
from typing import Optional

from qgis.PyQt.QtCore import (
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QBrush,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import QWidget

from qfieldsync.core.cloud_api import CloudNetworkAccessManager
from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.utils.cloud_utils import get_cloud_project_status_color


class CloudProjectsModel(QSortFilterProxyModel):
    refreshed = pyqtSignal()

    def __init__(
        self,
        network_manager: CloudNetworkAccessManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent=parent)

        self.source_model = CloudProjectsModelBase(network_manager, self)
        self.source_model.refreshed.connect(lambda: self.refreshed.emit())
        self.setSourceModel(self.source_model)

        self.include_public = False
        self.filter_string = ""

        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_include_public(self, include_public: bool) -> None:
        if self.include_public == include_public:
            return

        self.include_public = include_public
        self.invalidateFilter()

    def set_filter_string(self, filter_string: str) -> None:
        if self.filter_string == filter_string:
            return

        self.filter_string = filter_string
        self.invalidateFilter()

    def filterAcceptsRow(  # dead: disable # noqa: N802
        self,
        source_row: int,
        source_parent: QModelIndex,
    ) -> bool:
        cloud_project = self.source_model.data(
            self.source_model.index(source_row, 0, source_parent),
            Qt.ItemDataRole.UserRole,
        )
        if not self.include_public and cloud_project.user_role_origin == "public":
            return False

        if self.filter_string:
            if (
                self.filter_string not in cloud_project.name.lower()
                and self.filter_string not in cloud_project.owner.lower()
            ):
                return False

        return True


class CloudProjectsModelBase(QStandardItemModel):
    refreshed = pyqtSignal()

    def __init__(
        self,
        network_manager: CloudNetworkAccessManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent=parent)

        self.network_manager = network_manager
        self.network_manager.projects_cache.projects_updated.connect(
            lambda: self._refresh()
        )
        self.network_manager.logout_success.connect(lambda: self._refresh())

    def _get_name_item(self, cloud_project: CloudProject) -> QStandardItem:
        item = QStandardItem()
        item.setData(cloud_project, Qt.ItemDataRole.UserRole)
        item.setData(cloud_project.name, Qt.ItemDataRole.EditRole)
        item.setData(
            self._get_name_item_pixmap(cloud_project), Qt.ItemDataRole.DecorationRole
        )
        item.setToolTip(self._get_name_item_tooltip(cloud_project))
        return item

    def _get_name_item_tooltip(self, cloud_project: CloudProject) -> str:
        tooltip = self.tr("Cloud status: {}. \nLocal status: ").format(
            cloud_project.status
        )

        if bool(cloud_project.local_dir):
            tooltip += self.tr('Project stored at "{}".').format(
                str(cloud_project.local_dir)
            )
        else:
            tooltip += self.tr("No local dir configured.")

        return tooltip

    def _get_name_item_pixmap(self, cloud_project: CloudProject) -> QPixmap:
        color = get_cloud_project_status_color(cloud_project)

        decoration = QPixmap(40, 20)
        decoration.fill(Qt.GlobalColor.transparent)
        painter = QPainter(decoration)
        painter.setPen(QPen(color, 8, Qt.PenStyle.SolidLine))
        painter.setBrush(QBrush(color, Qt.BrushStyle.SolidPattern))
        painter.drawEllipse(30, 10, 5, 5)
        if cloud_project.local_dir:
            project_icon = "../resources/cloud_project.svg"
        else:
            project_icon = "../resources/cloud_project_remote.svg"

        icon = QIcon(str(Path(__file__).parent.joinpath(project_icon)))
        painter.drawPixmap(0, 0, icon.pixmap(decoration.size()))
        del painter

        return decoration

    def _refresh(self) -> None:
        self.clear()

        if (
            self.network_manager.is_authenticated()
            and self.network_manager.projects_cache.projects
        ):
            for cloud_project in self.network_manager.projects_cache.projects:
                self.appendRow(
                    [
                        self._get_name_item(cloud_project),
                        QStandardItem(cloud_project.owner),
                    ]
                )

        self.setHorizontalHeaderLabels(["Name", "Owner"])
        self.refreshed.emit()
