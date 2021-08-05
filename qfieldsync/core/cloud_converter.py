# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
                              -------------------
        begin                : 2021-07-20
        git sha              : $Format:%H$
        copyright            : (C) 2021 by OPENGIS.ch
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

from qgis.core import QgsMapLayer, QgsProject, QgsProviderRegistry
from qgis.PyQt.QtCore import QCoreApplication, QObject, pyqtSignal

from qfieldsync.libqfieldsync.layer import LayerSource
from qfieldsync.libqfieldsync.utils.file_utils import copy_images


class CloudConverter(QObject):
    progressStopped = pyqtSignal()
    warning = pyqtSignal(str, str)
    total_progress_updated = pyqtSignal(int, int, str)

    def __init__(
        self,
        project: QgsProject,
        export_folder: str,
    ):

        super(CloudConverter, self).__init__(parent=None)
        self.project = project
        self.__layers = list()

        # elipsis workaround
        self.trUtf8 = self.tr

        self.export_folder = export_folder

    def convert(self) -> None:  # noqa: C901
        """
        Convert the project to a cloud project.
        """

        original_project_path = self.project.fileName()
        project_path = os.path.join(
            self.export_folder, f"{self.project.baseName()}_cloud.qgs"
        )
        is_converted = False
        try:
            if not os.path.exists(self.export_folder):
                os.makedirs(self.export_folder)

            if glob.glob(os.path.join(self.export_folder, "*.qgs")) or glob.glob(
                os.path.join(self.export_folder, "*.qgz")
            ):
                raise Exception(
                    self.tr("The destination folder already contains a project file")
                )

            self.total_progress_updated.emit(0, 100, self.trUtf8("Converting project…"))
            self.__layers = list(self.project.mapLayers().values())

            # Loop through all layers and copy them to the destination folder
            pathResolver = self.project.pathResolver()
            for current_layer_index, layer in enumerate(self.__layers):
                self.total_progress_updated.emit(
                    current_layer_index,
                    len(self.__layers),
                    self.trUtf8("Copying layers…"),
                )

                layer_source = LayerSource(layer)
                if not layer_source.is_supported:
                    self.project.removeMapLayer(layer)
                    continue

                if layer.dataProvider() is not None:
                    provider_metadata = QgsProviderRegistry.instance().providerMetadata(
                        layer.dataProvider().name()
                    )
                    if provider_metadata is not None:
                        decoded = provider_metadata.decodeUri(layer.source())
                        if "path" in decoded:
                            path = pathResolver.writePath(decoded["path"])
                            if path.startswith("localized:"):
                                # layer stored in localized data path, skip
                                continue

                if layer.type() == QgsMapLayer.VectorLayer:
                    if not layer_source.convert_to_gpkg(self.export_folder):
                        # something went wrong, remove layer and inform the user that layer will be missing
                        self.project.removeMapLayer(layer)
                        self.warning.emit(
                            self.tr("Cloud Converter"),
                            self.tr(
                                "The layer '{}' could not be converted and was therefore removed from the cloud project."
                            ).format(layer.name()),
                        )
                else:
                    layer_source.copy(self.export_folder, list())

            # save the offline project twice so that the offline plugin can "know" that it's a relative path
            if not self.project.write(project_path):
                raise Exception(
                    self.tr('Failed to save project to "{}".').format(project_path)
                )

            # export the DCIM folder
            copy_images(
                os.path.join(os.path.dirname(original_project_path), "DCIM"),
                os.path.join(os.path.dirname(project_path), "DCIM"),
            )

            # Now we have a project state which can be saved as cloud project
            self.project.write(project_path)
            is_converted = True
        finally:
            # We need to let the app handle events before loading the next project or QGIS will crash with rasters
            QCoreApplication.processEvents()
            self.project.clear()
            QCoreApplication.processEvents()
            if is_converted:
                self.project.read(project_path)
                self.project.setFileName(project_path)
            else:
                self.project.read(original_project_path)
                self.project.setFileName(original_project_path)

        self.total_progress_updated.emit(100, 100, self.tr("Finished"))
