# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSyncDialog
                                 A QGIS plugin
 Sync your projects to QField on android
                             -------------------
        begin                : 2020-10-10
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
from typing import Callable

from PyQt5.QtWidgets import QPushButton
from qgis.core import Qgis, QgsMapLayerModel, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QComboBox,
    QMenu,
    QTableWidgetItem,
    QToolButton,
    QWidget,
)
from qgis.PyQt.uic import loadUiType
from qgis.utils import iface

from qfieldsync.gui.utils import set_available_actions
from qfieldsync.libqfieldsync.layer import LayerSource, SyncAction

LayersConfigWidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/layers_config_widget.ui")
)


class LayersConfigWidget(QWidget, LayersConfigWidgetUi):
    def __init__(self, project, use_cloud_actions, layer_sources, parent=None):
        """Constructor."""
        super(LayersConfigWidget, self).__init__(parent=parent)
        self.setupUi(self)

        self.project = project
        self.use_cloud_actions = use_cloud_actions
        self.layer_sources = layer_sources

        self.multipleToggleButton.setIcon(
            QIcon(
                os.path.join(os.path.dirname(__file__), "../resources/visibility.svg")
            )
        )
        self.toggleMenu = QMenu(self)
        self.removeAllAction = QAction(self.tr("Remove All Layers"), self.toggleMenu)
        self.toggleMenu.addAction(self.removeAllAction)
        self.removeHiddenAction = QAction(
            self.tr("Remove Hidden Layers"), self.toggleMenu
        )
        self.toggleMenu.addAction(self.removeHiddenAction)
        self.addAllCopyAction = QAction(self.tr("Add All Layers"), self.toggleMenu)
        self.toggleMenu.addAction(self.addAllCopyAction)
        self.addVisibleCopyAction = QAction(
            self.tr("Add Visible Layers"), self.toggleMenu
        )
        self.toggleMenu.addAction(self.addVisibleCopyAction)
        self.addAllOfflineAction = QAction(
            self.tr("Add All Vector Layers as Offline"), self.toggleMenu
        )
        self.toggleMenu.addAction(self.addAllOfflineAction)
        self.addVisibleOfflineAction = QAction(
            self.tr("Add Visible Vector Layers as Offline"), self.toggleMenu
        )
        self.toggleMenu.addAction(self.addVisibleOfflineAction)
        self.multipleToggleButton.setMenu(self.toggleMenu)
        self.multipleToggleButton.setAutoRaise(True)
        self.multipleToggleButton.setPopupMode(QToolButton.InstantPopup)
        self.toggleMenu.triggered.connect(self.toggleMenu_triggered)
        self.unsupportedLayersList = list()

        self.reloadProject()

    def get_available_actions(self, layer_source):
        if self.use_cloud_actions:
            return layer_source.available_cloud_actions
        else:
            return layer_source.available_actions

    def get_layer_action(self, layer_source):
        if self.use_cloud_actions:
            return layer_source.cloud_action
        else:
            return layer_source.action

    def set_layer_action(self, layer_source, action):
        if self.use_cloud_actions:
            layer_source.cloud_action = action
        else:
            layer_source.action = action

    def reloadProject(self):
        """
        Load all layers from the map layer registry into the table.
        """
        self.unsupportedLayersList = list()

        self.layersTable.setRowCount(0)
        self.layersTable.setSortingEnabled(False)
        for layer_source in self.layer_sources:
            count = self.layersTable.rowCount()
            self.layersTable.insertRow(count)
            item = QTableWidgetItem(layer_source.layer.name())
            item.setData(Qt.UserRole, layer_source)
            item.setData(Qt.EditRole, layer_source.layer.name())
            item.setIcon(QgsMapLayerModel.iconForLayer(layer_source.layer))
            self.layersTable.setItem(count, 0, item)

            cmb = QComboBox()
            available_actions = self.get_available_actions(layer_source)
            set_available_actions(
                cmb, available_actions, self.get_layer_action(layer_source)
            )

            properties_btn = QPushButton()
            properties_btn.setText(self.tr("Properties"))
            properties_btn.clicked.connect(self.propertiesBtn_clicked(layer_source))

            self.layersTable.setCellWidget(count, 1, cmb)
            self.layersTable.setCellWidget(count, 2, properties_btn)

            if not layer_source.is_supported:
                self.unsupportedLayersList.append(layer_source)
                self.layersTable.item(count, 0).setFlags(Qt.NoItemFlags)
                self.layersTable.cellWidget(count, 1).setEnabled(False)
                cmb.setCurrentIndex(cmb.findData(SyncAction.REMOVE))

        self.layersTable.resizeColumnsToContents()
        self.layersTable.sortByColumn(0, Qt.AscendingOrder)
        self.layersTable.setSortingEnabled(True)

        if self.unsupportedLayersList:
            self.unsupportedLayersLabel.setVisible(True)

            unsupported_layers_text = "<b>{}: </b>".format(self.tr("Warning"))
            unsupported_layers_text += self.tr(
                "There are unsupported layers in your project which will not be available in QField."
            )
            unsupported_layers_text += self.tr(
                " If needed, you can create a Base Map to include those layers in your packaged project."
            )
            self.unsupportedLayersLabel.setText(unsupported_layers_text)

    def propertiesBtn_clicked(self, layer_source: LayerSource) -> Callable:
        def clicked_callback() -> None:
            if Qgis.QGIS_VERSION_INT >= 31900:
                iface.showLayerProperties(layer_source.layer, "QFieldLayerSettingsPage")
            else:
                iface.showLayerProperties(layer_source.layer)

        return clicked_callback

    def toggleMenu_triggered(self, action):
        """
        Toggles usage of layers
        :param action: the menu action that triggered this
        """
        sync_action = SyncAction.NO_ACTION
        if action in (self.removeHiddenAction, self.removeAllAction):
            sync_action = SyncAction.REMOVE
        elif action in (self.addAllOfflineAction, self.addVisibleOfflineAction):
            sync_action = SyncAction.OFFLINE

        is_project_dirty = False
        # all layers
        if action in (
            self.removeAllAction,
            self.addAllCopyAction,
            self.addAllOfflineAction,
        ):
            for i in range(self.layersTable.rowCount()):
                item = self.layersTable.item(i, 0)
                layer_source = item.data(Qt.UserRole)
                old_action = self.get_layer_action(layer_source)
                available_actions, _ = zip(*self.get_available_actions(layer_source))
                if sync_action in available_actions:
                    self.set_layer_action(layer_source, sync_action)
                    if self.get_layer_action(layer_source) != old_action:
                        self.project.setDirty(True)
                    layer_source.apply()
                    is_project_dirty |= layer_source.apply()
        # based on visibility
        elif action in (
            self.removeHiddenAction,
            self.addVisibleCopyAction,
            self.addVisibleOfflineAction,
        ):
            visible = Qt.Unchecked if action == self.removeHiddenAction else Qt.Checked
            root = QgsProject.instance().layerTreeRoot()
            for layer in QgsProject.instance().mapLayers().values():
                node = root.findLayer(layer.id())
                if node and node.isVisible() == visible:
                    layer_source = LayerSource(layer)
                    old_action = self.get_layer_action(layer_source)
                    available_actions, _ = zip(
                        *self.get_available_actions(layer_source)
                    )
                    if sync_action in available_actions:
                        self.set_layer_action(layer_source, sync_action)
                        if self.get_layer_action(layer_source) != old_action:
                            self.project.setDirty(True)
                        layer_source.apply()
                        is_project_dirty |= layer_source.apply()

        if is_project_dirty:
            self.project.setDirty(True)

        self.reloadProject()

    def apply(self):
        is_project_dirty = False

        for i in range(self.layersTable.rowCount()):
            item = self.layersTable.item(i, 0)
            layer_source = item.data(Qt.UserRole)
            cmb = self.layersTable.cellWidget(i, 1)

            self.set_layer_action(layer_source, cmb.itemData(cmb.currentIndex()))

            is_project_dirty |= layer_source.apply()

        if is_project_dirty:
            self.project.setDirty(True)
