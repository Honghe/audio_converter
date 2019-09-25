import logging
import os
import sys
import time
import traceback

# TODO, better solution to use local package.
PACKAGE_PARENT = '.'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

import ffmpeg
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import pyqtSlot, QRunnable, QThreadPool, QObject, pyqtSignal, QMutex
from PyQt5.QtWidgets import QFileDialog
from fbs_runtime.application_context.PyQt5 import ApplicationContext

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_QUIT = False


class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        `tuple` (exctype, value, traceback.format_exc() )

    result
        `object` data returned from processing, anything

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        try:
            result = self.fn(
                *self.args, **self.kwargs
            )
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()
        # https://github.com/mherrmann/fbs/issues/32
        uic.loadUi(appctxt.get_resource('main.ui'), self)
        # `findChild(,'open')`非必需，比如uic会自动在此自动生成`self.open`
        self.open_button = self.findChild(QtWidgets.QPushButton, 'open')
        self.convert_button = self.findChild(QtWidgets.QPushButton, 'convertButton')
        self.output_button = self.findChild(QtWidgets.QPushButton, 'output')
        self.output_dir_edit = self.findChild(QtWidgets.QLineEdit, 'output_dir')
        self.progress_bar = self.findChild(QtWidgets.QProgressBar, 'progressBar')
        self.list_widget = self.findChild(QtWidgets.QListWidget, 'listWidget')

        self.open_button.clicked.connect(self.open_button_pressed)
        self.convert_button.clicked.connect(self.convert_button_pressed)
        self.output_button.clicked.connect(self.output_button_pressed)

        self.directory = None
        self.entries = None
        self.output_dir = None
        self.mutex = QMutex()
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(os.cpu_count() - 1) # for not use all system cpu
        self.show()

    def convert(self, entry):
        in_filename = os.path.join(self.directory, entry)
        out_filename = os.path.join(self.output_dir, os.path.splitext(entry)[0] + '.mp3')
        # `run_async(quite=True)` will pipe subprocess stdout and stderr from ffmpeg-python code.
        # This will block subprocess If parent process not read the PIPE,
        # cause the PIPE bufsize is io.DEFAULT_BUFFER_SIZE by default.
        # so use `run_async()` now.
        # TODO Read stdout and stderr from PIPE for logs.
        process = (ffmpeg
                   .input(in_filename)
                   .output(out_filename, format='mp3')
                   .overwrite_output()
                   .run_async()
                   )
        while process.poll() is None:
            if _QUIT:
                process.terminate()
                process.wait()
            else:
                time.sleep(1)

    def thread_complete(self):
        self.mutex.lock()
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        self.mutex.unlock()
        if self.progress_bar.value() == self.progress_bar.maximum():
            self.convert_button.setDisabled(False)
            self.statusBar.showMessage('文件全部转换完成.')

    def convert_button_pressed(self):
        self.statusBar.showMessage('')
        if self.output_dir and self.directory and self.entries:
            self.progress_bar.setMaximum(len(self.entries))
            self.progress_bar.setValue(0)
            self.convert_button.setEnabled(False)
            self.statusBar.showMessage('文件转换中...')
            for entry in self.entries:
                worker = Worker(self.convert, entry)
                worker.signals.finished.connect(self.thread_complete)
                self.thread_pool.start(worker)

    def open_button_pressed(self):
        self.directory = str(QFileDialog.getExistingDirectory(self, "选择音频目录"))
        if self.directory:
            self.entries = sorted(
                [i for i in os.listdir(self.directory) if os.path.splitext(i)[-1][1:] in ['wma', 'mp3']])
            self.list_widget.clear()
            self.list_widget.addItems(self.entries)

    def output_button_pressed(self):
        self.output_dir = str(QFileDialog.getExistingDirectory(self, "选择输出目录"))
        if self.output_dir:
            self.output_dir_edit.setText(self.output_dir)

    def exit(self):
        self.thread_pool.clear()
        global _QUIT
        _QUIT = True
        time.sleep(1.5)
        self.thread_pool.waitForDone()


if __name__ == '__main__':
    appctxt = ApplicationContext()  # 1. Instantiate ApplicationContext
    window = Ui()
    exit_code = appctxt.app.exec_()  # 2. Invoke appctxt.app.exec_()
    logger.info('exit_code {}'.format(exit_code))
    window.exit()
    sys.exit(exit_code)
