# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/settings.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

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

class Ui_QFieldRemoteOptionsBase(object):
    def setupUi(self, QFieldRemoteOptionsBase):
        QFieldRemoteOptionsBase.setObjectName(_fromUtf8("QFieldRemoteOptionsBase"))
        QFieldRemoteOptionsBase.resize(285, 190)
        self.verticalLayout = QtGui.QVBoxLayout(QFieldRemoteOptionsBase)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.label_3 = QtGui.QLabel(QFieldRemoteOptionsBase)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.verticalLayout.addWidget(self.label_3)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.importDir = QtGui.QLineEdit(QFieldRemoteOptionsBase)
        self.importDir.setObjectName(_fromUtf8("importDir"))
        self.horizontalLayout_2.addWidget(self.importDir)
        self.importDir_btn = QtGui.QPushButton(QFieldRemoteOptionsBase)
        self.importDir_btn.setObjectName(_fromUtf8("importDir_btn"))
        self.horizontalLayout_2.addWidget(self.importDir_btn)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.label = QtGui.QLabel(QFieldRemoteOptionsBase)
        self.label.setObjectName(_fromUtf8("label"))
        self.verticalLayout.addWidget(self.label)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.exportDir = QtGui.QLineEdit(QFieldRemoteOptionsBase)
        self.exportDir.setObjectName(_fromUtf8("exportDir"))
        self.horizontalLayout.addWidget(self.exportDir)
        self.exportDir_btn = QtGui.QPushButton(QFieldRemoteOptionsBase)
        self.exportDir_btn.setObjectName(_fromUtf8("exportDir_btn"))
        self.horizontalLayout.addWidget(self.exportDir_btn)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.button_box = QtGui.QDialogButtonBox(QFieldRemoteOptionsBase)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtGui.QDialogButtonBox.Close)
        self.button_box.setObjectName(_fromUtf8("button_box"))
        self.verticalLayout.addWidget(self.button_box)

        self.retranslateUi(QFieldRemoteOptionsBase)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("accepted()")), QFieldRemoteOptionsBase.accept)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("rejected()")), QFieldRemoteOptionsBase.reject)
        QtCore.QMetaObject.connectSlotsByName(QFieldRemoteOptionsBase)

    def retranslateUi(self, QFieldRemoteOptionsBase):
        QFieldRemoteOptionsBase.setWindowTitle(_translate("QFieldRemoteOptionsBase", "QFieldSync settings", None))
        self.label_3.setText(_translate("QFieldRemoteOptionsBase", "Default Import Directory", None))
        self.importDir_btn.setText(_translate("QFieldRemoteOptionsBase", "Browse", None))
        self.label.setText(_translate("QFieldRemoteOptionsBase", "Default Export Directory", None))
        self.exportDir_btn.setText(_translate("QFieldRemoteOptionsBase", "Browse", None))

