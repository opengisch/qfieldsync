# -*- coding: utf-8 -*-
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


from pathlib import Path

from qgis.core import QgsProject

from qfieldsync.core.preferences import Preferences


class CloudProject:

    def __init__(self, project_data):
        """Constructor.
        """
        self._preferences = Preferences()
        self._data = project_data
        self._cloud_files = None
        self.local_dir = self._data.get('local_dir', self.local_dir)


    @staticmethod
    def get_instance_cloud_project():
        preferences = Preferences()
        project_dir = QgsProject.instance().homePath()

        for project_id, local_dir in preferences.value('qfieldCloudProjectLocalDirs').items():
            if local_dir != project_dir:
                continue
            
            cached_cloud_project = CloudProject.get_project_cache(project_id)

            if cached_cloud_project is not None:
                return cached_cloud_project

    
    @staticmethod
    def get_project_cache(project_id):
        preferences = Preferences()

        for project in preferences.value('qfieldCloudProjectsCache'):
            if project['id'] == project_id:
                return CloudProject({
                    **project,
                    'local_dir': preferences.value('qfieldCloudProjectLocalDirs').get(project_id)
                })

        return None


    def update_data(self, new_project_data):
        self._data = {**self._data, **new_project_data}
        self.local_dir = self._data.get('local_dir')


    @property
    def id(self):
        return self._data['id']


    @property
    def name(self):
        return self._data['name']


    @property
    def owner(self):
        return self._data['owner']


    @property
    def description(self):
        return self._data['description']


    @property
    def is_private(self):
        return self._data['private']


    @property
    def created_at(self):
        return self._data['created_at']


    @property
    def updated_at(self):
        return self._data['updated_at']


    @property
    def local_dir(self):
        return self._preferences.value('qfieldCloudProjectLocalDirs').get(self.id)


    @local_dir.setter
    def local_dir(self, local_dir):
        old_value = self._preferences.value('qfieldCloudProjectLocalDirs')

        new_value = {
            **old_value,
            self.id: local_dir,
        }

        self._preferences.set_value('qfieldCloudProjectLocalDirs', new_value)


    @property
    def cloud_files(self):
        return self._cloud_files


    @cloud_files.setter
    def cloud_files(self, files):
        self._cloud_files = files


    @property
    def cloud_only_files(self):
        return [f for f in self.cloud_files if f['name'] not in self.local_files]


    @property
    def is_current_qgis_project(self):
        project_home_path = QgsProject.instance().homePath()

        return len(project_home_path) > 0 and self.local_dir == QgsProject.instance().homePath()


    @property
    def local_files(self):
        assert self.local_dir

        return [f for f in [str(f.relative_to(self.local_dir)) for f in Path(self.local_dir).glob('**/*')] if not f.startswith('.qfieldsync')]


    @property
    def  local_only_files(self):
        assert self._cloud_files

        return [f for f in self.local_files if f not in self.cloud_files]




