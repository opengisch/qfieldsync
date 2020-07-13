# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QFieldSync
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
import requests
from glob import glob
from pathlib import Path

from qfieldsync.core import project

from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal,
)


BASE_URL = 'https://dev.qfield.cloud/api/v1/'

# store the current token
token = None


def set_token(new_token):
    global token
    token = new_token


def get_error_reason(response):
    try:
        resp = response.json()
        return resp['detail']
    except:
        return 'Unknown reason'


def login(username, password):
    """Login to QFieldCloud and print the token"""

    url = BASE_URL + 'auth/login/'
    data = {
        "username": username,
        "password": password,
    }

    response = requests.post(
        url,
        data=data,
    )

    response.raise_for_status()
    resp = response.json()
    set_token(resp['token'])

    return resp


def logout():
    """Login to QFieldCloud and print the token"""

    url = BASE_URL + 'auth/logout/'

    headers = {'Authorization': 'token {}'.format(token)}
    response = requests.post(
        url,
        headers=headers,
    )

    response.raise_for_status()
    set_token(None)

    return response.json()


def create_project(name, owner, description, private=True):
    """Create a new QFieldCloud project"""

    url = BASE_URL + 'projects/'
    data = {
        "name": name,
        "owner": owner,
        "description": description,
        "private": private
    }

    headers = {'Authorization': 'token {}'.format(token)}

    response = requests.post(
        url,
        data=data,
        headers=headers,
    )

    print(data, response, headers, response.text)

    response.raise_for_status()

    return response.json()


class ProjectUploader(QObject):
    progress_uploaded = pyqtSignal(int, int, str)


    def __init__(self, project_id, local_dir, is_new_project=False):
        super(ProjectUploader, self).__init__(parent=None)

        self.project_id = project_id
        self.local_dir = local_dir
        self.is_new_project = is_new_project


    def upload(self):
        file_names = glob(os.path.join(self.local_dir, '**'), recursive=True)

        # upload the QGIS project file at the end
        file_names.sort(key=lambda s: Path(s).suffix in ('.qgs', '.qgz') )

        # do not upload the project file, if it is already there
        if not self.is_new_project:
            file_names = file_names[:-2]

        file_paths = [Path(f) for f in file_names if Path(f).is_file()]
        total_size = sum([p.stat().st_size for p in file_paths])
        total_transferred = 0

        for local_path in file_paths:
            remote_path = local_path.relative_to(self.local_dir)

            url = BASE_URL + 'files/' + self.project_id + '/' + str(remote_path) + '/'
            headers = {
                'Authorization': 'token {}'.format(token),
            }

            with open(local_path, 'rb')  as local_file:
                files = {'file': local_file}

                self.progress_uploaded.emit(total_transferred, total_size, str(local_path))

                response = requests.post(
                    url,  
                    headers=headers,
                    files=files,
                    stream=True
                )
                response.raise_for_status()

                total_transferred += local_path.stat().st_size

                if total_transferred == total_size:
                    self.progress_uploaded.emit(total_transferred, total_size, "Done!")

