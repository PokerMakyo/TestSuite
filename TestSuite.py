import os
import time
import xmlrpclib
import ConfigParser

from SimpleXMLRPCServer import SimpleXMLRPCServer
from threading import Thread

class TestCase(object):
    def __init__(self, mm, server, tcfile, litm = None, logs = None):
        self.status = 'not started'

        self.litm = litm
        self.logs = logs

        self.bround = None

        self.config = ConfigParser.SafeConfigParser()
        self.tcfile = tcfile
        self.config.read(tcfile)

        self.mm = mm
        self.server = server

        server.register_function(self.event)

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

    def _parse_actions(self, config_text):
        actions = []
        for act in config_text.split(','):
            act = act.strip()
            act = act.split(' ')
            actions.append([a.strip() for a in act])
        return actions

    def _reset_table(self):
        for c in range(0, 10):
            self.mm.SetActive(c, False)
            self.mm.SetSeated(c, False)
            self.mm.SetCards(c, 'N', 'N')
            self.mm.SetBalance(c, 1000.0)
            self.mm.SetBet(c, 0.0)
            self.mm.SetFlopCards('N', 'N', 'N')
            self.mm.SetTurnCard('N')
            self.mm.SetRiverCard('N')
        for b in 'FCKRA':
            self.mm.SetButton(b, False)
        time.sleep(2)

    def _configure_table(self):
        config = self.config # shortcut

        def sblind():
            sblind = config.getfloat('table', 'sblind')
            self.mm.SetSBlind(sblind)

        def bblind():
            bblind = config.getfloat('table', 'bblind')
            self.mm.SetBBlind(bblind)

        def bbet():
            bbet = float(config.getfloat('table', 'bbet'))
            self.mm.SetBBet(bbet)

        def ante():
            ante = float(config.getfloat('table', 'ante'))
            self.mm.SetAnte(ante)

        def gtype():
            gtype = config.get('table', 'gtype')
            if gtype in ('NL', 'PL', 'FL'):
                self.mm.SetGType(gtype)

        def network():
            network = config.get('table', 'network')
            self.mm.SetNetwork(network)

        def tournament():
            tournament = config.getboolean('table', 'tournament')
            self.mm.SetTournament(tournament)

        def balances():
            balances = config.get('table', 'balances')
            balances = balances.split(',')
            for balance in balances:
                b = balance.strip().split(' ')
                print b
                self.mm.SetBalance(self.players.index(b[0].strip()), float(b[1].strip()))

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

        self.mm.Refresh()

    def _add_players(self):
        c = 0
        for p in self.players:
            self.mm.SetActive(c, True)
            self.mm.SetSeated(c, True)
            self.mm.SetCards(c, 'B', 'B')
            self.mm.SetName(c, p)
            c += 1
        self.mm.Refresh()

    def _set_hero(self):
        self.mm.SetCards(self.players.index(self.hero), self.hand[0], self.hand[1])

    def _set_dealer(self):
        self.mm.SetDealer(self.players.index(self.dealer))

    def _next_action(self):
        self.bround = 'preflop'
        for a in self.pf_actions:
            yield a

        if self.fc:
            self.mm.SetFlopCards(self.fc[0], self.fc[1], self.fc[2])

        self.bround = 'flop'
        for a in self.flop_actions:
            yield a

        if self.tc:
            self.mm.SetTurnCard(self.tc)
        else:
            return

        self.bround = 'turn'
        for a in self.turn_actions:
            yield a

        if self.rc:
            self.mm.SetRiverCard(self.rc)
        else:
            return

        self.bround = 'river'
        for a in self.river_actions:
            yield a

    def _do_action(self, action):
        self.last_action = action
        if not self.logs:
            print 'Processing %s action: %s' % (self.bround, action)
        else:
            self.logs.append('Processing %s action: %s' % (self.bround, action))
        time.sleep(0.5)
        if len(action) == 2:
            if action[1] == 'S':
                self.mm.PostSB(self.players.index(action[0]))
            elif action[1] == 'B':
                self.mm.PostBB(self.players.index(action[0]))
            elif action[1] == 'C':
                self.mm.DoCall(self.players.index(action[0]))
            elif action[1] == 'R':
                self.mm.DoRaise(self.players.index(action[0]))
            elif action[1] == 'F':
                self.mm.DoFold(self.players.index(action[0]))
            self.mm.Refresh()
            return False
        elif len(action) == 3:
            if action[1] == 'R':
                self.mm.DoRaise(self.players.index(action[0]),float(action[2]))
            self.mm.Refresh()
            return False
        else:
            # it's out turn, we need to show buttons
            for b in action[2]:
                self.mm.SetButton(b, True)
            self.mm.Refresh()

            return True

    def execute(self, hand_number = None):
        if self.status == 'not started':
            if hand_number:
                self.mm.SetHandNumber(hand_number)
            if not self.logs:
                print '    ====    %s    ====' % self.tcfile
            else:
                self.logs.append('\n    <b>====    %s    ====</b>\n' % self.tcfile)
            self._reset_table()
            self._configure_table()
            self.mm.ProvideEventsHandling()
            self._add_players()
            self._set_hero()
            self._set_dealer()
            self.status = 'started'
            self._next_action = self._next_action() # yea, ugly

        ra = False
        for action in self._next_action:
            ra = self._do_action(action)
            if ra:
                self.server.handle_request() # need to wait for OH action
                break;
        if not ra:
            self.status = 'done'

    def handle_event(self, button):
        if not self.logs:
            print 'Expected %s, got %s.' % (self.last_action[4], button)
        else:
            if self.last_action[4] == button:
                self.logs.append('<font color="#009900"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (self.last_action[4], button))
            else:
                self.logs.append('<font color="#FF0000"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (self.last_action[4], button))

        if button == 'F':
            #print 'We are doing fold.'
            self.mm.DoFold(self.players.index(self.hero))
        elif button == 'C':
            #print 'We are doing call.'
            self.mm.DoCall(self.players.index(self.hero))
        elif button == 'K':
            #print 'We are doing check.'
            pass
        elif button == 'R':
            #print 'We are doing raise.'
            self.mm.DoRaise(self.players.index(self.hero))
        self.mm.Refresh()

        self.execute()

    def event(self, button):
        for b in 'FCKRA':
            self.mm.SetButton(b, False)
        self.mm.Refresh()
        Thread(target=self.handle_event, args=(button,)).start()

class TestSuite(object):
    def __init__(self):
        self.tc_dir = 'testcases'

        self.server = SimpleXMLRPCServer(("localhost", 9093))
        self.mm = xmlrpclib.ServerProxy('http://localhost:9092')

        self.load_testcases()
        self.hand_number = 0

    def load_testcases(self):
        self.tc_files = os.listdir(self.tc_dir)

    def execute(self, tcf, litm, logs):
        tc = TestCase(self.mm, self.server, os.path.join(self.tc_dir, str(tcf)), litm, logs)
        self.hand_number += 1
        tc.execute(self.hand_number)
        while tc.status != 'done':
            time.sleep(1)

if __name__ == '__main__':
    ts = TestSuite()
    ts.execute_all()

# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

