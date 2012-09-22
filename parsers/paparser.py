class MyCycle(object):
    """Cycle with possibility to removing elements during iteration.
    """
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


# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

