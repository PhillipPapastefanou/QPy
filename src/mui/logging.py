from PyQt5.QtCore import pyqtSlot, pyqtSignal, QThread, QObject
import sys
class WriteStream(object):
    def __init__(self,queue):
        self.queue = queue
    def write(self, text):
        self.queue.put(text)
    def flush(self):
        sys.stdout = sys.__stdout__

class LoggingReceiver(QObject):
    mysignal = pyqtSignal(str)
    def __init__(self,queue,*args,**kwargs):
        QObject.__init__(self,*args,**kwargs)
        self.queue = queue
    @pyqtSlot()
    def run(self):
        while True:
            text = self.queue.get()
            self.mysignal.emit(text)