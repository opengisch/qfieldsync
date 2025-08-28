"""
/***************************************************************************
 QFieldCloud
                             -------------------
        begin                : 2020-07-13
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

import os
from pathlib import Path
from typing import List

from libqfieldsync.utils.qgis import get_qgis_files_within_dir
from qgis.core import (
    QgsDataCollectionItem,
    QgsDataItem,
    QgsDataItemProvider,
    QgsDataProvider,
    QgsErrorItem,
)
from qgis.gui import QgsDataItemGuiProvider
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface

from qfieldsync.core.cloud_api import CloudNetworkAccessManager
from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.gui.cloud_projects_dialog import CloudProjectsDialog
from qfieldsync.gui.cloud_transfer_dialog import CloudTransferDialog


class QFieldCloudItemProvider(QgsDataItemProvider):
    def __init__(self, network_manager: CloudNetworkAccessManager):
        QgsDataItemProvider.__init__(self)
        self.network_manager = network_manager

    def name(self):
        return "QFieldCloudItemProvider"

    def capabilities(self):
        return QgsDataProvider.Net

    def createDataItem(self, _path, parentItem):  # noqa: N802
        if not parentItem:
            root_item = QFieldCloudRootItem(self.network_manager)
            return root_item
        else:
            return None


class QFieldCloudRootItem(QgsDataCollectionItem):
    """QFieldCloud root"""

    def __init__(self, network_manager: CloudNetworkAccessManager):
        QgsDataCollectionItem.__init__(
            self, None, "QFieldCloud", "/QFieldCloud", "QFieldCloudProvider"
        )
        self.setIcon(
            QIcon(os.path.join(os.path.dirname(__file__), "../resources/cloud_off.svg"))
        )
        self.network_manager = network_manager
        self.error = None

        self.network_manager.login_finished.connect(self._on_login_finished)
        self.network_manager.token_changed.connect(self._on_token_changed)
        self.network_manager.projects_cache.projects_updated.connect(
            self._on_projects_updated
        )

    def capabilities2(self):
        return QgsDataItem.Fast

    def createChildren(self):  # noqa: N802
        items = []

        if not self.network_manager.has_token():
            CloudLoginDialog.show_auth_dialog(self.network_manager)
            self.setState(QgsDataItem.Populating)
            return []

        self.setState(QgsDataItem.Populated)

        if self.error:
            error_item = QgsErrorItem(self, self.error, "/QFieldCloud/error")
            error_item.setIcon(
                QIcon(os.path.join(os.path.dirname(__file__), "../resources/cloud.svg"))
            )
            return [error_item]

        my_projects = QFieldCloudGroupItem(
            self, "My projects", "private", "../resources/cloud.svg", 1
        )
        items.append(my_projects)

        # TODO @suricactus: uncomment when public projects API is ready
        # public_projects = QFieldCloudGroupItem(
        #     self, "Community", "public", "../resources/cloud.svg", 2
        # )
        # items.append(public_projects)

        return items

    def refreshing_cloud_projects(self):
        self.depopulate()
        self.refresh()

    def update_icon(self):
        if self.network_manager.has_token():
            self.setIcon(
                QIcon(os.path.join(os.path.dirname(__file__), "../resources/cloud.svg"))
            )
        else:
            self.setIcon(
                QIcon(
                    os.path.join(
                        os.path.dirname(__file__), "../resources/cloud_off.svg"
                    )
                )
            )

    def _on_login_finished(self) -> None:
        """Handle login finished signal"""
        self.update_icon()

    def _on_token_changed(self) -> None:
        """Handle token changed signal"""
        self.update_icon()

    def _on_projects_updated(self) -> None:
        """Handle projects updated signal"""
        self.refreshing_cloud_projects()


class QFieldCloudGroupItem(QgsDataCollectionItem):
    """QFieldCloud group data item."""

    def __init__(self, parent, name, project_type, icon, order):  # noqa: PLR0913
        super().__init__(parent, name, "/QFieldCloud/" + name)

        self.network_manager = parent.network_manager
        self.project_type = project_type
        self.setIcon(QIcon(os.path.join(os.path.dirname(__file__), icon)))
        self.setSortKey(order)

    def createChildren(self):  # noqa: N802
        items = []

        projects: List[CloudProject] = self.network_manager.projects_cache.projects

        if projects is None:
            try:
                # TODO @suricactus: I do not recall why this was required to be not-async, but otherwise it failed. Revisit why.
                self.network_manager.projects_cache.refresh_not_async()
            except Exception:
                return []

            projects = self.network_manager.projects_cache.projects

        for project in self.network_manager.projects_cache.projects:
            if (self.project_type == "public" and not project.is_private) or (
                self.project_type == "private" and project.is_private
            ):
                item = QFieldCloudProjectItem(self, project)
                item.setState(QgsDataItem.Populated)
                items.append(item)

        return items


class QFieldCloudProjectItem(QgsDataItem):
    """QFieldCloud project item."""

    def __init__(self, parent, project):
        super().__init__(
            QgsDataItem.Collection,
            parent,
            project.name,
            "/QFieldCloud/project/" + project.id,
        )
        self.project_id = project.id
        project = parent.network_manager.projects_cache.find_project(self.project_id)
        self.setIcon(
            QIcon(
                str(
                    Path(__file__).parent.joinpath(
                        "../resources/cloud_project.svg"
                        if project.local_dir
                        else "../resources/cloud_project_remote.svg"
                    )
                )
            )
        )


class QFieldCloudItemGuiProvider(QgsDataItemGuiProvider):
    def __init__(self, network_manager: CloudNetworkAccessManager):
        QgsDataItemGuiProvider.__init__(self)
        self.network_manager = network_manager

    def name(self):
        return "QFieldCloudItemGuiProvider"

    def populateContextMenu(self, item, menu, _selectedItems, _context):  # noqa: N802
        if type(item) is QFieldCloudProjectItem:
            project = self.network_manager.projects_cache.find_project(item.project_id)
            if project and project.local_dir:
                open_action = menu.addAction(QObject().tr("Open Project"))
                open_action.triggered.connect(self._on_open_project_action_triggered)

            sync_action = menu.addAction(
                QIcon(os.path.join(os.path.dirname(__file__), "../resources/sync.svg")),
                QObject().tr("Synchronize Project"),
            )
            sync_action.triggered.connect(self._on_synchronize_project_action_triggered)

            properties_action = menu.addAction(QObject().tr("Project Properties"))
            properties_action.triggered.connect(self._on_project_properties_action)

            # Store item reference for callbacks
            self._current_item = item

        elif type(item) is QFieldCloudGroupItem:
            create_action = menu.addAction(
                QIcon(os.path.join(os.path.dirname(__file__), "../resources/edit.svg")),
                QObject().tr("Create New Project"),
            )
            create_action.triggered.connect(self._on_create_project_action_triggered)

        elif type(item) is QFieldCloudRootItem:
            projects_overview_action = menu.addAction(
                QIcon(
                    os.path.join(os.path.dirname(__file__), "../resources/cloud.svg")
                ),
                QObject().tr("Projects Overview"),
            )
            projects_overview_action.triggered.connect(
                self._on_projects_overview_action_triggered
            )

            refresh_action = menu.addAction(
                QIcon(
                    os.path.join(os.path.dirname(__file__), "../resources/refresh.png")
                ),
                QObject().tr("Refresh Projects"),
            )
            refresh_action.triggered.connect(self._on_refresh_projects_action_triggered)

    def handleDoubleClick(self, item, context):  # noqa: ARG002, N802
        if type(item) is QFieldCloudProjectItem:
            if not self.open_project(item):
                self.show_cloud_synchronize_dialog(item)
            return True
        return False

    def _create_projects_dialog(self, item) -> CloudProjectsDialog:
        # it is important to get the project like this, because if the project list is refreshed, here we will store an old reference
        project = self.network_manager.projects_cache.find_project(item.project_id)
        return CloudProjectsDialog(
            self.network_manager, iface.mainWindow(), project=project
        )

    def show_cloud_synchronize_dialog(self, item):
        project = self.network_manager.projects_cache.find_project(item.project_id)
        CloudTransferDialog.show_transfer_dialog(
            self.network_manager, project, None, None, iface.mainWindow()
        )

    def open_project(self, item) -> bool:
        project = self.network_manager.projects_cache.find_project(item.project_id)
        if project and project.local_dir:
            project_file_name = get_qgis_files_within_dir(Path(project.local_dir))
            if project_file_name:
                iface.addProject(os.path.join(project.local_dir, project_file_name[0]))
                return True

        return False

    def refresh_cloud_projects(self):
        if not self.network_manager.has_token():
            CloudLoginDialog.show_auth_dialog(
                self.network_manager, self._on_refresh_after_login
            )
            return

        if self.network_manager.is_login_active:
            return

        self.network_manager.projects_cache.refresh()

    def _on_open_project_action_triggered(self):
        """Handle open project action"""
        self.open_project(self._current_item)

    def _on_synchronize_project_action_triggered(self):
        """Handle synchronize project action"""
        self.show_cloud_synchronize_dialog(self._current_item)

    def _on_project_properties_action(self):
        """Handle project properties action"""
        self._create_projects_dialog(self._current_item).show_project_form()

    def _on_create_project_action_triggered(self):
        """Handle create project action"""
        CloudProjectsDialog(
            self.network_manager, iface.mainWindow()
        ).show_create_project()

    def _on_projects_overview_action_triggered(self):
        """Handle projects overview action"""
        CloudProjectsDialog(self.network_manager, iface.mainWindow()).show()

    def _on_refresh_projects_action_triggered(self):
        """Handle refresh projects action"""
        self.refresh_cloud_projects()

    def _on_refresh_after_login(self):
        """Handle refresh after login callback"""
        self.refresh_cloud_projects()
