# -*- coding: utf-8 -*-
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

import glob
import os
from typing import List

from qgis.core import (
    QgsDataCollectionItem,
    QgsDataItem,
    QgsDataItemProvider,
    QgsDataProvider,
    QgsErrorItem,
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.utils import iface

from qfieldsync.core.cloud_api import CloudNetworkAccessManager
from qfieldsync.core.cloud_project import CloudProject
from qfieldsync.gui.cloud_login_dialog import CloudLoginDialog
from qfieldsync.gui.cloud_projects_dialog import CloudProjectsDialog
from qfieldsync.gui.cloud_transfer_dialog import CloudTransferDialog


class DataItemProvider(QgsDataItemProvider):
    def __init__(self, network_manager: CloudNetworkAccessManager):
        QgsDataItemProvider.__init__(self)
        self.network_manager = network_manager

    def name(self):
        return "QFieldCloudProvider"

    def capabilities(self):
        return QgsDataProvider.Net

    def createDataItem(self, path, parentItem):
        if not parentItem:
            root_item = QFieldCloudRootItem(self.network_manager)
            return root_item
        else:
            return


class QFieldCloudRootItem(QgsDataCollectionItem):
    """ QFieldCloud root """

    def __init__(self, network_manager: CloudNetworkAccessManager):
        QgsDataCollectionItem.__init__(
            self, None, "QFieldCloud", "/QFieldCloud", "QFieldCloudProvider"
        )
        self.setIcon(
            QIcon(os.path.join(os.path.dirname(__file__), "../resources/cloud_off.svg"))
        )
        self.network_manager = network_manager
        self.error = None

        self.network_manager.login_success.connect(lambda: self.refresh_icon())
        self.network_manager.token_changed.connect(lambda: self.refresh_icon())
        self.network_manager.projects_cache.projects_updated.connect(
            lambda: self.refreshing_projects()
        )

    def capabilities2(self):
        return QgsDataItem.Fast

    def createChildren(self):
        items = []

        if not self.network_manager.has_token():
            dlg = CloudLoginDialog(self.network_manager)
            dlg.authenticate()
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

        public_projects = QFieldCloudGroupItem(
            self, "Public projects", "public", "../resources/cloud.svg", 2
        )
        items.append(public_projects)

        return items

    def actions(self, parent):
        actions = []

        projects_overview_action = QAction(
            QIcon(os.path.join(os.path.dirname(__file__), "../resources/cloud.svg")),
            self.tr("Projects Overview"),
            parent,
        )
        projects_overview_action.triggered.connect(
            lambda: CloudProjectsDialog(self.network_manager, iface.mainWindow()).show()
        )

        refresh_action = QAction(
            QIcon(os.path.join(os.path.dirname(__file__), "../resources/refresh.png")),
            "Refresh Projects",
            parent,
        )
        refresh_action.triggered.connect(lambda: self.refresh_projects())

        actions.append(projects_overview_action)
        actions.append(refresh_action)

        return actions

    def refresh_projects(self):
        if not self.network_manager.has_token():
            dlg = CloudLoginDialog(self.network_manager)
            dlg.authenticate()
            dlg.accepted.connect(lambda: self.refresh_projects())
            return

        if self.network_manager.is_login_active:
            return

        self.network_manager.projects_cache.refresh()

    def refreshing_projects(self):
        self.depopulate()
        self.refresh()

    def refresh_icon(self):
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

        self.refresh()


class QFieldCloudGroupItem(QgsDataCollectionItem):
    """ QFieldCloud group data item. """

    def __init__(self, parent, name, project_type, icon, order):
        super(QFieldCloudGroupItem, self).__init__(parent, name, "/QFieldCloud/" + name)

        self.network_manager = parent.network_manager
        self.project_type = project_type
        self.setIcon(QIcon(os.path.join(os.path.dirname(__file__), icon)))
        self.setSortKey(order)

    def createChildren(self):
        items = []

        projects: List[CloudProject] = self.network_manager.projects_cache.projects

        if projects is None:
            try:
                # TODO try to be make it Fast Fertile
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

    def actions(self, parent):
        actions = []

        create = QAction(
            QIcon(os.path.join(os.path.dirname(__file__), "../resources/edit.svg")),
            "Create New Project",
            parent,
        )
        create.triggered.connect(
            lambda: CloudProjectsDialog(
                self.network_manager, iface.mainWindow()
            ).show_project_form()
        )

        actions.append(create)

        return actions


class QFieldCloudProjectItem(QgsDataItem):
    """ QFieldCloud project item. """

    def __init__(self, parent, project):
        super(QFieldCloudProjectItem, self).__init__(
            QgsDataItem.Collection,
            parent,
            project.name,
            "/QFieldCloud/project/" + project.id,
        )
        self.project_id = project.id

    def _create_projects_dialog(self) -> CloudProjectsDialog:
        network_manager = self.parent().parent().network_manager
        # it is important to get the project like this, because if the project list is refreshed, here we will store an old reference
        project = network_manager.projects_cache.find_project(self.project_id)
        return CloudProjectsDialog(network_manager, iface.mainWindow(), project=project)

    def show_cloud_synchronize_dialog(self):
        network_manager = self.parent().parent().network_manager
        project = network_manager.projects_cache.find_project(self.project_id)
        dlg = CloudTransferDialog(network_manager, project, iface.mainWindow())
        dlg.show()

    def open_project(self) -> bool:
        network_manager = self.parent().parent().network_manager
        project = network_manager.projects_cache.find_project(self.project_id)
        if project.local_dir:
            project_file_name = glob.glob(
                os.path.join(project.local_dir, "*.qgs")
            ) + glob.glob(os.path.join(project.local_dir, "*.qgz"))
            print(project_file_name)
            if project_file_name:
                iface.addProject(os.path.join(project.local_dir, project_file_name[0]))
                return True

        return False

    def actions(self, parent):
        actions = []

        network_manager = self.parent().parent().network_manager
        project = network_manager.projects_cache.find_project(self.project_id)
        if project.local_dir:
            open_action = QAction(QIcon(), "Open Project", parent)
            open_action.triggered.connect(lambda: self.open_project())
            actions.append(open_action)

        sync_action = QAction(
            QIcon(os.path.join(os.path.dirname(__file__), "../resources/sync.svg")),
            "Synchronize Project",
            parent,
        )
        sync_action.triggered.connect(lambda: self.show_cloud_synchronize_dialog())
        actions.append(sync_action)

        properties_action = QAction(QIcon(), "Project Properties", parent)
        properties_action.triggered.connect(
            lambda: self._create_projects_dialog().show_project_form()
        )
        actions.append(properties_action)

        return actions

    def handleDoubleClick(self):
        if not self.open_project():
            self._create_projects_dialog().show_project_form()
        return True
