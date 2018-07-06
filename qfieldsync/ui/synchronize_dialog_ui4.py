# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/synchronize_dialog.ui'
#
# Created by: PyQt4 UI code generator 4.12.1
#
# WARNING! All changes made in this file will be lost!

from builtins import object
from qgis.PyQt import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_QFieldSynchronizeBase(object):
    def setupUi(self, QFieldSynchronizeBase):
        QFieldSynchronizeBase.setObjectName(_fromUtf8("QFieldSynchronizeBase"))
        QFieldSynchronizeBase.resize(413, 320)
        self.verticalLayout = QtGui.QVBoxLayout(QFieldSynchronizeBase)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.label = QtGui.QLabel(QFieldSynchronizeBase)
        self.label.setTextFormat(QtCore.Qt.RichText)
        self.label.setObjectName(_fromUtf8("label"))
        self.verticalLayout.addWidget(self.label)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.qfieldDir = QtGui.QLineEdit(QFieldSynchronizeBase)
        self.qfieldDir.setObjectName(_fromUtf8("qfieldDir"))
        self.horizontalLayout.addWidget(self.qfieldDir)
        self.qfieldDir_button = QtGui.QToolButton(QFieldSynchronizeBase)
        self.qfieldDir_button.setObjectName(_fromUtf8("qfieldDir_button"))
        self.horizontalLayout.addWidget(self.qfieldDir_button)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.progress_group = QtGui.QGroupBox(QFieldSynchronizeBase)
        self.progress_group.setEnabled(False)
        self.progress_group.setObjectName(_fromUtf8("progress_group"))
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.progress_group)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.label_2 = QtGui.QLabel(self.progress_group)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.verticalLayout_2.addWidget(self.label_2)
        self.totalProgressBar = QtGui.QProgressBar(self.progress_group)
        self.totalProgressBar.setProperty("value", 0)
        self.totalProgressBar.setObjectName(_fromUtf8("totalProgressBar"))
        self.verticalLayout_2.addWidget(self.totalProgressBar)
        self.label_3 = QtGui.QLabel(self.progress_group)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.verticalLayout_2.addWidget(self.label_3)
        self.layerProgressBar = QtGui.QProgressBar(self.progress_group)
        self.layerProgressBar.setProperty("value", 0)
        self.layerProgressBar.setObjectName(_fromUtf8("layerProgressBar"))
        self.verticalLayout_2.addWidget(self.layerProgressBar)
        self.verticalLayout.addWidget(self.progress_group)
        self.button_box = QtGui.QDialogButtonBox(QFieldSynchronizeBase)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtGui.QDialogButtonBox.Close)
        self.button_box.setObjectName(_fromUtf8("button_box"))
        self.verticalLayout.addWidget(self.button_box)

        self.retranslateUi(QFieldSynchronizeBase)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("accepted()")), QFieldSynchronizeBase.accept)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("rejected()")), QFieldSynchronizeBase.reject)
        QtCore.QMetaObject.connectSlotsByName(QFieldSynchronizeBase)

    def retranslateUi(self, QFieldSynchronizeBase):
        QFieldSynchronizeBase.setWindowTitle(_translate("QFieldSynchronizeBase", "Synchronize project", None))
        self.label.setText(_translate("QFieldSynchronizeBase", "<html><head/><body><p>Select the QField project folder</p></body></html>", None))
        self.qfieldDir_button.setText(_translate("QFieldSynchronizeBase", "...", None))
        self.progress_group.setTitle(_translate("QFieldSynchronizeBase", "Progress", None))
        self.label_2.setText(_translate("QFieldSynchronizeBase", "Total", None))
        self.label_3.setText(_translate("QFieldSynchronizeBase", "Layer", None))

