# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/settings.ui'
#
# Created by: PyQt5 UI code generator 5.7
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_QFieldRemoteOptionsBase(object):
    def setupUi(self, QFieldRemoteOptionsBase):
        QFieldRemoteOptionsBase.setObjectName("QFieldRemoteOptionsBase")
        QFieldRemoteOptionsBase.resize(285, 190)
        self.verticalLayout = QtWidgets.QVBoxLayout(QFieldRemoteOptionsBase)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_3 = QtWidgets.QLabel(QFieldRemoteOptionsBase)
        self.label_3.setObjectName("label_3")
        self.verticalLayout.addWidget(self.label_3)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.importDir = QtWidgets.QLineEdit(QFieldRemoteOptionsBase)
        self.importDir.setObjectName("importDir")
        self.horizontalLayout_2.addWidget(self.importDir)
        self.importDir_btn = QtWidgets.QPushButton(QFieldRemoteOptionsBase)
        self.importDir_btn.setObjectName("importDir_btn")
        self.horizontalLayout_2.addWidget(self.importDir_btn)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.label = QtWidgets.QLabel(QFieldRemoteOptionsBase)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.exportDir = QtWidgets.QLineEdit(QFieldRemoteOptionsBase)
        self.exportDir.setObjectName("exportDir")
        self.horizontalLayout.addWidget(self.exportDir)
        self.exportDir_btn = QtWidgets.QPushButton(QFieldRemoteOptionsBase)
        self.exportDir_btn.setObjectName("exportDir_btn")
        self.horizontalLayout.addWidget(self.exportDir_btn)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.button_box = QtWidgets.QDialogButtonBox(QFieldRemoteOptionsBase)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        self.button_box.setObjectName("button_box")
        self.verticalLayout.addWidget(self.button_box)

        self.retranslateUi(QFieldRemoteOptionsBase)
        self.button_box.accepted.connect(QFieldRemoteOptionsBase.accept)
        self.button_box.rejected.connect(QFieldRemoteOptionsBase.reject)
        QtCore.QMetaObject.connectSlotsByName(QFieldRemoteOptionsBase)

    def retranslateUi(self, QFieldRemoteOptionsBase):
        _translate = QtCore.QCoreApplication.translate
        QFieldRemoteOptionsBase.setWindowTitle(_translate("QFieldRemoteOptionsBase", "QFieldSync settings"))
        self.label_3.setText(_translate("QFieldRemoteOptionsBase", "Default Import Directory"))
        self.importDir_btn.setText(_translate("QFieldRemoteOptionsBase", "Browse"))
        self.label.setText(_translate("QFieldRemoteOptionsBase", "Default Export Directory"))
        self.exportDir_btn.setText(_translate("QFieldRemoteOptionsBase", "Browse"))

