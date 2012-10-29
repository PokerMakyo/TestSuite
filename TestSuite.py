import os
import sys
import time
import xmlrpclib
import socket

from gen import Ui_Form
from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QTextCursor
from PyQt4.QtCore import SIGNAL, QObject, QString

from itertools import izip

from parsers.txtparser import TxtParser
from parsers.paparser import PaParser

class MyForm(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.ui.testcases.setSortingEnabled(True)
        self.ts = None

        self.aborted = False

    def _update_buttons(self, executing):
        self.ui.execute.setEnabled(not executing)
        self.ui.execute_all.setEnabled(not executing)
        self.ui.reload.setEnabled(not executing)
        self.ui.stop.setEnabled(executing)

    def add_log(self, message):
        self.ui.logs.append(message)

    def network_error(self):
        QtGui.QMessageBox.warning(None, QString(sys.argv[0]), QString('Can\'t connect to ManualMode. Check if ManualMode-XMLRPC is running.'))
        self.stop_event()

    def handle_execute(self, all=False):
        class Testing(QtCore.QThread):
            def __init__(self, form, all):
                QtCore.QThread.__init__(self)
                self.form = form
                self.all = all

            def run(self):
                litm = self.form.ui.testcases.currentItem()

                if litm or all:
                    self.form._update_buttons(True)
                    self.form.aborted = False
                    if not self.all:
                        self.form.ts.execute(litm.text())
                    else:
                        for i in range(0, self.form.ui.testcases.count()):
                            if self.form.aborted:
                                break
                            litm = self.form.ui.testcases.item(i)
                            self.form.ts.execute(litm.text())
                    self.form._update_buttons(False)

        self.testing = Testing(self, all)
        self.testing.start()

    def execute_event(self):
        self.handle_execute()

    def execute_all_event(self):
        self.handle_execute(all=True)

    def stop_event(self):
        self.aborted = True
        self.ts.stop()
        self._update_buttons(False)

    def logs_event(self):
        c = self.ui.logs.textCursor()
        c.movePosition(QTextCursor.End)
        self.ui.logs.setTextCursor(c)

    def reload_event(self):
        if self.ui.directory.displayText():
            for i in range(0, self.ui.testcases.count()):
                self.ui.testcases.takeItem(0)

            self.ts = TestSuite(str(self.ui.directory.displayText()), self)
            for tcf in self.ts.tc_files:
                self.ui.testcases.addItem(unicode(tcf))

    def add_log(self, message):
        self.ui.logs.append(message)

    def get_directory_event(self):
        self.ui.directory.setText(QtGui.QFileDialog.getExistingDirectory())
        self.reload_event()

class TestCase(QObject):
    def __init__(self, tcfile, form):
        """Initialization of TestCase object.
        """
        QObject.__init__(self)

        self.status = 'not started'

        self.aborted = False
        self.form = form
        self.bround = None
        self.tcfile = tcfile

        self.connect(self, SIGNAL('add_log'), form.add_log, QtCore.Qt.QueuedConnection)

        if tcfile[-3:] == '.pa':
            self._parse_pa(tcfile)
        else:
            self._parse_txt(tcfile)

        self._dump_history()

        self.players = []
        for a in self.parser.pf_actions:
            if a[0] not in self.players:
                self.players.append(a[0])
            else:
                break

        # we want to have Hero always on chair == 0
        for i in range(0, len(self.players) - self.players.index(self.parser.hero)):
            p = self.players.pop()
            self.players.insert(0, p)

        SB = self.parser.pf_actions[0][0]

        if len(self.players) > 2:
            # dealer is sitting before SB
            self.dealer = self.players[self.players.index(SB) - 1]
        else:
            # delaer is SB
            self.dealer = SB

    def add_log(self, message):
        """Send log message to GUI.
        """
        self.emit(SIGNAL('add_log'), message)

    def _dump_history(self):
        """Save history in tshistory file.
        """
        fd = open('tshistory.py', 'w')
        fd.write('pf = %s\n' % str(self.parser.pf_actions))
        fd.write('f = %s\n' % str(self.parser.flop_actions))
        fd.write('t = %s\n' % str(self.parser.turn_actions))
        fd.write('r = %s\n' % str(self.parser.river_actions))
        fd.close()

    def _parse_txt(self, tcfile):
        """Parse testcase file using txt parser.
        """
        self.parser = TxtParser(tcfile)

    def _parse_pa(self, tcfile):
        """Parse testcase file using poker academy parser.
        """
        self.parser = PaParser(tcfile)

    def _reset_table(self, mm):
        """Reset MM-XMLRPC.
        """
        for c in range(0, 10):
            mm.SetActive(c, False)
            mm.SetSeated(c, False)
            mm.SetCards(c, 'N', 'N')
            mm.SetBalance(c, 1000.0)
            mm.SetBet(c, 0.0)
            mm.SetFlopCards('N', 'N', 'N')
            mm.SetTurnCard('N')
            mm.SetRiverCard('N')
            mm.SetTournament(True)
        for b in 'FCKRA':
            mm.SetButton(b, False)
        time.sleep(0.5)

    def _configure_table(self, mm):
        """Configure MM-XMLRPC for this testcase.
        """
        mm.SetPot(0.0)

        if self.parser.sblind is not None:
            mm.SetSBlind(self.parser.sblind)

        if self.parser.bblind is not None:
            mm.SetBBlind(self.parser.bblind)

        if self.parser.bbet is not None:
            mm.SetBBet(self.parser.bbet)

        if self.parser.ante is not None:
            mm.SetAnte(self.parser.ante)

        if self.parser.gtype is not None:
            if self.parser.gtype in ('NL', 'PL', 'FL'):
                mm.SetGType(self.parser.gtype)

        if self.parser.network is not None:
            mm.SetNetwork(self.parser.network)

        if self.parser.tournament is not None:
            mm.SetTournament(self.parser.tournament)

        if self.parser.balances is not None:
            for player, balance in self.parser.balances:
                mm.SetBalance(self.players.index(player.strip()), float(balance.strip()))

        mm.Refresh()

    def _add_players(self, mm):
        """Add players form testcase to the table.
        """
        c = 0
        for p in self.players:
            mm.SetActive(c, True)
            mm.SetSeated(c, True)
            mm.SetCards(c, 'B', 'B')
            mm.SetName(c, p)
            c += 1
        mm.Refresh()

    def _set_hero(self, mm):
        """Configure hero cards.
        """
        mm.SetCards(self.players.index(self.parser.hero), self.parser.hand[0], self.parser.hand[1])

    def _set_dealer(self, mm):
        """Configure dealer on the table.
        """
        mm.SetDealer(self.players.index(self.dealer))

    def _next_action(self, mm):
        """Generator which yeld next action in this testcase.
        """
        self.bround = 'preflop'
        for a in self.parser.pf_actions:
            yield a

        if self.parser.fc:
            mm.SetFlopCards(self.parser.fc[0], self.parser.fc[1], self.parser.fc[2])

        self.bround = 'flop'
        for a in self.parser.flop_actions:
            yield a

        if self.parser.tc:
            mm.SetTurnCard(self.parser.tc)
        else:
            return

        self.bround = 'turn'
        for a in self.parser.turn_actions:
            yield a

        if self.parser.rc:
            mm.SetRiverCard(self.parser.rc)
        else:
            return

        self.bround = 'river'
        for a in self.parser.river_actions:
            yield a

    def _do_action(self, action, mm):
        """Do single action on the table.
        """
        self.last_action = action
        self.add_log('Processing %s action: %s' % (self.bround, action))
        time.sleep(0.5)
        if len(action) == 2:
            if action[1] == 'S':
                mm.PostSB(self.players.index(action[0]))
            elif action[1] == 'B':
                mm.PostBB(self.players.index(action[0]))
            elif action[1] == 'C':
                mm.DoCall(self.players.index(action[0]))
            elif action[1] == 'R':
                mm.DoRaise(self.players.index(action[0]))
            elif action[1] == 'F':
                mm.DoFold(self.players.index(action[0]))
            return False
        elif len(action) == 3:
            if action[1] == 'R':
                mm.DoRaise(self.players.index(action[0]),float(action[2]))
            return False
        else:
            #print str(action)
            # it's out turn, we need to show buttons
            for b in action[2]:
                mm.SetButton(b, True)
            return True

    def execute(self, hand_number = None):
        """Method used to starting testcase execution.
        """
        mm = xmlrpclib.ServerProxy('http://localhost:9092')

        if self.status == 'not started':
            if hand_number:
                mm.SetHandNumber(hand_number)
                self.add_log('\n    <b>====    %s    ====</b>\n' % self.tcfile)
            self._reset_table(mm)
            self._configure_table(mm)
            self._add_players(mm)
            self._set_hero(mm)
            self._set_dealer(mm)
            self.status = 'started'
            self._next_action = self._next_action(mm) # yea, ugly

        for action in self._next_action:
            if self.aborted:
                self.status = 'done'
                return
            ra = self._do_action(action, mm)
            mm.Refresh()
            if ra:
                try:
                    result = mm.GetAction()
                    button = result['button']
                    betsize = result['betsize']
                except:
                    break

                for b in 'FCKRA':
                    mm.SetButton(b, False)
                self.handle_button(button, betsize)
        self.status = 'done'

    def handle_button(self, button, betsize):
        """Handler for button click send by OH.
        """
        mm = xmlrpclib.ServerProxy('http://localhost:9092')

        # NOTE: be careful!

        # _expected_action_ is action from testcase, so:
        #
        # F - Fold, C - Call, K - Check, A - AllIn
        # but:
        # R - min raise, R - swag (depends on betsize)
        # if betsize then swag, else min raise


        # _button_ is button of ManualMode clicked by OH, so:
        #
        # F - action Fold, C - action Call, K - action Check,
        # R - action min raise!
        # but:
        # A - AllIn, A - swag (depends on betsize)
        # if betsize then swag, else AllIn

        expected_action = self.last_action[4]

        expected_betsize = None
        if len(self.last_action) == 6:
            expected_betsize = self.last_action[5]

        if expected_action == button and betsize == '' and not expected_betsize:
            # expected F got F
            # expected C got C
            # expected K got K
            # expected R got R - where R is min raise
            # expected A got A.
            # all this without betsize set
            self.add_log('<font color="#009900"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected_action, button))

        elif expected_action == 'R' and expected_betsize and button == 'A' and betsize != "":
            # correct swag (defined in testcase as R)
            # expected S (A + betsize) got S (A + betsize)
            self.add_log('<font color="#009900"><b>Expected %s (swag), got %s (swag).</b></font><font color="#000000"> </font>' % (expected_action, button))

        elif (expected_action == 'K' and button == 'C') or (expected_action == 'F' and button == 'K'):
            # acceptable button
            # expected K got C
            # expected F got K
            self.add_log('<font color="#CF8D0A"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected_action, button))

        else:
            ginfo = "" # got info
            einfo = "" # expected info

            if betsize and button == 'A':
                ginfo = " (swag)"

            if expected_betsize and expected_action == 'R':
                einfo = " (swag)"

            self.add_log('<font color="#FF0000"><b>Expected %s%s, got %s%s.</b></font><font color="#000000"> </font>' % (expected_action, einfo, button, ginfo))

        if expected_betsize:
            if expected_betsize == betsize:
                self.add_log('<font color="#009900"><b>Expected \'%s\', got \'%s\'.</b></font><font color="#000000"> </font>' % (expected_betsize, betsize))
            else:
                self.add_log('<font color="#FF0000"><b>Expected \'%s\', got \'%s\'.</b></font><font color="#000000"> </font>' % (expected_betsize, betsize))
        else:
            if betsize:
                self.add_log('<font color="#FF0000"><b>Didn\'t expected swag, got \'%s\'.</b></font><font color="#000000"> </font>' % (betsize))

        if button == 'F' or expected_action == 'F':
            mm.DoFold(self.players.index(self.parser.hero))
            # Abort testcase after bot fold
            self.aborted = True

        elif button == 'C':
            mm.DoCall(self.players.index(self.parser.hero))

        elif button == 'K':
            pass

        elif button == 'R': # min raise
            mm.DoRaise(self.players.index(self.parser.hero))

        elif button == 'A': # allin or swag
            if betsize:
                mm.DoRaise(self.players.index(self.parser.hero), float(betsize))
            else:
                mm.DoAllin(self.players.index(self.parser.hero))

        mm.Refresh()

    def stop_handling(self):
        return 0

class TestSuite(QObject):
    def __init__(self, directory, form):
        QObject.__init__(self)

        self.tc_dir = directory

        self.tc = None

        self.load_testcases()
        self.hand_number = 0

        self.form = form
        self.connect(self, SIGNAL('add_log'), form.add_log, QtCore.Qt.QueuedConnection)
        self.connect(self, SIGNAL('network_error'), form.network_error, QtCore.Qt.QueuedConnection)

    def network_error(self):
        self.emit(SIGNAL('network_error'))

    def load_testcases(self):
        self.tc_files = [file for file in os.listdir(self.tc_dir) if file[-4:] == '.txt' or file[-3:] == '.pa']

    def execute(self, tcf):
        self.tc = TestCase(os.path.join(self.tc_dir, str(tcf)), self.form)
        self.hand_number += 1

        try:
            self.tc.execute(self.hand_number)
        except socket.error:
            self.network_error()

        while self.tc.status != 'done':
            time.sleep(0.5)

    def stop(self):
        self.tc.aborted = True

        try:
            mm = xmlrpclib.ServerProxy('http://localhost:9092')
            mm.CancelGetAction()
        except socket.error:
            pass

        self.emit(SIGNAL('add_log'), '<font color="#FF0000"><b>Stopped...</b></font><font color="#000000"> </font>')


def start_gui():
    app = QtGui.QApplication(sys.argv)
    myapp = MyForm()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    start_gui()

# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

