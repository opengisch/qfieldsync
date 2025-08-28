"""
/***************************************************************************
 QFieldSync
                             -------------------
        begin                : 2020-08-01
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


import hashlib
import os
import sqlite3
from enum import IntFlag
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from libqfieldsync.utils.qgis import get_qgis_files_within_dir
from qgis.core import Qgis, QgsApplication, QgsProject, QgsProviderRegistry
from qgis.PyQt.QtCore import QDir

from qfieldsync.core.preferences import Preferences


class ProjectFileCheckout(IntFlag):
    Deleted = 0
    Local = 1
    Cloud = 2
    LocalAndCloud = 3


def calc_etag(filename: Union[str, Path], part_size: int = 8 * 1024 * 1024) -> str:
    """
    Calculate ETag as in Object Storage (S3) of a local file.

    ETag is a MD5. But for the multipart uploaded files, the MD5 is computed from the concatenation of the MD5s of each uploaded part.

    See the inspiration of this implementation here: https://stackoverflow.com/a/58239738/1226137

    Args:
        filename (str): the local filename
        part_size (int): the size of the Object Storage part. Most Object Storages use 8MB. Defaults to 8*1024*1024.

    Returns:
        str: the calculated ETag value
    """
    with open(filename, "rb") as f:
        file_size = os.fstat(f.fileno()).st_size

        if file_size <= part_size:
            BLOCKSIZE = 65536
            # TODO @suricactus: Python 3.9, pass `usedforsecurity=False`
            hasher = hashlib.md5()  # noqa: S324

            buf = f.read(BLOCKSIZE)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(BLOCKSIZE)

            return hasher.hexdigest()
        else:
            # Say you uploaded a 14MB file and your part size is 5MB.
            # Calculate 3 MD5 checksums corresponding to each part, i.e. the checksum of the first 5MB, the second 5MB, and the last 4MB.
            # Then take the checksum of their concatenation.
            # Since MD5 checksums are hex representations of binary data, just make sure you take the MD5 of the decoded binary concatenation, not of the ASCII or UTF-8 encoded concatenation.
            # When that's done, add a hyphen and the number of parts to get the ETag.
            md5sums = []
            for data in iter(lambda: f.read(part_size), b""):
                # TODO @suricactus: Python 3.9, pass `usedforsecurity=False`
                md5sums.append(hashlib.md5(data).digest())  # noqa: S324

            # TODO @suricactus: Python 3.9, pass `usedforsecurity=False`
            final_md5sum = hashlib.md5(b"".join(md5sums))  # noqa: S324

            return "{}-{}".format(final_md5sum.hexdigest(), len(md5sums))


class ProjectFile:
    def __init__(self, data: Dict[str, Any], local_dir: Optional[str] = None) -> None:
        self._local_dir = local_dir
        self._temp_dir = None
        self._data = data

    @property
    def name(self) -> str:
        return self._data["name"]

    @property
    def path(self) -> Path:
        return Path(self.name)

    @property
    def dirname(self) -> str:
        return str(self.path.parent)

    @property
    def created_at(self) -> Optional[str]:
        if not self.versions:
            return None

        return self.versions[-1].get("last_modified")

    @property
    def updated_at(self) -> Optional[str]:
        if not self.versions:
            return None

        return self.versions[0].get("last_modified")

    @property
    def versions(self) -> Optional[List[Dict[str, str]]]:
        return self._data.get("versions")

    @property
    def checkout(self) -> ProjectFileCheckout:
        checkout = ProjectFileCheckout.Deleted

        if self.local_path and self.local_path.exists():
            checkout |= ProjectFileCheckout.Local

        # indirect way to check whether it is a cloud project
        if self.size is not None:
            checkout |= ProjectFileCheckout.Cloud

        return checkout

    @property
    def size(self) -> Optional[int]:
        return self._data.get("size")

    @property
    def sha256(self) -> Optional[str]:
        return self._data.get("sha256")

    @property
    def etag(self) -> Optional[str]:
        # NOTE the etag is actually stored in the `md5sum` key by mistake
        return self._data.get("md5sum")

    @property
    def local_size(self) -> Optional[int]:
        if not self.local_path_exists:
            return None

        assert self.local_path

        return self.local_path.stat().st_size

    @property
    def local_dir(self) -> Optional[str]:
        return self._local_dir

    @property
    def local_path(self) -> Optional[Path]:
        if not self._local_dir:
            return None

        return Path(self._local_dir + "/" + self.name)

    @property
    def local_path_exists(self) -> bool:
        if self.local_path:
            return self.local_path.exists()

        return False

    @property
    def local_sha256(self) -> Optional[str]:
        if not self.local_path_exists:
            return None

        assert self.local_path
        assert self.local_path.is_file()

        with open(self.local_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    @property
    def local_etag(self) -> Optional[str]:
        if not self.local_path_exists:
            return None

        assert self.local_path
        assert self.local_path.is_file()

        return calc_etag(self.local_path)

    def flush(self) -> None:
        if not self._local_dir:
            return

        if self.name.endswith(".gpkg"):
            path = Path(str(self.local_path) + "-wal")
            if path.exists() and path.stat().st_size > 0:
                conn = sqlite3.connect(str(self.local_path))

                with conn:
                    conn.execute("PRAGMA wal_checkpoint")


class CloudProject:
    def __init__(self, project_data: Dict[str, Any]) -> None:
        """Constructor."""
        self._preferences = Preferences()
        self._files = {}
        self._data = {}
        self._cloud_files = None
        self._local_dir = None

        self.update_data(project_data)

    def update_data(self, new_data: Dict[str, Any]) -> None:
        self._data = {**self._data, **new_data}
        # make sure empty string is converted to None

        if "local_dir" in new_data and self._local_dir != new_data.get("local_dir"):
            self._local_dir = (self._data.get("local_dir") or "").strip() or None

            del self._data["local_dir"]

            if self._local_dir and not Path(self._local_dir).is_absolute():
                self._local_dir = None

            old_project_local_dirs = self._preferences.value(
                "qfieldCloudProjectLocalDirs"
            )
            new_value = {
                **old_project_local_dirs,
                self.id: self._local_dir,
            }

            self._preferences.set_value("qfieldCloudProjectLocalDirs", new_value)

            if self._local_dir:
                Path(self._local_dir).mkdir(exist_ok=True, parents=True)

        # NOTE the cloud_files value is a list and may be in any order, so always assume that if the key is present in the new data, then there is a change
        if "cloud_files" in new_data:
            self._cloud_files = self._data.get("cloud_files")

            del self._data["cloud_files"]

            if isinstance(self._cloud_files, list):
                self._preferences.set_value(
                    "qfieldCloudLastProjectFiles",
                    {
                        **self._preferences.value("qfieldCloudLastProjectFiles"),
                        self.id: [
                            cloud_file["name"] for cloud_file in self._cloud_files
                        ],
                    },
                )
                self._cloud_files = sorted(self._cloud_files, key=lambda f: f["name"])
            else:
                assert self._cloud_files is None

        if "cloud_files" in new_data or "local_dir" in new_data or not self._files:
            self.refresh_files()

    @staticmethod
    def get_cloud_project_id(path: str) -> Optional[str]:
        project_local_dirs: Dict[str, str] = Preferences().value(
            "qfieldCloudProjectLocalDirs"
        )

        for project_id, project_path in project_local_dirs.items():
            if project_path == path:
                return project_id

        return None

    @property
    def id(self) -> str:
        return self._data["id"]

    @property
    def name(self) -> str:
        return self._data["name"]

    @property
    def owner(self) -> str:
        return self._data["owner"]

    @property
    def description(self) -> str:
        return self._data["description"]

    @property
    def is_private(self) -> bool:
        return self._data["private"]

    @property
    def created_at(self) -> str:
        return self._data["created_at"]

    @property
    def updated_at(self) -> str:
        return self._data["updated_at"]

    @property
    def user_role(self) -> str:
        return self._data["user_role"]

    @property
    def user_role_origin(self) -> str:
        return self._data["user_role_origin"]

    @property
    def status(self) -> bool:
        # TODO @suricactus: remove as soon as all API servers support `status` key
        return self._data.get("status", "busy")

    @property
    def local_dir(self) -> Optional[str]:
        dirname = self._preferences.value("qfieldCloudProjectLocalDirs").get(self.id)

        if not dirname or not Path(dirname).exists() or not Path(dirname).is_absolute():
            return None

        return dirname

    @property
    def human_local_dir(self) -> Optional[str]:
        dirname = self._preferences.value("qfieldCloudProjectLocalDirs").get(self.id)

        if not dirname or not Path(dirname).exists() or not Path(dirname).is_absolute():
            return None

        if QDir(dirname).absolutePath().startswith(QDir.homePath()):
            return f"{QDir.toNativeSeparators(QDir.home().relativeFilePath(dirname))}"
        else:
            return dirname

    @property
    def cloud_files(self) -> Optional[List]:
        return self._cloud_files

    @property
    def files_to_sync(self) -> Iterator[ProjectFile]:
        for project_file in self.get_files():
            project_file.flush()

            # don't attempt to sync files that are the same both locally and remote
            if project_file.etag == project_file.local_etag:
                continue

            # ignore local files that are not in the temp directory
            if (
                project_file.checkout & ProjectFileCheckout.Local
                and not project_file.local_path_exists
            ):
                continue

            yield project_file

    @property
    def is_current_qgis_project(self) -> bool:
        project_home_path = QgsProject.instance().homePath()

        return len(project_home_path) > 0 and self.local_dir == project_home_path

    @property
    def url(self) -> str:
        return f"a/{self.owner}/{self.name}"

    @property
    def name_with_owner(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def root_project_files(self) -> List[Path]:
        if self.local_dir:
            return get_qgis_files_within_dir(Path(self.local_dir))
        else:
            return []

    @property
    def local_project_file(self) -> Optional[ProjectFile]:
        if len(self.root_project_files) != 1:
            return None

        for project_file in self.get_files():
            if project_file.local_path == self.root_project_files[0]:
                return project_file

        return None

    def get_localized_dataset_files(self) -> List[ProjectFile]:
        localized_data_paths = (
            QgsApplication.instance().localizedDataPathRegistry().paths()
        )
        if (
            len(localized_data_paths) == 0
            or not self.local_project_file
            or not self.local_project_file.local_path_exists
        ):
            return []

        read_flags = QgsProject.ReadFlags()
        read_flags |= QgsProject.FlagDontLoadLayouts
        read_flags |= QgsProject.FlagTrustLayerMetadata

        if Qgis.versionInt() >= 32600:
            read_flags |= QgsProject.FlagDontLoad3DViews

        temporary_project = QgsProject()
        temporary_project.read(str(self.local_project_file.local_path), read_flags)
        layers = temporary_project.mapLayers()

        localized_datasets_files = []
        for layer in layers.values():
            if not layer.dataProvider():
                continue

            metadata = QgsProviderRegistry.instance().providerMetadata(
                layer.dataProvider().name()
            )
            metadata.decodeUri(layer.source())

            filename = metadata.decodeUri(layer.source()).get("path", "")
            if not filename:
                continue

            for localized_data_path in localized_data_paths:
                if not filename.startswith(localized_data_path):
                    continue

                localized_datasets_name = (
                    Path(filename).relative_to(localized_data_path).as_posix()
                )
                localized_datasets_files.append(
                    ProjectFile(
                        {"name": localized_datasets_name},
                        local_dir=localized_data_path,
                    )
                )

        return localized_datasets_files

    def get_files(
        self, checkout_filter: Optional[ProjectFileCheckout] = None
    ) -> List[ProjectFile]:
        if checkout_filter is None:
            return list(self._files.values())

        return [
            file for file in self._files.values() if file.checkout & checkout_filter
        ]

    def refresh_files(self) -> None:
        self._files = {}

        if self._cloud_files:
            for file_obj in self._cloud_files:
                self._files[file_obj["name"]] = ProjectFile(
                    file_obj, local_dir=self.local_dir
                )

        if self.local_dir:
            local_filenames = [
                f
                for f in [
                    str(f.relative_to(self.local_dir).as_posix())
                    for f in Path(self.local_dir).glob("**/*")
                    if f.is_file()
                ]
                if not f.startswith(".")
            ]

            for filename in local_filenames:
                if filename in self._files:
                    continue

                if filename.endswith((".gpkg-shm", ".gpkg-wal")):
                    continue

                if filename.endswith((".qgs~", ".qgz~")):
                    continue

                self._files[filename] = ProjectFile(
                    {"name": filename}, local_dir=self.local_dir
                )
