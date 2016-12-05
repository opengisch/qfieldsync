# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/preferences_dialog.ui'
#
# Created by: PyQt5 UI code generator 5.7
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_QFieldPreferencesBase(object):
    def setupUi(self, QFieldPreferencesBase):
        QFieldPreferencesBase.setObjectName("QFieldPreferencesBase")
        QFieldPreferencesBase.resize(481, 299)
        self.verticalLayout = QtWidgets.QVBoxLayout(QFieldPreferencesBase)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_3 = QtWidgets.QLabel(QFieldPreferencesBase)
        self.label_3.setObjectName("label_3")
        self.verticalLayout.addWidget(self.label_3)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.import_directory = QtWidgets.QLineEdit(QFieldPreferencesBase)
        self.import_directory.setObjectName("import_directory")
        self.horizontalLayout_2.addWidget(self.import_directory)
        self.import_directory_button = QtWidgets.QToolButton(QFieldPreferencesBase)
        self.import_directory_button.setObjectName("import_directory_button")
        self.horizontalLayout_2.addWidget(self.import_directory_button)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.label = QtWidgets.QLabel(QFieldPreferencesBase)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.export_directory = QtWidgets.QLineEdit(QFieldPreferencesBase)
        self.export_directory.setObjectName("export_directory")
        self.horizontalLayout.addWidget(self.export_directory)
        self.export_directory_button = QtWidgets.QToolButton(QFieldPreferencesBase)
        self.export_directory_button.setObjectName("export_directory_button")
        self.horizontalLayout.addWidget(self.export_directory_button)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.label_2 = QtWidgets.QLabel(QFieldPreferencesBase)
        self.label_2.setObjectName("label_2")
        self.verticalLayout.addWidget(self.label_2)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.temporary_files_directory = QtWidgets.QLineEdit(QFieldPreferencesBase)
        self.temporary_files_directory.setObjectName("temporary_files_directory")
        self.horizontalLayout_3.addWidget(self.temporary_files_directory)
        self.temporary_files_directory_button = QtWidgets.QToolButton(QFieldPreferencesBase)
        self.temporary_files_directory_button.setObjectName("temporary_files_directory_button")
        self.horizontalLayout_3.addWidget(self.temporary_files_directory_button)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.button_box = QtWidgets.QDialogButtonBox(QFieldPreferencesBase)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.button_box.setObjectName("button_box")
        self.verticalLayout.addWidget(self.button_box)

        self.retranslateUi(QFieldPreferencesBase)
        self.button_box.accepted.connect(QFieldPreferencesBase.accept)
        self.button_box.rejected.connect(QFieldPreferencesBase.reject)
        QtCore.QMetaObject.connectSlotsByName(QFieldPreferencesBase)

    def retranslateUi(self, QFieldPreferencesBase):
        _translate = QtCore.QCoreApplication.translate
        QFieldPreferencesBase.setWindowTitle(_translate("QFieldPreferencesBase", "QFieldSync preferences"))
        self.label_3.setText(_translate("QFieldPreferencesBase", "Default import directory"))
        self.import_directory_button.setText(_translate("QFieldPreferencesBase", "..."))
        self.label.setText(_translate("QFieldPreferencesBase", "Default export directory"))
        self.export_directory_button.setText(_translate("QFieldPreferencesBase", "..."))
        self.label_2.setText(_translate("QFieldPreferencesBase", "Temporary files directory"))
        self.temporary_files_directory.setPlaceholderText(_translate("QFieldPreferencesBase", "[Leave empty to let QFieldSync choose one for you]"))
        self.temporary_files_directory_button.setText(_translate("QFieldPreferencesBase", "..."))

