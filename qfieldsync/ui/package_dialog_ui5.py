# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/package_dialog.ui'
#
# Created by: PyQt5 UI code generator 5.9.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_QFieldPackageDialogBase(object):
    def setupUi(self, QFieldPackageDialogBase):
        QFieldPackageDialogBase.setObjectName("QFieldPackageDialogBase")
        QFieldPackageDialogBase.resize(650, 638)
        self.gridLayout_2 = QtWidgets.QGridLayout(QFieldPackageDialogBase)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.informationStack = QtWidgets.QStackedWidget(QFieldPackageDialogBase)
        self.informationStack.setObjectName("informationStack")
        self.progressPage = QtWidgets.QWidget()
        self.progressPage.setObjectName("progressPage")
        self.gridLayout_3 = QtWidgets.QGridLayout(self.progressPage)
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.progress_group = QtWidgets.QGroupBox(self.progressPage)
        self.progress_group.setObjectName("progress_group")
        self.verticalLayout_6 = QtWidgets.QVBoxLayout(self.progress_group)
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.label_11 = QtWidgets.QLabel(self.progress_group)
        self.label_11.setObjectName("label_11")
        self.verticalLayout_6.addWidget(self.label_11)
        self.totalProgressBar = QtWidgets.QProgressBar(self.progress_group)
        self.totalProgressBar.setProperty("value", 0)
        self.totalProgressBar.setObjectName("totalProgressBar")
        self.verticalLayout_6.addWidget(self.totalProgressBar)
        self.statusLabel = QtWidgets.QLabel(self.progress_group)
        self.statusLabel.setObjectName("statusLabel")
        self.verticalLayout_6.addWidget(self.statusLabel)
        self.layerProgressBar = QtWidgets.QProgressBar(self.progress_group)
        self.layerProgressBar.setProperty("value", 0)
        self.layerProgressBar.setObjectName("layerProgressBar")
        self.verticalLayout_6.addWidget(self.layerProgressBar)
        self.gridLayout_3.addWidget(self.progress_group, 0, 0, 1, 1)
        self.informationStack.addWidget(self.progressPage)
        self.selectExtentPage = QtWidgets.QWidget()
        self.selectExtentPage.setObjectName("selectExtentPage")
        self.gridLayout_4 = QtWidgets.QGridLayout(self.selectExtentPage)
        self.gridLayout_4.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.groupBox_2 = QtWidgets.QGroupBox(self.selectExtentPage)
        self.groupBox_2.setObjectName("groupBox_2")
        self.gridLayout_5 = QtWidgets.QGridLayout(self.groupBox_2)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.widget = QtWidgets.QWidget(self.groupBox_2)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.widget.sizePolicy().hasHeightForWidth())
        self.widget.setSizePolicy(sizePolicy)
        self.widget.setObjectName("widget")
        self.gridLayout_6 = QtWidgets.QGridLayout(self.widget)
        self.gridLayout_6.setObjectName("gridLayout_6")
        self.yMaxLabel = QtWidgets.QLineEdit(self.widget)
        self.yMaxLabel.setEnabled(False)
        self.yMaxLabel.setObjectName("yMaxLabel")
        self.gridLayout_6.addWidget(self.yMaxLabel, 3, 2, 1, 1)
        self.yMinLabel = QtWidgets.QLineEdit(self.widget)
        self.yMinLabel.setEnabled(False)
        self.yMinLabel.setObjectName("yMinLabel")
        self.gridLayout_6.addWidget(self.yMinLabel, 1, 2, 1, 1)
        self.xMinLabel = QtWidgets.QLineEdit(self.widget)
        self.xMinLabel.setEnabled(False)
        self.xMinLabel.setObjectName("xMinLabel")
        self.gridLayout_6.addWidget(self.xMinLabel, 2, 1, 1, 1)
        self.xMaxLabel = QtWidgets.QLineEdit(self.widget)
        self.xMaxLabel.setEnabled(False)
        self.xMaxLabel.setObjectName("xMaxLabel")
        self.gridLayout_6.addWidget(self.xMaxLabel, 2, 3, 1, 1)
        self.widget_2 = QtWidgets.QWidget(self.widget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.widget_2.sizePolicy().hasHeightForWidth())
        self.widget_2.setSizePolicy(sizePolicy)
        self.widget_2.setStyleSheet("border: 1px solid #e67e22")
        self.widget_2.setObjectName("widget_2")
        self.gridLayout_7 = QtWidgets.QGridLayout(self.widget_2)
        self.gridLayout_7.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_7.setObjectName("gridLayout_7")
        self.label_3 = QtWidgets.QLabel(self.widget_2)
        self.label_3.setAlignment(QtCore.Qt.AlignCenter)
        self.label_3.setWordWrap(True)
        self.label_3.setObjectName("label_3")
        self.gridLayout_7.addWidget(self.label_3, 0, 0, 1, 1)
        self.gridLayout_6.addWidget(self.widget_2, 2, 2, 1, 1)
        self.gridLayout_5.addWidget(self.widget, 0, 0, 1, 1)
        self.gridLayout_4.addWidget(self.groupBox_2, 0, 0, 1, 1)
        self.informationStack.addWidget(self.selectExtentPage)
        self.gridLayout_2.addWidget(self.informationStack, 2, 0, 1, 2)
        self.groupBox = QtWidgets.QGroupBox(QFieldPackageDialogBase)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout = QtWidgets.QGridLayout(self.groupBox)
        self.gridLayout.setObjectName("gridLayout")
        self.manualDir = QtWidgets.QLineEdit(self.groupBox)
        self.manualDir.setObjectName("manualDir")
        self.gridLayout.addWidget(self.manualDir, 0, 0, 1, 1)
        self.manualDir_btn = QtWidgets.QPushButton(self.groupBox)
        self.manualDir_btn.setObjectName("manualDir_btn")
        self.gridLayout.addWidget(self.manualDir_btn, 0, 1, 1, 1)
        self.gridLayout_2.addWidget(self.groupBox, 1, 0, 1, 2)
        self.label_2 = QtWidgets.QLabel(QFieldPackageDialogBase)
        self.label_2.setTextFormat(QtCore.Qt.RichText)
        self.label_2.setObjectName("label_2")
        self.gridLayout_2.addWidget(self.label_2, 0, 0, 1, 1)
        self.project_lbl = QtWidgets.QLabel(QFieldPackageDialogBase)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.project_lbl.sizePolicy().hasHeightForWidth())
        self.project_lbl.setSizePolicy(sizePolicy)
        self.project_lbl.setText("")
        self.project_lbl.setObjectName("project_lbl")
        self.gridLayout_2.addWidget(self.project_lbl, 0, 1, 1, 1)
        self.button_box = QtWidgets.QDialogButtonBox(QFieldPackageDialogBase)
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        self.button_box.setObjectName("button_box")
        self.gridLayout_2.addWidget(self.button_box, 4, 0, 1, 2)
        self.infoGroupBox = QtWidgets.QGroupBox(QFieldPackageDialogBase)
        self.infoGroupBox.setObjectName("infoGroupBox")
        self.gridLayout_8 = QtWidgets.QGridLayout(self.infoGroupBox)
        self.gridLayout_8.setObjectName("gridLayout_8")
        self.infoLabel = QtWidgets.QLabel(self.infoGroupBox)
        self.infoLabel.setObjectName("infoLabel")
        self.gridLayout_8.addWidget(self.infoLabel, 0, 0, 1, 1)
        self.gridLayout_2.addWidget(self.infoGroupBox, 3, 0, 1, 2)

        self.retranslateUi(QFieldPackageDialogBase)
        self.informationStack.setCurrentIndex(1)
        self.button_box.accepted.connect(QFieldPackageDialogBase.accept)
        self.button_box.rejected.connect(QFieldPackageDialogBase.reject)
        QtCore.QMetaObject.connectSlotsByName(QFieldPackageDialogBase)

    def retranslateUi(self, QFieldPackageDialogBase):
        _translate = QtCore.QCoreApplication.translate
        QFieldPackageDialogBase.setWindowTitle(_translate("QFieldPackageDialogBase", "Package project for QField"))
        self.progress_group.setTitle(_translate("QFieldPackageDialogBase", "Progress"))
        self.label_11.setText(_translate("QFieldPackageDialogBase", "Total"))
        self.statusLabel.setText(_translate("QFieldPackageDialogBase", "Layer"))
        self.groupBox_2.setTitle(_translate("QFieldPackageDialogBase", "Select extent"))
        self.label_3.setText(_translate("QFieldPackageDialogBase", "<html><head/><body><p>The main map canvas<br/>can be panned and<br/>zoomed as usual<br/>while this window is<br/>open.<br/>Try it!</p></body></html>"))
        self.groupBox.setTitle(_translate("QFieldPackageDialogBase", "Export Directory"))
        self.manualDir_btn.setText(_translate("QFieldPackageDialogBase", "..."))
        self.label_2.setText(_translate("QFieldPackageDialogBase", "<html><head/><body><p><span style=\" font-weight:600;\">Project:</span></p></body></html>"))
        self.infoGroupBox.setTitle(_translate("QFieldPackageDialogBase", "Information"))
        self.infoLabel.setText(_translate("QFieldPackageDialogBase", "Some layers in this project have not yet been configured. <a href=\"configuration\">Configure project now</a>."))

