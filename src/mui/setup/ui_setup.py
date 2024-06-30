import os.path

from src.mui.designs.setup_design import Ui_MainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject
from src.mui.ui_settings import Ui_Settings
from src.mui.ui_settings import Ui_Settings_Parser
from PyQt5.QtWidgets import QApplication
from queue import Queue
from src.mui.setup.setup_parser import SetupParser
from src.mui.setup.setup_parser import BuildingThread
from datetime import datetime


class UI_Setup(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, ui_settings: Ui_Settings):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.pushButton_Build.clicked.connect(self.build)
        self.ui.pushButton_Save.clicked.connect(self.save)

        self.pix_checked = QtGui.QPixmap(os.path.join("..", "res", "check.png"))
        self.pix_removed= QtGui.QPixmap(os.path.join("..", "res", "remove.png"))

        self.pix_checked =  self.pix_checked.scaled(22, 22)
        self.pix_removed =  self.pix_removed.scaled(20, 20)

        if os.path.exists(ui_settings.quincy_binary_path):
            self.ui.label_quincy_binary.setPixmap(self.pix_checked)
        else:
            self.ui.label_quincy_binary.setPixmap(self.pix_removed)
        if os.path.exists(ui_settings.quincy_binary_path):
            self.ui.label_quincy_directory.setPixmap(self.pix_checked)
        else:
            self.ui.label_quincy_directory.setPixmap(self.pix_removed)
        if os.path.exists(ui_settings.forcing_generator_binary_path):
            self.ui.label_weather_gen_binary.setPixmap(self.pix_checked)
        else:
            self.ui.label_weather_gen_binary.setPixmap(self.pix_removed)
        if os.path.exists(ui_settings.root_qpy_directory):
            self.ui.label_qpy_directory.setPixmap(self.pix_checked)
        else:
            self.ui.label_qpy_directory.setPixmap(self.pix_removed)

        self.new_line_logger = True
        self.found_quincy_binary = False
        self.found_generator_binary = False

        self.ui_settings = ui_settings
        self.setup_parser = SetupParser(ui_settings)


        if not self.ui_settings.successfull_setup:
            self.setup_parser.look_for_compilers()

        self.setup_parser.sig_add_text.connect(self.append_text)
        self.setup_parser.sig_qpy_path.connect(self.set_qpy_path)
        self.setup_parser.sig_generator_bin.connect(self.set_weather_generator_binary_path)
        self.setup_parser.sig_quincy_bin.connect(self.set_quincy_binary_path)
        self.setup_parser.sig_quincy_dir.connect(self.set_quincy_root_path)
        self.ui.lineEdit_quincy_directory.textChanged.connect(self.update_quincy_root_path_set)

        self.ui.lineEdit_path_cmake.setText(self.ui_settings.cmake_binary_path)
        self.ui.lineEdit_cmake_version.setText(self.setup_parser.cmake_version)
        self.ui.label_cmake_found.setPixmap(self.pix_checked)  if self.setup_parser.cmake_version else self.ui.label_cmake_found.setPixmap(self.pix_removed)
        self.ui.lineEdit_path_cpp.setText(self.setup_parser.cpp_compiler_path)
        self.ui.lineEdit_cpp_version.setText(self.setup_parser.cpp_compiler_version)
        self.ui.label_cpp_found.setPixmap(self.pix_checked)  if self.setup_parser.cpp_found else self.ui.label_cpp_found.setPixmap(self.pix_removed)
        self.ui.lineEdit_path_fortran.setText(self.setup_parser.fortran_compiler_path)
        self.ui.lineEdit_fortran_version.setText(self.setup_parser.fortran_compiler_version)
        self.ui.label_fortran_found.setPixmap(self.pix_checked)  if self.setup_parser.fortran_found else self.ui.label_fortran_found.setPixmap(self.pix_removed)


        self.ui.lineEdit_weather_gen_binary.setText(self.ui_settings.forcing_generator_binary_path)
        self.ui.lineEdit_QPy_directory.setText(self.ui_settings.root_qpy_directory)

    def update_quincy_root_path_set(self):
        self.ui_settings.quincy_root_path = self.ui.lineEdit_quincy_directory.text()

    def set_qpy_path(self, text):
        self.ui.lineEdit_QPy_directory.setText(text)
        self.ui.label_qpy_directory.setPixmap(self.pix_checked)

    def set_weather_generator_binary_path(self, text):
        self.ui.lineEdit_weather_gen_binary.setText(text)
        self.ui.label_weather_gen_binary.setPixmap(self.pix_checked)
        self.found_generator_binary = True
    def set_quincy_root_path(self, text):
        self.ui.lineEdit_quincy_directory.setText(text)
        self.ui.label_quincy_directory.setPixmap(self.pix_checked)
    def set_quincy_binary_path(self, text):
        self.ui.lineEdit_quincy_binary.setText(text)
        self.ui.label_quincy_binary.setPixmap(self.pix_checked)
        self.found_quincy_binary = True

    @pyqtSlot(str)
    def append_text(self,text):
        self.ui.textBrowser_Logging.moveCursor(QtGui.QTextCursor.End)

        if self.new_line_logger:
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            text_with_date = f"{date_str} {text}"
        else:
            text_with_date = f"{text}"

        if '\n' in text:
            self.new_line_logger = True
        else:
            self.new_line_logger = False

        self.ui.textBrowser_Logging.insertPlainText( text_with_date )


    def build(self):

        self.thread = BuildingThread(self.setup_parser)
        self.thread.start()

    def save(self):
        parser = Ui_Settings_Parser()
        if self.found_generator_binary & self.found_quincy_binary:
            self.ui_settings.successfull_setup = True

        parser.settings = self.ui_settings
        parser.save()


