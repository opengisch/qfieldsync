import os
import requests
from urllib.parse import urljoin
from pathlib import Path
from qgis.PyQt.QtCore import pyqtSignal, QObject


class QFieldCloudClient(QObject):
    download_progress = pyqtSignal(int)

    def __init__(self, base_url):
        super().__init__()
        self.__token = None
        self._base_url = base_url

    def login(self, username, password):

        url = urljoin(self._base_url, 'api/v1/auth/login/')
        data = {
            "username": username,
            "password": password,
        }

        try:
            response = requests.post(
                url,
                data=data,
            )

            # Raise exception if bad response status
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return False

        self.token = response.json()['token']
        return True

    # TODO decorator for token?
    def list_user_projects(self):

        url = urljoin(self._base_url, 'api/v1/projects/user/')
        headers = {'Authorization': 'token {}'.format(self.token)}

        try:
            response = requests.get(
                url,
                headers=headers,
            )

            # Raise exception if bad response status
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return None

        return response.json()

    def list_public_projects(self):

        url = urljoin(self._base_url, 'api/v1/projects/')
        headers = {'Authorization': 'token {}'.format(self.token)}

        try:
            response = requests.get(
                url,
                headers=headers,
            )

            # Raise exception if bad response status
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return None

        return response.json()

    def list_files(self, project):

        url = urljoin(self._base_url, 'api/v1/projects/{}/files/'.format(project))
        headers = {'Authorization': 'token {}'.format(self.token)}

        try:
            response = requests.get(
                url,
                headers=headers,
            )

            # Raise exception if bad response status
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return None

        return response.json()

    def pull_file(self, project, file_path, dest_path, file_size=0):

        url = urljoin(self._base_url, 'api/v1/projects/{}/{}/'.format(project, file_path))
        headers = {'Authorization': 'token {}'.format(self.token)}

        try:
            response = requests.get(
                url,
                headers=headers,
            )

            # Raise exception if bad response status
            response.raise_for_status()
        except requests.exceptions.RequestException:
            return None

        # Create destination directory
        Path(dest_path).mkdir(parents=True, exist_ok=True)

        dest_file = os.path.join(dest_path, file_path)
        chunk_size = 4096

        progress_step = 0

        if file_size:
            progress_step = 100 / (file_size / chunk_size)

        with open(dest_file, 'wb') as f:
            for i, chunk in enumerate(response.iter_content(chunk_size=chunk_size)):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    self.download_progress.emit((i + 1) * progress_step)

        self.download_progress.emit(100)
