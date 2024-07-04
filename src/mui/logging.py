from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject
import sys
from enum import Enum



class MessageType(Enum):
    ERROR = 0
    WARN = 1
    SUCCESS = 2
    INFO = 3
class MessageFormat(str, Enum):
    ERROR = '<span style="color:red;">{}</span>'
    WARN = '<span style="color:orange;">{}</span>'
    SUCCESS = '<span style="color:green;">{}</span>'
    INFO = '<span style="color:black;">{}</span>'

class WriteStream(object):
    def __init__(self,queue):
        self.queue = queue
    def write(self, text):
        self.queue.put(text)
    def flush(self):
        sys.stdout = sys.__stdout__

class LoggingReceiver(QObject):
    sig_log = pyqtSignal(str, int)
    def __init__(self,queue,*args,**kwargs):
        QObject.__init__(self,*args,**kwargs)
        self.queue = queue
    @pyqtSlot()
    def run(self):
        while True:
            result = self.queue.get()

            if type(result) == tuple:
                text, int = result
                self.sig_log.emit(text, int)
            else:
                self.sig_log.emit(result, MessageType.INFO.value)
