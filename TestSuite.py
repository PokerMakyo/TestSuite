import os
import sys
import time
import xmlrpclib
import socket
import ConfigParser

from gen import Ui_Form
from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QTextCursor
from PyQt4.QtCore import SIGNAL, QObject, QString

from itertools import izip

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

                if litm:
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

class MyCycle(object):
    def __init__(self, lst):
        self.list = lst

    def __iter__(self):
        while True:
            items_left = False
            for x in self.list:
                if x is not None:
                    items_left = True
                    yield x
            if not items_left:
                return

    def remove(self, e):
        self.list[self.list.index(e)] = None

    def get_list(self):
        return [p for p in self.list if p]

class TxtParser(object):
    def __init__(self, tcfile):
        # table configuration
        self.sblind = None
        self.bblind = None
        self.bbet = None
        self.ante = None
        self.gtype = None
        self.network = None
        self.tournament = None
        self.balances = None

        self._parse(tcfile)

    def _parse_actions(self, config_text):
        actions = []
        for act in config_text.split(','):
            act = act.strip()
            act = act.split(' ')
            actions.append([a.strip() for a in act])
        return actions

    def _parse(self, tcfile):
        self.config = ConfigParser.SafeConfigParser()
        self.config.read(tcfile)

        config = self.config # shortcut
        self.pf_actions = self._parse_actions(config.get('preflop', 'actions'))
        self.hand = [c.strip() for c in config.get('preflop', 'hand').split(',')]

        try:
            self.flop_actions = self._parse_actions(config.get('flop', 'actions'))
            self.fc = [c.strip() for c in config.get('flop', 'cards').split(',')]
        except:
            self.flop_actions = []
            self.fc = None

        try:
            self.turn_actions = self._parse_actions(config.get('turn', 'actions'))
            self.tc = config.get('turn', 'card')
        except:
            self.turn_actions = []
            self.tc = None

        try:
            self.river_actions = self._parse_actions(config.get('river', 'actions'))
            self.rc = config.get('river', 'card')
        except:
            self.river_actions = []
            self.rc = None

        for a in self.pf_actions:
            if len(a) > 3:
                self.hero = a[0]

        def sblind():
            self.sblind = config.getfloat('table', 'sblind')

        def bblind():
            self.bblind = config.getfloat('table', 'bblind')

        def bbet():
            self.bbet = float(config.getfloat('table', 'bbet'))

        def ante():
            self.ante = float(config.getfloat('table', 'ante'))

        def gtype():
            self.gtype = config.get('table', 'gtype')

        def network():
            self.network = config.get('table', 'network')

        def tournament():
            self.tournament = config.getboolean('table', 'tournament')

        def balances():
            balances = config.get('table', 'balances')
            self.balances = [b.split() for b in balances.split(',')]

        for t in (sblind, bblind, bbet, ante, gtype, network, tournament, balances):
            try:
                t()
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
                if e.section == 'table':
                    pass # this is optional
                else:
                    pass
                    # FIXME: handle it!
            except:
                pass
                # FIXME: handle it!

class PaParser(object):
    def __init__(self, tcfile):
        self.sblind = None
        self.bblind = None
        self.bbet = None
        self.ante = None
        self.gtype = None
        self.network = None
        self.tournament = None
        self.balances = None

        self.pf_actions = ()
        self.flop_actions = ()
        self.turn_actions = ()
        self.river_actions = ()

        self._parse(tcfile)

    def _parse(self, tcfile):
        fd = file(tcfile)
        tcd = {}

        for e in fd.readline()[:-1].split(';'):
            key, value = e.split('=')
            if key[:2] == 'PN':
                value = value.replace(' ', '')
            tcd[key] = value

        sb = int(tcd['SBS'])

        players_order = [i for i in range(sb, 10)] + [i for i in range(0, sb)]

        players = []
        for i in players_order:
            try:
                players.append(tcd['PN%i' % i])
            except KeyError:
                pass

        actions = tcd['SEQ'].split('/')

        actions = [a.replace('b', 'r').upper() for a in actions]

        self.hero = tcd['HERO']

        def get_history(pc, actions):
            history = []
            for player, action in izip(pc, actions):
                if action == 'F':
                    pc.remove(player)
                if player == self.hero:
                    if action == 'S':
                        action = (player, 'S')
                    elif action == 'B':
                        action = (player, 'B')
                    else:
                        action = ("%s can CRFK do %s" % (player, action)).split(' ')
                    history.append(action)
                else:
                    history.append((player, action))
            return history

        pc = MyCycle(players)
        try:
            self.pf_actions = get_history(pc, actions[0])

            pc = MyCycle(pc.get_list())
            self.flop_actions = get_history(pc, actions[1])

            pc = MyCycle(pc.get_list())
            self.turn_actions = get_history(pc, actions[2])

            pc = MyCycle(pc.get_list())
            self.river_actions = get_history(pc, actions[3])
        except IndexError:
            pass # don't have turn for example

        board = tcd['BOARD']
        cards = [board[i]+board[i+1] for i in range(0, len(board), 2)]

        if cards[0][0] != '?':
            self.fc = cards[:3]
        else:
            self.fc = None

        if cards[3][0] != '?':
            self.tc = cards[3]
        else:
            self.tc = None

        if cards[4][0] != '?':
            self.rc = cards[4]
        else:
            self.rc = None

        ntp = {}
        for i in range(0, 10):
            try:
                ntp[tcd['PN%i' % i]] = i
            except KeyError:
                pass

        self.hand = [tcd['PC%i' % ntp[self.hero]][:2], tcd['PC%i' % ntp[self.hero]][-2:]]

        self.balances = []
        for i in range(0, 10):
            try:
                self.balances.append((tcd['PN%i' % i], tcd['PB%i' % i]))
            except KeyError:
                pass

        self.sblind = float(tcd['SB'])
        self.bblind = float(tcd['BB'])
        self.ante = float(tcd['ANTE'])


class TestCase(QObject):
    def __init__(self, tcfile, form):
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

        # dealer is sitting before SB
        SB = self.parser.pf_actions[0][0]
        self.dealer = self.players[self.players.index(SB) - 1]

    def add_log(self, message):
        self.emit(SIGNAL('add_log'), message)

    def _dump_history(self):
        fd = open('tshistory.py', 'w')
        fd.write('pf = %s\n' % str(self.parser.pf_actions))
        fd.write('f = %s\n' % str(self.parser.flop_actions))
        fd.write('t = %s\n' % str(self.parser.turn_actions))
        fd.write('r = %s\n' % str(self.parser.river_actions))
        fd.close()

    def _parse_txt(self, tcfile):
        self.parser = TxtParser(tcfile)

    def _parse_pa(self, tcfile):
        self.parser = PaParser(tcfile)

    def _reset_table(self, mm):
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
        mm.SetPot(0.0)

        if self.parser.sblind:
            mm.SetSBlind(self.parser.sblind)

        if self.parser.bblind:
            mm.SetBBlind(self.parser.bblind)

        if self.parser.bbet:
            mm.SetBBet(self.parser.bbet)

        if self.parser.ante:
            mm.SetAnte(self.parser.ante)

        if self.parser.gtype:
            if self.parser.gtype in ('NL', 'PL', 'FL'):
                mm.SetGType(self.parser.gtype)

        if self.parser.network:
            mm.SetNetwork(self.parser.network)

        if self.parser.tournament:
            mm.SetTournament(self.parser.tournament)

        if self.parser.balances:
            for player, balance in self.parser.balances:
                mm.SetBalance(self.players.index(player.strip()), float(balance.strip()))

        mm.Refresh()

    def _add_players(self, mm):
        c = 0
        for p in self.players:
            mm.SetActive(c, True)
            mm.SetSeated(c, True)
            mm.SetCards(c, 'B', 'B')
            mm.SetName(c, p)
            c += 1
        mm.Refresh()

    def _set_hero(self, mm):
        mm.SetCards(self.players.index(self.parser.hero), self.parser.hand[0], self.parser.hand[1])

    def _set_dealer(self, mm):
        mm.SetDealer(self.players.index(self.dealer))

    def _next_action(self, mm):
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
        mm = xmlrpclib.ServerProxy('http://localhost:9092')

        expected_button = self.last_action[4]
        expected_betsize = None
        if len(self.last_action) == 6:
            expected_betsize = self.last_action[5]


        stop = False
        if expected_button == button:
            self.add_log('<font color="#009900"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected_button, button))
        elif (expected_button == 'K' and button == 'C') or (expected_button == 'F' and button == 'K'):
            self.add_log('<font color="#CF8D0A"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected_button, button))
        else:
            self.add_log('<font color="#FF0000"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected_button, button))

        if expected_betsize:
            if expected_betsize == betsize:
                self.add_log('<font color="#009900"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected_betsize, betsize))
            else:
                self.add_log('<font color="#FF0000"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected_betsize, betsize))

        if button == 'F' or expected_button == 'F':
            #print 'We are doing fold.'
            mm.DoFold(self.players.index(self.parser.hero))
            # Abort testcase after bot fold
            self.aborted = True
        elif button == 'C':
            #print 'We are doing call.'
            mm.DoCall(self.players.index(self.parser.hero))
        elif button == 'K':
            #print 'We are doing check.'
            pass
        elif button == 'R':
            #print 'We are doing raise.'
            if expected_betsize:
                mm.DoRaise(self.players.index(self.parser.hero), float(betsize))
            else:
                mm.DoRaise(self.players.index(self.parser.hero))

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
        except:
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

