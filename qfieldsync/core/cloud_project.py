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


from qfieldsync.core.preferences import Preferences


class CloudProject:

    def __init__(self, project_data):
        """Constructor.
        """
        self._preferences = Preferences()
        self._data = project_data
        self._cloud_files = None
        self.local_dir = self._data.get('local_dir', self.local_dir)


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
        return self._preferences.value('qfieldCloudProjects').get(self.id)


    @local_dir.setter
    def local_dir(self, local_dir):
        old_value = self._preferences.value('qfieldCloudProjects')

        new_value = {
            **old_value,
            self.id: local_dir,
        }

        self._preferences.set_value('qfieldCloudProjects', new_value)


    @property
    def cloud_files(self):
        return self._cloud_files


    @cloud_files.setter
    def cloud_files(self, files):
        self._cloud_files = files
