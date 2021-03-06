import datetime as dt
import pygame as pg

class PseudoCamera(object):
    '''
    Pseudo Camera replacing piggyphoto used for developing / debugging without plugged-in hardware device.
    '''

    def __init__(self):
        self.__surface = pg.display.get_surface()
        self.__font = pg.font.SysFont("monospace", 800)
        pass

    def __capture(self, path, size):
        surface = pg.Surface(size)
        surface.fill([80, 0, 0])

        time = dt.datetime.now().strftime("%H:%M:%S.%f")

        text = self.__font.render(time, 1, (200, 200, 0))
        surface.blit(text, [50, 50])
        pg.image.save(surface, path)

    def capture_image(self, path):
        self.__capture(path, [2592, 1728])

    def capture_preview(self, path):
       self.__capture(path, [5184, 3456])

    def leave_locked(self):
        pass

    def close(self):
        pass
