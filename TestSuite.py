import os
import time
import xmlrpclib
import ConfigParser

from itertools import izip
from SimpleXMLRPCServer import SimpleXMLRPCServer
from threading import Thread

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
    def __init__(self, mm, server, tcfile, litm = None, logs = None):
        self.status = 'not started'

        self.aborted = False
        self.handling = False

        self.litm = litm
        self.logs = logs

        self.bround = None

        self.tcfile = tcfile

        self.mm = mm
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
        if self.sblind:
            self.mm.SetSBlind(self.sblind)

        if self.bblind:
            self.mm.SetBBlind(self.bblind)

        if self.bbet:
            self.mm.SetBBet(self.bbet)

        if self.ante:
            self.mm.SetAnte(self.ante)

        if self.gtype:
            if self.gtype in ('NL', 'PL', 'FL'):
                self.mm.SetGType(self.gtype)

        if self.network:
            self.mm.SetNetwork(self.network)

        if self.tournament:
            self.mm.SetTournament(self.tournament)

        if self.balances:
            for player, balance in self.balances:
                self.mm.SetBalance(self.players.index(player.strip()), float(balance.strip()))

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
            if self.aborted:
                return
            ra = self._do_action(action)
            if ra:
                self.handling = True
                self.server.handle_request() # need to wait for OH action
                self.handling = False
                break;
        if not ra:
            self.status = 'done'

    def handle_event(self, button):
        if not self.logs:
            print 'Expected %s, got %s.' % (self.last_action[4], button)
        else:
            if self.last_action[4] == button:
                self.logs.append('<font color="#009900"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (self.last_action[4], button))
            elif self.last_action[4] == 'K' and button == 'C':
                self.logs.append('<font color="#CF8D0A"><b>Expected %s, got %s.</b></font><font color="#000000"> </font>' % (self.last_action[4], button))
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

    def stop_handling(self):
        return 0

class TestSuite(object):
    def __init__(self):
        self.tc_dir = 'testcases'

        self.tc = None

        self.logs = None

        self.server = SimpleXMLRPCServer(("localhost", 9093))
        self.mm = xmlrpclib.ServerProxy('http://localhost:9092')

        self.load_testcases()
        self.hand_number = 0

    def load_testcases(self):
        self.tc_files = [file for file in os.listdir(self.tc_dir) if file[-4:] == '.txt' or file[-3:] == '.pa']

    def execute(self, tcf, litm, logs):
        self.logs = logs
        self.tc = TestCase(self.mm, self.server, os.path.join(self.tc_dir, str(tcf)), litm, logs)
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

if __name__ == '__main__':
    ts = TestSuite()
    ts.execute_all()

# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

