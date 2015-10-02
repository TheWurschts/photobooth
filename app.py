#!/usr/bin/env python2

from __future__ import division
from __future__ import print_function

import ConfigParser as cfgp
import ctypes
import datetime as dt
import numpy
import os, errno
import piggyphoto
import pygame as pg
import sys
import threading
import time

from PseudoCamera import PseudoCamera

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)


ENABLE_GREENSCREEN = False
GREENSCREEN_COLOR = ''

SHOW_STYLING = False


ST_SLEEP = 0
ST_IDLE = 1
ST_SHOOT = 2
ST_BACKVIEW = 3
ST_PRINT = 4


def amIOnRpi():
	try:
		import RPi
		return True
	except:
		return False

def load_shared_lib(libname):
# We assume the shared library is present in the same directory as this script.
	libpath = os.path.dirname(os.path.realpath(__file__))

# Append proper extension to library path (.dll for Windows, .so for Linux)
	if sys.platform in ("win32", "cygwin"):
		libpath = os.path.join(libpath, "%s.dll" % libname)
	else:
		libpath = os.path.join(libpath, "%s.so" % libname)

# Check that library exists (in same folder as this script).
	if not os.path.exists(libpath):
		print("Shared lib not found: ", libname, ", ", libpath)
		return None

	return ctypes.CDLL(libpath)

class Photo(pg.sprite.Sprite):
	def __init__(self, width, height):
		pg.sprite.Sprite.__init__(self)
		self.image = pg.Surface([width, height])
		self.image.fill(GREEN)

		self.rect = self.image.get_rect()

class Photobooth:

	def __init__(self):

		self.__onRpi = amIOnRpi();

		# basic initializations
		self.__done = False				# Done? Exit.
		self.__state = ST_IDLE		# global state
		self.__surface = None		 # main surface
		self.__cnt_start = None		# countdown start timestamp

		# load config
		self.cfg = cfgp.ConfigParser()
		self.cfg.read("booth.cfg")

		self.__cfgs = self.cfg.items("shooting")

		self.__countdown = self.cfg.getint("shooting", "countdown")

		#if SHOW_STYLING == True:
		# load style
		self.__load_style()
		
		# init pg
		pg.init()

		self.__screen_width = self.cfg.getint("booth", "screen_width")
		self.__screen_height = self.cfg.getint("booth", "screen_height")

		#prepare screen
		self.__screen_size = map(int, [self.__screen_width , self.__screen_height])
		#screen = pg.display.set_mode(self.__screen_size)
		if self.__onRpi == True:
			screen = pg.display.set_mode(self.__screen_size, pg.FULLSCREEN)
		else:
			screen = pg.display.set_mode(self.__screen_size)#, pg.FULLSCREEN)
		pg.display.set_caption("Rocksack's Photobooth")

		# get main surface
		self.__surface = pg.display.get_surface()

		# font for writing countdown numbers
		self.__cnt_font = pg.font.SysFont("monospace", 400)

		# use clock to limit framerate
		self.__clock = pg.time.Clock()
		self.__fps = 60

		self.__mkdir("preview")

		if ENABLE_GREENSCREEN == True:
			self.__bgimage = pg.transform.scale(pg.image.load("gfx/berge.jpg").convert_alpha(), [800, 600])

		
			self.__libps = load_shared_lib("libpyslow")
			self.__gbf = self.__libps.greenbox
			self.__gbf.restype = None
			self.__gbf.argtypes = [numpy.ctypeslib.ndpointer(ctypes.c_int32), ctypes.c_int, ctypes.c_int]
			self.__zzf = self.__libps.sepia
			self.__zzf.restype = None
			self.__zzf.argtypes = [numpy.ctypeslib.ndpointer(ctypes.c_int32), ctypes.c_int, ctypes.c_int]

			self.__scalef = self.__libps.scale
			self.__scalef.restype = None
			self.__scalef.argtypes = [numpy.ctypeslib.ndpointer(ctypes.c_int32), ctypes.c_int, ctypes.c_int, numpy.ctypeslib.ndpointer(ctypes.c_int32), ctypes.c_int, ctypes.c_int]


	def __mkdir(self, path):
		try:
			os.makedirs(path)
		except OSError as exc: # Python >2.5
			if exc.errno == errno.EEXIST and os.path.isdir(path):
				pass
			else: raise
	def __load_style(self):
		style = self.cfg.get("shooting", "pic_style")
		pics = filter(lambda item: item[0][:3] == "pic", self.cfg.items(style))
		pics.sort()
		self.__pics_pos = list()
		for p in pics:
			self.__pics_pos.append(map(int, p[1].split(",")))
		self.__num_pics = len(pics)
		self.__bgcolor = map(int, self.cfg.get(style, "bgcolor").split(","))
		self.__view_box = map(int, self.cfg.get(style, "box").split(","))
		self.__resolution = map(int, self.cfg.get(style, "resolution").split(","))
		self.__fgsmall = pg.transform.scale(pg.image.load(self.cfg.get(style, "fgimage")), self.__view_box[2:])
		self.__fg = pg.transform.scale(pg.image.load(self.cfg.get(style, "fgimage")), self.__resolution)

	def show(self, file):
		picture = pg.image.load(file)
		self.__surface.blit(picture, (30, 40))
		pg.display.flip()

	def event_loop(self):
		for event in pg.event.get():
			if event.type == pg.KEYDOWN:
				if event.key == ord('q'):
					self.__done = True
				elif event.key == ord('a'):
					if self.__state == ST_IDLE:
						self.__state = ST_SHOOT
						now = dt.datetime.now()
						self.__photopath = dt.datetime.now().strftime("photos/%Y-%m-%d")
						self.__mkdir(self.__photopath)
						self.__cnt_images = len(self.__pics_pos)
						self.__cnt_start = dt.datetime.now()
				print('key: ' + str(event.key))
			if event.type == pg.QUIT:
				self.__camera.close()
				done = True

	def render_live(self, path):
		self.__camera.capture_preview(path)
		picture = pg.transform.scale(pg.image.load(path).convert_alpha(), self.__screen_size)

		if ENABLE_GREENSCREEN == True:
			self.__surface.blit(self.__bgimage, [0, 0])

			rgb = pg.surfarray.pixels2d(picture)
			self.__gbf(rgb, rgb.shape[0], rgb.shape[1])
			#self.__zzf(rgb, rgb.shape[0], rgb.shape[1])
			rgb = None

		self.__surface.blit(picture, (0, 0))

	def render_preview(self):
		pic = len(self.__pics_pos) - self.__cnt_images - 1
		picture = pg.transform.scale(pg.image.load("preview/preview_{}.jpg".format(pic)).convert_alpha(), self.__screen_size)

		rgb = pg.surfarray.pixels2d(picture)
		self.__gbf(rgb, rgb.shape[0], rgb.shape[1])
		rgb = None



		self.__surface.blit(picture, (0, 0))

	def __render_result(self):
		#
		# todo render with imagemagick
		#
		# image = pg.Surface(self.__resolution)
		# image.fill(self.__bgcolor)
		# for pic in range(0, self.__num_pics):
		# 	rect = [0, 0, 0, 0]
		# 	for i in range(0, 4):
		# 		rect[i] = int(self.__pics_pos[pic][i] * self.__resolution[i & 1] / self.__view_box[i | 2])
		# 	img = pg.transform.scale(pg.image.load("{0}/image_{1}.jpg".format(self.__photopath, pic)), rect[2:])
		# 	image.blit(img, rect[:2])
		# image.blit(self.__fg, [0, 0])
		# pg.image.save(image, "{}/image.jpg".format(self.__photopath))
		pass
			
	def render(self):
		self.__surface.fill([0, 0, 0])
		
		if self.__state == ST_SLEEP:
			pass
		elif self.__state == ST_IDLE:
			self.render_live("preview/preview.jpg")
		elif self.__state == ST_SHOOT:
			
			pic = len(self.__pics_pos) - self.__cnt_images
			self.render_live("preview/preview_{0}.jpg".format(pic))
			diff = dt.datetime.now() - self.__cnt_start
			cnt = self.__countdown - diff.seconds
			if cnt > 0:
				lbl_cnt = self.__cnt_font.render(str(max(0, cnt)), 1, (200, 0, 0))
				self.__surface.blit(lbl_cnt, (400, 200))
			else:
				self.__camera.capture_image("{0}/image_{1}_{2}.jpg".format(self.__photopath, dt.datetime.now().strftime("%H%M%S"), pic))
				self.__cnt_images = self.__cnt_images - 1
				self.__state = ST_BACKVIEW
				self.__cnt_start = dt.datetime.now()

		elif self.__state == ST_BACKVIEW:
			time_back = self.cfg.getint("shooting", "backview")

			diff = dt.datetime.now() - self.__cnt_start
			diffms = int(time_back - diff.seconds * 1000 - diff.microseconds / 1000)

			if SHOW_STYLING == True:
				time_mosaic = self.cfg.getint("shooting", "backview_mosaic")
				time_anim = self.cfg.getint("shooting", "backview_animate")

				rect = pg.draw.rect(self.__surface, self.__bgcolor, [200, 0, 400, 600])
				for pic in range(0, len(self.__pics_pos) - self.__cnt_images - 1):
					pics_pos = self.__pics_pos[pic][:]
					pics_pos[0] = self.__pics_pos[pic][0] + 200
					picture = pg.transform.scale(pg.image.load("preview/preview_{0}.jpg".format(pic)), pics_pos[2:])
					self.__surface.blit(picture, pics_pos[:2])
				
				if diffms >= time_anim:
					self.render_preview()
				elif diffms >= 0:
					progress = max(0, (diffms - time_mosaic) / (time_anim - time_mosaic))
					pic = len(self.__pics_pos) - self.__cnt_images - 1
					pics_pos = self.__pics_pos[pic][:]
					pics_pos[0] = self.__pics_pos[pic][0] + 200
					coords = map(lambda x: int(x[0] * (1 - progress) + x[1] * progress), zip(pics_pos, [0, 0, self.__screen_size[0], self.__screen_size[1]]))
					#picture = pg.transform.scale(pg.image.load("preview_{0}.jpg".format(pic)), coords[2:])
					srcpic = pg.image.load("preview/preview_{}.jpg".format(pic)).convert_alpha()
					srcrgb = pg.surfarray.pixels2d(srcpic)
					picture = pg.Surface(coords[2:])
					dstrgb = pg.surfarray.pixels2d(picture)
					self.__scalef(srcrgb, srcpic.get_width(), srcpic.get_height(), dstrgb, coords[2], coords[3])
					srcrgb = None
					dstrgb = None

					self.__surface.blit(picture, coords[:2])

					self.__surface.blit(self.__fgsmall, [200, 0])

				else:
					if self.__cnt_images > 0:
						self.__state = ST_SHOOT
						self.__cnt_start = dt.datetime.now()
					else:
						self.__render_result()
						self.__state = ST_PRINT
			else:
				if diffms >= 0:
					backview_border = self.cfg.getint("shooting", "backview_border")
					pic = len(self.__pics_pos) - self.__cnt_images - 1
					pics_pos = [backview_border,backview_border,(self.__screen_width-(backview_border*2)),(self.__screen_height-(backview_border*2))]
					picture = pg.transform.scale(pg.image.load("preview/preview_{0}.jpg".format(pic)), pics_pos[2:])
					self.__surface.blit(picture, pics_pos[:2])
				else:
					if self.__cnt_images > 0:
						self.__state = ST_SHOOT
						self.__cnt_start = dt.datetime.now()
					else:

						self.__render_result()
						self.__state = ST_PRINT
		elif self.__state == ST_PRINT:	
			self.__state = ST_IDLE
			pass

	def main(self):
		self.__camera = piggyphoto.Camera()
		#self.__camera = PseudoCamera()
		
		self.__camera.leave_locked()
		self.__camera.capture_preview('preview/preview.jpg')

		# -------- Main Program Loop -----------
		while not self.__done:
			self.event_loop()
			self.render()
			pg.display.update()
			self.__clock.tick(self.__fps)

		pg.quit()


def main():
	booth = Photobooth()
	booth.main()

if __name__ == "__main__":
	main()
