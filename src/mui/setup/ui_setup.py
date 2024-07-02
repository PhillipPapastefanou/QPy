import os.path

from src.mui.designs.setup_design import Ui_MainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject
from src.mui.ui_settings import Ui_Settings
from src.mui.ui_settings import Ui_Settings_Parser
from PyQt5.QtWidgets import QApplication
from queue import Queue
from src.mui.setup.setup_model_interface import SetupParserInterface
from src.mui.setup.setup_model_interface import BuildingThread
from datetime import datetime
from functools import partial

class UI_Setup(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, ui_settings: Ui_Settings):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui_settings = ui_settings


        self.pix_checked = QtGui.QPixmap(os.path.join("..", "res", "check.png"))
        self.pix_removed= QtGui.QPixmap(os.path.join("..", "res", "remove.png"))

        self.pix_checked =  self.pix_checked.scaled(20, 20)
        self.pix_removed =  self.pix_removed.scaled(20, 20)

        self.setup_interface = SetupParserInterface(ui_settings)


        self.new_line_logger = True


        if not self.ui_settings.successfull_setup:
            self.setup_interface.look_for_compilers()

        self.setup_interface_parser = self.setup_interface.parser

        self.set_lib_version_and_image(self.ui.label_make_found, self.ui.lineEdit_path_make, self.ui.lineEdit_make_version, self.setup_interface_parser.lib_make)
        self.set_lib_version_and_image(self.ui.label_cmake_found, self.ui.lineEdit_path_cmake, self.ui.lineEdit_cmake_version, self.setup_interface_parser.lib_cmake)
        self.set_lib_version_and_image(self.ui.label_cpp_found, self.ui.lineEdit_path_cpp, self.ui.lineEdit_cpp_version, self.setup_interface_parser.lib_cpp)
        self.set_lib_version_and_image(self.ui.label_fortran_found, self.ui.lineEdit_path_fortran, self.ui.lineEdit_fortran_version, self.setup_interface_parser.lib_fortran)
        self.set_lib_version_and_image(self.ui.label_pythyon_found, self.ui.lineEdit_path_python, self.ui.lineEdit_python_version, self.setup_interface_parser.lib_python)

        self.ui.pushButton_Build.clicked.connect(self.build)
        self.ui.pushButton_Save.clicked.connect(self.save)
        self.setup_interface.sig_add_text.connect(self.append_text)
        self.ui.lineEdit_quincy_directory.textChanged.connect(self.update_quincy_root_path_set)
        self.ui.lineEdit_forcing_directory.textChanged.connect(self.update_forcing_root_path_set)

        self.setup_interface.sig_qpy_path.connect(
            lambda found, path,
                    label = self.ui.label_qpy_directory, lineEdit = self.ui.lineEdit_QPy_directory:self.set_paths_and_bins(label, lineEdit, found, path))

        self.setup_interface.sig_forcing_path.connect(
            lambda found, path,
                    label = self.ui.label_forcing_directory, lineEdit = self.ui.lineEdit_forcing_directory:self.set_paths_and_bins(label, lineEdit, found, path))

        self.setup_interface.sig_quincy_path.connect(
            lambda found, path,
                    label = self.ui.label_quincy_directory, lineEdit = self.ui.lineEdit_quincy_directory:self.set_paths_and_bins(label, lineEdit, found, path))

        self.setup_interface.sig_generator_bin.connect(
            lambda found, path,
                    label = self.ui.label_weather_gen_binary, lineEdit = self.ui.lineEdit_weather_gen_binary:self.set_paths_and_bins(label, lineEdit, found, path))

        self.setup_interface.sig_quincy_bin.connect(
            lambda found, path,
                    label = self.ui.label_quincy_binary, lineEdit = self.ui.lineEdit_quincy_binary:self.set_paths_and_bins(label, lineEdit, found, path))


        self.setup_interface_parser.path_QPy_directory = self.ui_settings.directory_QPy
        self.setup_interface_parser.path_quincy_directory = self.ui_settings.directory_quincy
        self.setup_interface_parser.path_forcing_directory = self.ui_settings.directory_forcing
        self.setup_interface_parser.lib_quincy.path = self.ui_settings.binary_quincy
        self.setup_interface_parser.lib_weather_gen.path = self.ui_settings.binary_weather_generator


        self.setup_interface.parser.check_directory_QPy()
        self.setup_interface.parser.check_directory_forcing()
        self.setup_interface.parser.check_directory_quincy()
        self.setup_interface.parser.check_weather_generator_binary()
        self.setup_interface.parser.check_quincy_binary()

        self.set_paths_and_bins(self.ui.label_qpy_directory, self.ui.lineEdit_QPy_directory,
                                self.setup_interface_parser.found_QPy_directory, self.setup_interface_parser.path_QPy_directory)
        self.set_paths_and_bins(self.ui.label_forcing_directory, self.ui.lineEdit_forcing_directory,
                                self.setup_interface_parser.found_forcing_directory, self.setup_interface_parser.path_forcing_directory)
        self.set_paths_and_bins(self.ui.label_quincy_directory, self.ui.lineEdit_quincy_directory,
                                self.setup_interface_parser.found_quincy_directory, self.setup_interface_parser.path_quincy_directory)
        self.set_paths_and_bins(self.ui.label_weather_gen_binary, self.ui.lineEdit_weather_gen_binary,
                                self.setup_interface_parser.lib_weather_gen.found, self.setup_interface_parser.lib_weather_gen.path)
        self.set_paths_and_bins(self.ui.label_quincy_binary, self.ui.lineEdit_quincy_binary,
                                self.setup_interface_parser.lib_quincy.found, self.setup_interface_parser.lib_quincy.path)

        #self.setup_interface.build()


        # self.ui.lineEdit_path_cmake.setText(self.ui_settings.cmake_binary_path)
        # self.ui.lineEdit_cmake_version.setText(self.setup_parser.cmake_version)
        # self.ui.label_cmake_found.setPixmap(self.pix_checked)  if self.setup_parser.cmake_version else self.ui.label_cmake_found.setPixmap(self.pix_removed)
        # self.ui.lineEdit_path_cpp.setText(self.setup_parser.cpp_compiler_path)
        # self.ui.lineEdit_cpp_version.setText(self.setup_parser.cpp_compiler_version)
        # self.ui.label_cpp_found.setPixmap(self.pix_checked)  if self.setup_parser.cpp_found else self.ui.label_cpp_found.setPixmap(self.pix_removed)
        # self.ui.lineEdit_path_fortran.setText(self.setup_parser.fortran_compiler_path)
        # self.ui.lineEdit_fortran_version.setText(self.setup_parser.fortran_compiler_version)
        # self.ui.label_fortran_found.setPixmap(self.pix_checked)  if self.setup_parser.fortran_found else self.ui.label_fortran_found.setPixmap(self.pix_removed)
        #
        #
        # self.ui.lineEdit_weather_gen_binary.setText(self.ui_settings.forcing_generator_binary_path)
        # self.ui.lineEdit_QPy_directory.setText(self.ui_settings.root_qpy_directory)
    def set_lib_version_and_image(self, label, line_edit_path, line_edit_version, lib):
        if lib.found:
            line_edit_path.setText(lib.path)
            line_edit_version.setText(lib.version)
            label.setPixmap(self.pix_checked)
        else:
            label.setPixmap(self.pix_removed)
            line_edit_version.setText("")


    def update_quincy_root_path_set(self):
        self.setup_interface_parser.path_quincy_directory = self.ui.lineEdit_quincy_directory.text()
        self.setup_interface_parser.check_directory_quincy()
        self.set_paths_and_bins(self.ui.label_quincy_directory, self.ui.lineEdit_quincy_directory,
                                self.setup_interface_parser.found_quincy_directory, self.setup_interface_parser.path_quincy_directory)

    def update_forcing_root_path_set(self):
        self.setup_interface_parser.path_forcing_directory = self.ui.lineEdit_forcing_directory.text()
        self.setup_interface_parser.check_directory_forcing()
        self.set_paths_and_bins(self.ui.label_forcing_directory, self.ui.lineEdit_forcing_directory,
                                self.setup_interface_parser.found_forcing_directory, self.setup_interface_parser.path_forcing_directory)


    def set_paths_and_bins(self, label, lineEdit, found, path):
        if found:
            lineEdit.setText(path)
            label.setPixmap(self.pix_checked)
        else:
            label.setPixmap(self.pix_removed)

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

        self.thread = BuildingThread(self.setup_interface)
        self.thread.start()

    def save(self):
        settings_parser = Ui_Settings_Parser()

        setup_parser = self.setup_interface_parser

        self.ui_settings.directory_QPy = setup_parser.path_QPy_directory
        self.ui_settings.directory_quincy = setup_parser.path_quincy_directory
        self.ui_settings.directory_forcing = setup_parser.path_forcing_directory

        self.ui_settings.binary_weather_generator = setup_parser.lib_weather_gen.path
        self.ui_settings.binary_quincy = setup_parser.lib_quincy.path

        self.ui_settings.quincy_lctlib_path = setup_parser.quincy_lctlib_path
        self.ui_settings.quincy_namelist_path = setup_parser.quincy_namelist_path

        self.ui_settings.successfull_setup = setup_parser.successfull_setup

        settings_parser.settings = self.ui_settings
        settings_parser.save()


