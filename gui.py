import sys
from threading import Thread
from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QTextCursor, QMessageBox
from gen import Ui_Form
from TestSuite import TestSuite

class MyForm(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.ts = None


    def _update_buttons(self, executing):
        self.ui.execute.setEnabled(not executing)
        self.ui.execute_all.setEnabled(not executing)
        self.ui.reload.setEnabled(not executing)
        self.ui.stop.setEnabled(executing)

    def handle_execute(self, all=False):
        self._update_buttons(True)
        if not all:
            litm = self.ui.testcases.currentItem()
            self.ts.execute(litm.text(), litm, self.ui.logs)
        else:
            for i in range(0, self.ui.testcases.count()):
                litm = self.ui.testcases.item(i)
                self.ts.execute(litm.text(), litm, self.ui.logs)
        self._update_buttons(False)

    def execute_event(self):
        try:
            Thread(target=self.handle_execute, args=()).start()
        except:
            print 'dupa'

    def execute_all_event(self):
        Thread(target=self.handle_execute, args=(True,)).start()

    def stop_event(self):
        pass

    def logs_event(self):
        c = self.ui.logs.textCursor()
        c.movePosition(QTextCursor.End)
        self.ui.logs.setTextCursor(c)

    def reload_event(self):
        try:
            for i in range(0, self.ui.testcases.count()):
                self.ui.testcases.takeItem(0)
            self.ts = TestSuite()
            for tcf in self.ts.tc_files:
                self.ui.testcases.addItem(unicode(tcf))
        except:
            QMessageBox.warning(self,
                            "Can't load testcases.",
                            "Can't load testcases. Make sure that you have testcases directory and testcases there.")


def start_gui():
    app = QtGui.QApplication(sys.argv)
    myapp = MyForm()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    start_gui()

# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

