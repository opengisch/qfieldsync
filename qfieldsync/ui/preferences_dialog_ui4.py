# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/preferences_dialog.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
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

class Ui_QFieldPreferencesBase(object):
    def setupUi(self, QFieldPreferencesBase):
        QFieldPreferencesBase.setObjectName(_fromUtf8("QFieldPreferencesBase"))
        QFieldPreferencesBase.resize(285, 190)
        self.verticalLayout = QtGui.QVBoxLayout(QFieldPreferencesBase)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.label_3 = QtGui.QLabel(QFieldPreferencesBase)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.verticalLayout.addWidget(self.label_3)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        self.import_directory = QtGui.QLineEdit(QFieldPreferencesBase)
        self.import_directory.setObjectName(_fromUtf8("import_directory"))
        self.horizontalLayout_2.addWidget(self.import_directory)
        self.import_directory_button = QtGui.QToolButton(QFieldPreferencesBase)
        self.import_directory_button.setObjectName(_fromUtf8("import_directory_button"))
        self.horizontalLayout_2.addWidget(self.import_directory_button)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.label = QtGui.QLabel(QFieldPreferencesBase)
        self.label.setObjectName(_fromUtf8("label"))
        self.verticalLayout.addWidget(self.label)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        self.export_directory = QtGui.QLineEdit(QFieldPreferencesBase)
        self.export_directory.setObjectName(_fromUtf8("export_directory"))
        self.horizontalLayout.addWidget(self.export_directory)
        self.export_directory_button = QtGui.QToolButton(QFieldPreferencesBase)
        self.export_directory_button.setObjectName(_fromUtf8("export_directory_button"))
        self.horizontalLayout.addWidget(self.export_directory_button)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.button_box = QtGui.QDialogButtonBox(QFieldPreferencesBase)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.button_box.setObjectName(_fromUtf8("button_box"))
        self.verticalLayout.addWidget(self.button_box)

        self.retranslateUi(QFieldPreferencesBase)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("accepted()")), QFieldPreferencesBase.accept)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("rejected()")), QFieldPreferencesBase.reject)
        QtCore.QMetaObject.connectSlotsByName(QFieldPreferencesBase)

    def retranslateUi(self, QFieldPreferencesBase):
        QFieldPreferencesBase.setWindowTitle(_translate("QFieldPreferencesBase", "QFieldSync preferences", None))
        self.label_3.setText(_translate("QFieldPreferencesBase", "Default Import Directory", None))
        self.import_directory_button.setText(_translate("QFieldPreferencesBase", "...", None))
        self.label.setText(_translate("QFieldPreferencesBase", "Default Export Directory", None))
        self.export_directory_button.setText(_translate("QFieldPreferencesBase", "...", None))

