class One: pass
class Two: pass
class Maker(One, Two, metaclass=Meta): pass