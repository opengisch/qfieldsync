"""
/***************************************************************************
 QFieldSyncDialog
                                 A QGIS plugin
 Sync your projects to QField
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

from libqfieldsync.layer import LayerSource, SyncAction
from qgis.core import QgsApplication, QgsMapLayerModel, QgsProject
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QComboBox,
    QHeaderView,
    QMenu,
    QTableWidgetItem,
    QToolButton,
    QWidget,
)
from qgis.PyQt.uic import loadUiType
from qgis.utils import iface

from qfieldsync.core.message_bus import message_bus
from qfieldsync.gui.utils import set_available_actions

LayersConfigWidgetUi, _ = loadUiType(
    os.path.join(os.path.dirname(__file__), "../ui/layers_config_widget.ui")
)


class LayersConfigWidget(QWidget, LayersConfigWidgetUi):
    def __init__(self, project, use_cloud_actions, layer_sources, parent=None):
        """Constructor."""
        super().__init__(parent=parent)
        self.setupUi(self)

        self.project = project
        self.use_cloud_actions = use_cloud_actions
        self.layer_sources = layer_sources

        self.layersTable.setAlternatingRowColors(True)
        self.layersTable.verticalHeader().setVisible(False)
        self.layersTable.setColumnCount(3)
        self.layersTable.setHorizontalHeaderLabels(
            [self.tr("Layer"), self.tr("Packaging Action"), ""]
        )
        self.layersTable.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

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
        self.multipleToggleButton.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.toggleMenu.triggered.connect(self._on_toggle_menu_triggered)

        self.settingsPackagingButton.setVisible(False)
        if self.use_cloud_actions:
            self.settingsPackagingButton.setVisible(True)
            self.settingsPackagingButton.setIcon(
                QgsApplication.getThemeIcon("/propertyicons/settings.svg")
            )
            self.settingsPackagingMenu = QMenu(self)
            self.preferOnlineAction = QAction(
                self.tr("Prefer Online layers"), self.settingsPackagingButton
            )
            self.preferOfflineAction = QAction(
                self.tr("Prefer Offline layers"), self.settingsPackagingButton
            )
            self.settingsPackagingMenu.addAction(self.preferOnlineAction)
            self.settingsPackagingMenu.addAction(self.preferOfflineAction)

            self.settingsPackagingButton.setMenu(self.settingsPackagingMenu)

            self.settingsPackagingMenu.triggered.connect(
                self._on_layer_action_preference_changed
            )

            self.horizontalLayout.addWidget(self.settingsPackagingButton)

        self.unsupportedLayersList = []

        self._on_message_bus_messaged_wrapper = (
            lambda msg: self._on_message_bus_messaged(msg)
        )
        message_bus.messaged.connect(self._on_message_bus_messaged_wrapper)

        self.showVisibleLayersOnlyCheckbox.stateChanged.connect(self._reload_project)
        self.textFilterBox.textChanged.connect(self._reload_project)

        self._reload_project()

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

    def get_default_action(self, layer_source):
        if self.use_cloud_actions:
            return layer_source.default_cloud_action
        else:
            return layer_source.default_action

    def _reload_project(self):
        """Load all layers from the map layer registry into the table."""
        self.unsupportedLayersList = []

        self.layersTable.setRowCount(0)
        self.layersTable.setSortingEnabled(False)

        # Get filtered layers
        show_visible_only = self.showVisibleLayersOnlyCheckbox.isChecked()
        filter_text = self.textFilterBox.text().lower()

        layers = []
        if show_visible_only:
            for layer_source in self.layer_sources:
                if (
                    QgsProject.instance()
                    .layerTreeRoot()
                    .findLayer(layer_source.layer.id())
                    .isVisible()
                ):
                    layers.append(layer_source)
        else:
            layers = self.layer_sources

        for layer_source in layers:
            layer_name = layer_source.layer.name().lower()

            if filter_text and filter_text not in layer_name:
                continue

            count = self.layersTable.rowCount()
            self.layersTable.insertRow(count)
            item = QTableWidgetItem(layer_source.layer.name())
            item.setData(Qt.ItemDataRole.UserRole, layer_source)
            item.setData(Qt.ItemDataRole.EditRole, layer_source.layer.name())
            item.setIcon(QgsMapLayerModel.iconForLayer(layer_source.layer))
            self.layersTable.setItem(count, 0, item)

            cmb = QComboBox()
            available_actions = self.get_available_actions(layer_source)
            set_available_actions(
                cmb, available_actions, self.get_layer_action(layer_source)
            )

            properties_btn = QToolButton()
            properties_btn.setIcon(
                QgsApplication.getThemeIcon("/propertyicons/settings.svg")
            )
            properties_btn.setAutoRaise(True)
            properties_btn.clicked.connect(
                self._on_properties_button_clicked(layer_source)
            )

            self.layersTable.setCellWidget(count, 1, cmb)
            self.layersTable.setCellWidget(count, 2, properties_btn)

            if not layer_source.is_supported:
                self.unsupportedLayersList.append(layer_source)
                self.layersTable.item(count, 0).setFlags(Qt.ItemFlag.NoItemFlags)
                self.layersTable.cellWidget(count, 1).setEnabled(False)
                cmb.setCurrentIndex(cmb.findData(SyncAction.REMOVE))

        self.layersTable.resizeColumnsToContents()
        self.layersTable.sortByColumn(0, Qt.SortOrder.AscendingOrder)
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

    def _on_properties_button_clicked(self, layer_source: LayerSource) -> Callable:
        def clicked_callback() -> None:
            iface.showLayerProperties(layer_source.layer, "QFieldLayerSettingsPage")

        return clicked_callback

    def _on_layer_action_preference_changed(self, action: QAction):
        """Toggle when prefer online or offline menu actions have been triggered."""
        prefer_online = action == self.preferOnlineAction

        for i in range(self.layersTable.rowCount()):
            item = self.layersTable.item(i, 0)
            layer_source = item.data(Qt.ItemDataRole.UserRole)
            cmb = self.layersTable.cellWidget(i, 1)

            # It would be annoying to change the action on removed layers.
            if cmb.itemData(cmb.currentIndex()) == SyncAction.REMOVE:
                continue

            idx, _cloud_action = layer_source.preferred_cloud_action(prefer_online)
            cmb.setCurrentIndex(idx)

    def _on_toggle_menu_triggered(self, action):
        """
        Toggles usage of layers
        :param action: the menu action that triggered this
        """
        sync_action = None
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
                layer_source = item.data(Qt.ItemDataRole.UserRole)
                old_action = self.get_layer_action(layer_source)
                available_actions, _ = zip(*self.get_available_actions(layer_source))
                layer_sync_action = (
                    self.get_default_action(layer_source)
                    if sync_action is None
                    else sync_action
                )
                if layer_sync_action in available_actions:
                    self.set_layer_action(layer_source, layer_sync_action)
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
            visible = action != self.removeHiddenAction
            root = QgsProject.instance().layerTreeRoot()
            for layer in QgsProject.instance().mapLayers().values():
                node = root.findLayer(layer.id())
                if node and node.isVisible() == visible:
                    layer_source = LayerSource(layer)
                    old_action = self.get_layer_action(layer_source)
                    available_actions, _ = zip(
                        *self.get_available_actions(layer_source)
                    )
                    layer_sync_action = (
                        self.get_default_action(layer_source)
                        if sync_action is None
                        else sync_action
                    )
                    if layer_sync_action in available_actions:
                        self.set_layer_action(layer_source, layer_sync_action)
                        if self.get_layer_action(layer_source) != old_action:
                            self.project.setDirty(True)
                        layer_source.apply()
                        is_project_dirty |= layer_source.apply()

        if is_project_dirty:
            self.project.setDirty(True)

        self._reload_project()

    def apply(self):
        is_project_dirty = False

        for i in range(self.layersTable.rowCount()):
            item = self.layersTable.item(i, 0)
            layer_source = item.data(Qt.ItemDataRole.UserRole)
            cmb = self.layersTable.cellWidget(i, 1)

            self.set_layer_action(layer_source, cmb.itemData(cmb.currentIndex()))

            is_project_dirty |= layer_source.apply()

        if is_project_dirty:
            self.project.setDirty(True)

    def _on_message_bus_messaged(self, msg: str) -> None:
        # when MapLayerConfigWidget.apply() detects changes in layer settings,
        # the event is emitted with `layer_config_saved` as a message.
        # check ./gui/map_layer_config_widget.py
        if msg != "layer_config_saved":
            return

        for layer_source in self.layer_sources.copy():
            try:
                layer_source.read_layer()
            except RuntimeError:  # noqa: PERF203
                self.layer_sources.remove(layer_source)

        # quite ugly workaround, but this method sometimes operates on deleted objects,
        # so we need to make sure we don't get exceptions
        try:
            self._reload_project()
        except Exception:
            message_bus.messaged.disconnect(self._on_message_bus_messaged_wrapper)
