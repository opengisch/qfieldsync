# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/synchronize_base.ui'
#
# Created by: PyQt5 UI code generator 5.7
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_QFieldSynchronizeBase(object):
    def setupUi(self, QFieldSynchronizeBase):
        QFieldSynchronizeBase.setObjectName("QFieldSynchronizeBase")
        QFieldSynchronizeBase.resize(413, 320)
        self.verticalLayout = QtWidgets.QVBoxLayout(QFieldSynchronizeBase)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(QFieldSynchronizeBase)
        self.label.setTextFormat(QtCore.Qt.RichText)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.qfieldDir = QtWidgets.QLineEdit(QFieldSynchronizeBase)
        self.qfieldDir.setObjectName("qfieldDir")
        self.horizontalLayout.addWidget(self.qfieldDir)
        self.qfieldDir_btn = QtWidgets.QPushButton(QFieldSynchronizeBase)
        self.qfieldDir_btn.setObjectName("qfieldDir_btn")
        self.horizontalLayout.addWidget(self.qfieldDir_btn)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.progress_group = QtWidgets.QGroupBox(QFieldSynchronizeBase)
        self.progress_group.setEnabled(False)
        self.progress_group.setObjectName("progress_group")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.progress_group)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_2 = QtWidgets.QLabel(self.progress_group)
        self.label_2.setObjectName("label_2")
        self.verticalLayout_2.addWidget(self.label_2)
        self.totalProgressBar = QtWidgets.QProgressBar(self.progress_group)
        self.totalProgressBar.setProperty("value", 0)
        self.totalProgressBar.setObjectName("totalProgressBar")
        self.verticalLayout_2.addWidget(self.totalProgressBar)
        self.label_3 = QtWidgets.QLabel(self.progress_group)
        self.label_3.setObjectName("label_3")
        self.verticalLayout_2.addWidget(self.label_3)
        self.layerProgressBar = QtWidgets.QProgressBar(self.progress_group)
        self.layerProgressBar.setProperty("value", 0)
        self.layerProgressBar.setObjectName("layerProgressBar")
        self.verticalLayout_2.addWidget(self.layerProgressBar)
        self.verticalLayout.addWidget(self.progress_group)
        self.button_box = QtWidgets.QDialogButtonBox(QFieldSynchronizeBase)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        self.button_box.setObjectName("button_box")
        self.verticalLayout.addWidget(self.button_box)

        self.retranslateUi(QFieldSynchronizeBase)
        self.button_box.accepted.connect(QFieldSynchronizeBase.accept)
        self.button_box.rejected.connect(QFieldSynchronizeBase.reject)
        QtCore.QMetaObject.connectSlotsByName(QFieldSynchronizeBase)

    def retranslateUi(self, QFieldSynchronizeBase):
        _translate = QtCore.QCoreApplication.translate
        QFieldSynchronizeBase.setWindowTitle(_translate("QFieldSynchronizeBase", "Syncronize remote project"))
        self.label.setText(_translate("QFieldSynchronizeBase", "<html><head/><body><p>Select the directory containing the</p><p>QField project file:</p></body></html>"))
        self.qfieldDir_btn.setText(_translate("QFieldSynchronizeBase", "Browse"))
        self.progress_group.setTitle(_translate("QFieldSynchronizeBase", "Progress"))
        self.label_2.setText(_translate("QFieldSynchronizeBase", "Total"))
        self.label_3.setText(_translate("QFieldSynchronizeBase", "Layer"))

