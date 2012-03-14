import os
import sys
import time
import xmlrpclib
import ConfigParser

from gen import Ui_Form
from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import QTextCursor, QMessageBox

from itertools import izip
from SimpleXMLRPCServer import SimpleXMLRPCServer

import pdb

lock = QtCore.QMutex()

class MyForm(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.ts = None

        self.aborted = False

        self.reload_event()

    def _update_buttons(self, executing):
        self.ui.execute.setEnabled(not executing)
        self.ui.execute_all.setEnabled(not executing)
        self.ui.reload.setEnabled(not executing)
        self.ui.stop.setEnabled(executing)

    def handle_execute(self, all=False):
        class Testing(QtCore.QThread):
            def __init__(self, form, all):
                QtCore.QThread.__init__(self)
                self.form = form
                self.all = all

            def run(self):
                self.form._update_buttons(True)
                self.form.aborted = False
                if not self.all:
                    litm = self.form.ui.testcases.currentItem()
                    self.form.ts.execute(litm.text(), litm, self.form.ui.logs)
                else:
                    for i in range(0, self.form.ui.testcases.count()):
                        if self.form.aborted:
                            break
                        litm = self.form.ui.testcases.item(i)
                        self.form.ts.execute(litm.text(), litm, self.form.ui.logs)
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

class TestCase(object):
    def __init__(self, server, tcfile, logs = None):
        self.status = 'not started'

        self.aborted = False
        self.handling = False

        self.logs = logs

        self.bround = None

        self.tcfile = tcfile

        self.server = server

        server.register_function(self.event)
        server.register_function(self.stop_handling)

        # table configuration
        self.sblind = None
        self.bblind = None
        self.bbet = None
        self.ante = None
        self.gtype = None
        self.network = None
        self.tournament = None
        self.balances = None

        if tcfile[-3:] == '.pa':
            self._parse_pa(tcfile)
        else:
            self._parse_txt(tcfile)

        self._dump_history()

        self.players = []
        for a in self.pf_actions:
            if a[0] not in self.players:
                self.players.append(a[0])
            else:
                break

        # we want to have Hero always on chair == 0
        for i in range(0, len(self.players) - self.players.index(self.hero)):
            p = self.players.pop()
            self.players.insert(0, p)

        # dealer is sitting before SB
        SB = self.pf_actions[0][0]
        self.dealer = self.players[self.players.index(SB) - 1]

    def _dump_history(self):
        fd = open('tshistory.py', 'w')
        fd.write('pf = %s\n' % str(self.pf_actions))
        fd.write('f = %s\n' % str(self.flop_actions))
        fd.write('t = %s\n' % str(self.turn_actions))
        fd.write('r = %s\n' % str(self.river_actions))
        fd.close()

    def _parse_txt(self, tcfile):
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

    def _parse_pa(self, tcfile):
        fd = file(tcfile)

        tcd = {}

        for e in fd.readline()[:-1].split(';'):
            key, value = e.split('=')
            tcd[key] = value

        sb = int(tcd['SBS'])

        players_order = [i for i in range(sb, 10)] + [i for i in range(0, sb)]

        players = []
        for i in players_order:
            try:
                players.append(tcd['PN%i' % i])
            except KeyError:
                pass

        print players

        actions = tcd['SEQ'].split('/')

        actions = [a.replace('b', 'r').upper() for a in actions]

        print 'preflop'

        self.hero = tcd['HERO']

        def get_history(pc, actions):
            history = []
            for player, action in izip(pc, actions):
                if player == self.hero:
                    action = ("%s can CRFK do %s" % (player, action)).split(' ')
                    history.append(action)
                else:
                    history.append((player, action))
                if action == 'f':
                    pc.remove(player)
            return history


        pc = MyCycle(players)
        self.pf_actions = get_history(pc, actions[0])

        pc = MyCycle(pc.get_list())
        self.flop_actions = get_history(pc, actions[1])

        pc = MyCycle(pc.get_list())
        self.turn_actions = get_history(pc, actions[2])

        pc = MyCycle(pc.get_list())
        self.river_actions = get_history(pc, actions[3])

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

        print ntp

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

    def _parse_actions(self, config_text):
        actions = []
        for act in config_text.split(','):
            act = act.strip()
            act = act.split(' ')
            actions.append([a.strip() for a in act])
        return actions

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
        time.sleep(2)

    def _configure_table(self, mm):
        if self.sblind:
            mm.SetSBlind(self.sblind)

        if self.bblind:
            mm.SetBBlind(self.bblind)

        if self.bbet:
            mm.SetBBet(self.bbet)

        if self.ante:
            mm.SetAnte(self.ante)

        if self.gtype:
            if self.gtype in ('NL', 'PL', 'FL'):
                mm.SetGType(self.gtype)

        if self.network:
            mm.SetNetwork(self.network)

        if self.tournament:
            mm.SetTournament(self.tournament)

        if self.balances:
            for player, balance in self.balances:
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
        mm.SetCards(self.players.index(self.hero), self.hand[0], self.hand[1])

    def _set_dealer(self, mm):
        mm.SetDealer(self.players.index(self.dealer))

    def _next_action(self, mm):
        self.bround = 'preflop'
        for a in self.pf_actions:
            yield a

        if self.fc:
            mm.SetFlopCards(self.fc[0], self.fc[1], self.fc[2])

        self.bround = 'flop'
        for a in self.flop_actions:
            yield a

        if self.tc:
            mm.SetTurnCard(self.tc)
        else:
            return

        self.bround = 'turn'
        for a in self.turn_actions:
            yield a

        if self.rc:
            mm.SetRiverCard(self.rc)
        else:
            return

        self.bround = 'river'
        for a in self.river_actions:
            yield a

    def _do_action(self, action, mm):
        self.last_action = action
        if not self.logs:
            print 'Processing %s action: %s' % (self.bround, action)
        else:
            self.logs.append('Processing %s action: %s' % (self.bround, action))
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
            mm.Refresh()
            return False
        elif len(action) == 3:
            if action[1] == 'R':
                mm.DoRaise(self.players.index(action[0]),float(action[2]))
            mm.Refresh()
            return False
        else:
            # it's out turn, we need to show buttons
            for b in action[2]:
                mm.SetButton(b, True)
            mm.Refresh()

            return True

    def execute(self, hand_number = None):
        mm = xmlrpclib.ServerProxy('http://localhost:9092')

        if self.status == 'not started':
            if hand_number:
                mm.SetHandNumber(hand_number)
            if not self.logs:
                print '    ====    %s    ====' % self.tcfile
            else:
                self.logs.append('\n    <b>====    %s    ====</b>\n' % self.tcfile)
            self._reset_table(mm)
            self._configure_table(mm)
            mm.ProvideEventsHandling()
            self._add_players(mm)
            self._set_hero(mm)
            self._set_dealer(mm)
            self.status = 'started'
            self._next_action = self._next_action(mm) # yea, ugly

        ra = False
        for action in self._next_action:
            if self.aborted:
                return
            ra = self._do_action(action, mm)
            if ra:
                self.handling = True
                self.server.handle_request() # need to wait for OH action
                self.handling = False
                break;
        if not ra:
            self.status = 'done'

    def handle_event(self, button):
        mm = xmlrpclib.ServerProxy('http://localhost:9092')

        expected = self.last_action[4]
        stop = False
        if not self.logs:
            print 'Expected %s, got %s.' % (expected, button)
        else:
            if expected == button:
                self.logs.append('<font color="#009900"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected, button))
            elif (expected == 'K' and button == 'C') or (expected == 'F' and button == 'K'):
                self.logs.append('<font color="#CF8D0A"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected, button))
            else:
                self.logs.append('<font color="#FF0000"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (expected, button))

        if button == 'F' or expected == 'F':
            #print 'We are doing fold.'
            mm.DoFold(self.players.index(self.hero))
        elif button == 'C':
            #print 'We are doing call.'
            mm.DoCall(self.players.index(self.hero))
        elif button == 'K':
            #print 'We are doing check.'
            pass
        elif button == 'R':
            #print 'We are doing raise.'
            mm.DoRaise(self.players.index(self.hero))
        mm.Refresh()

        self.execute()

    def event(self, button):
        mm = xmlrpclib.ServerProxy('http://localhost:9092')

        for b in 'FCKRA':
            mm.SetButton(b, False)

        class EventWaiter(QtCore.QThread):
            def __init__(self, handle_event, button):
                QtCore.QThread.__init__(self)
                self.handle_event = handle_event
                self.button = button
            def run(self):
                self.handle_event(button)

        self.event_waiter = EventWaiter(self.handle_event, button)
        self.event_waiter.start()

        mm.Refresh()

    def stop_handling(self):
        return 0

class TestSuite(object):
    def __init__(self):
        self.tc_dir = 'testcases'

        self.tc = None

        self.logs = None

        self.server = SimpleXMLRPCServer(("localhost", 9093), logRequests = False)

        self.load_testcases()
        self.hand_number = 0

    def load_testcases(self):
        self.tc_files = [file for file in os.listdir(self.tc_dir) if file[-4:] == '.txt' or file[-3:] == '.pa']

    def execute(self, tcf, litm, logs):
        self.logs = logs
        self.tc = TestCase(self.server, os.path.join(self.tc_dir, str(tcf)), logs)
        self.hand_number += 1
        self.tc.execute(self.hand_number)
        while self.tc.status != 'done':
            time.sleep(1)

    def stop(self):
        self.tc.aborted = True
        if self.tc.handling:
            myself = xmlrpclib.ServerProxy('http://localhost:9093')
            myself.stop_handling()
        self.logs.append('<font color="#FF0000"><b>Stopped...</b></font><font color="#000000"> </font>')


def start_gui():
    app = QtGui.QApplication(sys.argv)
    myapp = MyForm()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    try:
        start_gui()
    except Exception, e:
        pdb.set_trace()

# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

