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

from pathlib import Path

from qgis.core import QgsMapLayer, QgsProject
from qgis.PyQt.QtCore import QCoreApplication, QObject, pyqtSignal
from qgis.utils import iface

from qfieldsync.libqfieldsync.layer import LayerSource
from qfieldsync.libqfieldsync.utils.file_utils import copy_images
from qfieldsync.libqfieldsync.utils.qgis import (
    get_qgis_files_within_dir,
    make_temp_qgis_file,
)
from qfieldsync.utils.qgis_utils import open_project


class CloudConverter(QObject):
    progressStopped = pyqtSignal()
    warning = pyqtSignal(str, str)
    total_progress_updated = pyqtSignal(int, int, str)

    def __init__(
        self,
        project: QgsProject,
        export_dirname: str,
    ):

        super(CloudConverter, self).__init__(parent=None)
        self.project = project
        self.__layers = list()

        # elipsis workaround
        self.trUtf8 = self.tr

        self.export_dirname = Path(export_dirname)

    def convert(self) -> None:  # noqa: C901
        """
        Convert the project to a cloud project.
        """

        original_project_path = self.project.fileName()
        project_path = self.export_dirname.joinpath(
            f"{self.project.baseName()}_cloud.qgs"
        )
        backup_project_path = make_temp_qgis_file(self.project)
        is_converted = False

        try:
            if not self.export_dirname.exists():
                self.export_dirname.mkdir(parents=True, exist_ok=True)

            if get_qgis_files_within_dir(self.export_dirname):
                raise Exception(
                    self.tr("The destination folder already contains a project file")
                )

            self.total_progress_updated.emit(0, 100, self.trUtf8("Converting project…"))
            self.__layers = list(self.project.mapLayers().values())

            # Loop through all layers and copy them to the destination folder
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
                    # layer stored in localized data path, skip
                    if layer_source.is_localized_path:
                        continue

                if layer.type() == QgsMapLayer.VectorLayer:
                    if not layer_source.convert_to_gpkg(self.export_dirname):
                        # something went wrong, remove layer and inform the user that layer will be missing
                        self.project.removeMapLayer(layer)
                        self.warning.emit(
                            self.tr("Cloud Converter"),
                            self.tr(
                                "The layer '{}' could not be converted and was therefore removed from the cloud project."
                            ).format(layer.name()),
                        )
                else:
                    layer_source.copy(self.export_dirname, list())

            # save the offline project twice so that the offline plugin can "know" that it's a relative path
            if not self.project.write(str(project_path)):
                raise Exception(
                    self.tr('Failed to save project to "{}".').format(project_path)
                )

            # export the DCIM folder
            copy_images(
                str(Path(original_project_path).parent.joinpath("DCIM")),
                str(project_path.parent.joinpath("DCIM")),
            )

            title = self.project.title()
            title_suffix = self.tr("(QFieldCloud)")
            if not title.endswith(title_suffix):
                self.project.setTitle("{} {}".format(title, title_suffix))
            # Now we have a project state which can be saved as cloud project
            self.project.write(str(project_path))
            is_converted = True
        finally:
            # We need to let the app handle events before loading the next project or QGIS will crash with rasters
            QCoreApplication.processEvents()
            self.project.clear()
            QCoreApplication.processEvents()

            # TODO whatcha gonna do if QgsProject::read()/write() fails
            if is_converted:
                iface.addProject(str(project_path))
            else:
                open_project(original_project_path, backup_project_path)

        self.total_progress_updated.emit(100, 100, self.tr("Finished"))
