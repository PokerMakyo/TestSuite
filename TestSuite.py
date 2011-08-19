import xmlrpclib

from SimpleXMLRPCServer import SimpleXMLRPCServer
from ConfigParser import SafeConfigParser

class TestCase(object):
    def __init__(self, mm, tcfile):
        self.started = False

        config = SafeConfigParser()
        config.read(tcfile)
        
        self.mm = mm

        self.pf_actions = self._parse_actions(config.get('preflop', 'actions'))
        self.flop_actions = self._parse_actions(config.get('flop', 'actions')) 
        self.turn_actions = self._parse_actions(config.get('turn', 'actions')) 
        self.river_actions = self._parse_actions(config.get('river', 'actions')) 

        self.hand = [c.strip() for c in config.get('preflop', 'hand').split(',')]
        self.fc = [c.strip() for c in config.get('flop', 'cards').split(',')]
        self.tc = config.get('turn', 'card')
        self.rc = config.get('river', 'card')

        self.players = []
        for a in self.pf_actions:
            if a[0] not in self.players:
                self.players.append(a[0])
            else:
                break
        
        for a in self.pf_actions:
            if len(a) > 2:
                self.hero = a[0]

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
        for a in self.pf_actions:
            yield a

        self.mm.SetFlopCards(self.fc[0], self.fc[1], self.fc[2])

        for a in self.flop_actions:
            yield a

        self.mm.SetTurnCard(self.tc)

        for a in self.turn_actions:
            yield a

        self.mm.SetRiverCard(self.rc)

        for a in self.river_actions:
            yield a

    def _do_action(self, action):
        self.last_action = action
        print action
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
        else:
            # it's out turn, we need to show buttons
            for b in action[2]:
                self.mm.SetButton(b, True)
            self.mm.Refresh()

            return True

    def execute(self):
        if not self.started:
            self._reset_table()
            mm.ProvideEventsHandling()
            self._add_players()
            self._set_hero()
            self._set_dealer()
            self.started = True
            self._next_action = self._next_action() # yea, ugly
        
        for action in self._next_action:
            if self._do_action(action):
                break; # need to wait for OH action
            
    def event(self, button):
        for b in 'FCKRA':
            self.mm.SetButton(b, False)

        print 'Button', button, 'was clicked.'
        print 'We expected', self.last_action[4]

        if button == 'F':
            print 'We are doing fold.'
            self.mm.DoFold(self.players.index(self.hero))
        elif button == 'C':
            print 'We are doing call.'
            self.mm.DoCall(self.players.index(self.hero))
        elif button == 'K':
            print 'We are doing check.'
        elif button == 'R':
            print 'We are doing raise.'

            self.mm.DoRaise(self.players.index(self.hero))
        self.mm.Refresh()
        self.execute()
        
if __name__ == '__main__':
    server = SimpleXMLRPCServer(("localhost", 9093))
    print "Listening on 9093..." 
    
    mm = xmlrpclib.ServerProxy('http://localhost:9092')

    tc = TestCase(mm, 'testcase1.txt')
    tc.execute()

    server.register_function(tc.event)
    
    while(1):
        server.handle_request()

# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

