import ConfigParser

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

# vim: filetype=python syntax=python expandtab shiftwidth=4 softtabstop=4

