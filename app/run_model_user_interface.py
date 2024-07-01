import os
import sys
sys.path.append("..")

from src.mui.app.ui_quincy import UI_Quincy
from src.mui.setup.ui_setup import UI_Setup

from src.mui.logging import WriteStream
from src.mui.logging import LoggingReceiver

from src.mui.setup.setup_model_interface import SetupParserInterface
from src.mui.ui_settings import Ui_Settings_Parser
from src.mui.ui_settings import Ui_Settings

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QApplication
from queue import Queue


class Model_Setup_Run_Interface:

    def run_setup(self, settings :Ui_Settings):
        self.settings = settings
        self.app = QApplication(sys.argv)
        self.setup_widget = UI_Setup(self.settings)

        queue = Queue()
        sys.stdout = WriteStream(queue)

        self.setup_thread = QThread()
        loggin_receiver = LoggingReceiver(queue)
        loggin_receiver.mysignal.connect(self.setup_widget.append_text)
        loggin_receiver.moveToThread(self.setup_thread)
        self.setup_thread.started.connect(loggin_receiver.run)
        self.setup_thread.start()
        self.setup_widget.show()
        self.finish_app_setup = self.app.exec_()

    def run_ui(self):
        self.app_ui = QApplication(sys.argv)
        self.ui_widget = UI_Quincy(self.settings)
        self.ui_widget.show()

        queue = Queue()
        sys.stdout = WriteStream(queue)

        thread = QThread()
        loggin_receiver = LoggingReceiver(queue)
        loggin_receiver.mysignal.connect(self.ui_widget.append_text)
        loggin_receiver.moveToThread(thread)
        thread.started.connect(loggin_receiver.run)
        thread.start()
        self.finish_app_ui = self.app_ui.exec_()

if __name__ == "__main__":
    input_parser = Ui_Settings_Parser()
    msri = Model_Setup_Run_Interface()

    # We have settings continue normally
    if os.path.exists(input_parser.filename):
        input_parser.open()
        settings = input_parser.settings

        # Modifiy setup
        if not settings.successfull_setup:
            msri.run_setup(input_parser.settings)

    # Generate setup
    else:
        msri.run_setup(input_parser.settings)

    # check if we have a successfull setup and start UI
    if input_parser.settings.successfull_setup:
        msri.settings = input_parser.settings
        msri.run_ui()

        sys.exit(msri.finish_app_ui)
    else:
        sys.exit(msri.finish_app_setup)

    sys.exit(msri.app.exec_())


