

class PseudoRpi(object):

    def __init__(self):
        pass
    pass

class GPIO:
    BCM = ''
    IN = 'in'
    OUT = 'out'
    PUD_DOWN = 'down'
    PUD_UP = 'up'
    RISING = 'rising'
    FALLING = 'falling'
    def __init__(self):
        pass
    def setmode(self,asdf):
        pass
    def setup(self, pinid, inout, pull_up_down = None):
        pass
    def add_event_detect(self, pinid, risefall, callback):
        pass
    def output(self, pinid, truefalse):
        pass
    def cleanup(self):
        pass


class LED:
    def __init__(self):
        pass
    class sevensegment:
        def __init__(self):
            pass
        def write_number(self, deviceId, value):
            pass
