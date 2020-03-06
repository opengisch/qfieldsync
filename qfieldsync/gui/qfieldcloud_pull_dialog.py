import os
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPushButton,
    QTreeWidgetItem,
    QHeaderView,
)
from qgis.PyQt.uic import loadUiType

from qfieldsync.utils.file_utils import get_project_in_folder
from qfieldsync.utils.qgis_utils import open_project
from qfieldsync.utils.qt_utils import make_folder_selector
from qfieldsync.utils.qfieldcloud_utils import QFieldCloudClient

DialogUi, _ = loadUiType(os.path.join(os.path.dirname(__file__), '../ui/qfieldcloud_pull_dialog.ui'))


class QFieldCloudPullDialog(QDialog, DialogUi):

    def __init__(self, iface, preferences, parent=None):
        """Constructor.
        :type qfield_preferences: qfieldsync.core.Preferences
        """
        super(QFieldCloudPullDialog, self).__init__(parent=parent)
        self.setupUi(self)
        self.iface = iface
        self.preferences = preferences

        self.push_btn = QPushButton(self.tr('Download'))
        self.push_btn.clicked.connect(self.start_download)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)

        self.push_btn = QPushButton(self.tr('Download and open'))
        self.push_btn.clicked.connect(self.start_download_and_open)
        self.button_box.addButton(self.push_btn, QDialogButtonBox.ActionRole)

        self.download_directory.setText(self.preferences.import_directory)
        self.download_directory_button.clicked.connect(make_folder_selector(self.download_directory))

        self.include_public_projects.stateChanged.connect(self.include_public_projects_changed)
        self.offline_editing_done = False
        self.qfieldcloud_client = QFieldCloudClient(self.preferences.qfieldcloud_base_url)
        self.qfieldcloud_client.login(
            self.preferences.qfieldcloud_username,
            self.preferences.qfieldcloud_password
        )

        self.get_project_list()

    def get_project_list(self):

        self.project_tree_widget.clear()

        project_list = self.qfieldcloud_client.list_user_projects()

        # Include public projects
        if self.include_public_projects.isChecked():
            public_projects = self.qfieldcloud_client.list_public_projects()

            project_list = list(project_list)
            project_list.extend(x for x in public_projects if x not in project_list)

        print(project_list)

        self.project_tree_widget.setColumnCount(2)
        self.project_tree_widget.setHeaderLabels(['Name', 'Description'])
        self.project_tree_widget.setSortingEnabled(True)

        self.project_tree_widget.header().setSectionResizeMode(0, QHeaderView.Stretch)

        for project in project_list:

            item = QTreeWidgetItem([project['owner'] + '/' + project['name'], project['description']])
            self.project_tree_widget.addTopLevelItem(item)

    def include_public_projects_changed(self):
        print("changed")
        self.get_project_list()

    def start_download_and_open(self):
        self.start_download(load_project=True)

    def start_download(self, load_project=False):

        # TODO: create the main project directory?
        self.progress_group.setEnabled(True)

        download_directory = self.download_directory.text()

        # TODO: only one selectedItem
        # TODO: check if at least one item is selected
        selectedItems = self.project_tree_widget.selectedItems()

        self.qfieldcloud_client.download_progress.connect(self.update_value)

        for item in selectedItems:

            # Get file list
            file_list = self.qfieldcloud_client.list_files(item.text(0))

            for i, file in enumerate(file_list):
                self.qfieldcloud_client.pull_file(
                    item.text(0),
                    file['name'],
                    download_directory,
                    file['size'],
                )
                self.update_total(i + 1, len(file_list))

        if load_project:
            # TODO: if the folder contains more than one qgs file there is an error
            # TODO: manage if no qgs file is present
            qgs_file = get_project_in_folder(download_directory)
            open_project(qgs_file)
            self.close()

    @pyqtSlot(int, int)
    def update_total(self, current, layer_count):
        self.totalProgressBar.setMaximum(layer_count)
        self.totalProgressBar.setValue(current)

    @pyqtSlot(int)
    def update_value(self, progress):
        self.layerProgressBar.setValue(progress)
