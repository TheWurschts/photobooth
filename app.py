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
import subprocess
import RPi.GPIO as GPIO
import max7219.led as led
from PIL import Image


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
ST_PRESHOOT = 2
ST_SHOOT = 3
ST_BACKVIEW = 4
ST_PREPRINT = 5
ST_PRINT = 6


GPIO.setmode(GPIO.BCM)



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


class MAXNumber:
	def __init__(self):
		self.__device = led.sevensegment()
		self.__save = [0,0,0]
		self.write()
	def setDownNumber(self,numberInt):
		number = str(numberInt)
		self.__save[2]=int(number)
		self.write()
	def setTopNumber(self, numberInt):
		number = str(numberInt)
		
		if(len(number)>1):
			self.__save[0]=int(number[0])
			self.__save[1]=int(number[1])
		else:
			self.__save[0]=int(0);
			self.__save[1]=int(number[0])
		self.write()
	def allPlusOne(self):
		for i, val in enumerate(self.__save):
			if(val == 9):
				self.__save[i]=0
			else:
				self.__save[i] = self.__save[i] + 1
		self.write()
	def write(self):
		outstring = int(str(self.__save[0])+str(self.__save[1])+str(self.__save[2]))
		self.__device.write_number(deviceId=0, value=outstring)



class PBGPIO:
	def __init__(self, pinid, gpiotype):
		self.__state = False;
		self.__pinid = pinid;
		if(gpiotype == 'IN'):
			GPIOTYPE = GPIO.IN
		elif (gpiotype =='OUT'):
			GPIOTYPE = GPIO.OUT
		GPIO.setup(self.__pinid, GPIOTYPE)
		if (gpiotype =='OUT'):
			self.reset()
	def toggle(self):
		if (self.__state == True):
			self.reset()
		else:
			self.set();
	def set(self):
		GPIO.output(self.__pinid,True)
		self.__state = True
	def reset(self):
		GPIO.output(self.__pinid,False)
		self.__state = False
	def get(self):
		if (GPIO.input(self.__pinid)):
			return True
		else:
			return False

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
		self.__blink_start = dt.datetime.now() # blink timestamp
		self.__blink_sec = 0.5

		self.__numberdisplay = MAXNumber()
		
		self.__startupDateTimeString = dt.datetime.now().strftime("%H%M%S")
		self.__serienCount = 0

		#config IN/OUT
		self.__pin_dome_in = PBGPIO(17,'IN')
		self.__pin_orange_top_in = PBGPIO(22,'IN')
		self.__pin_orange_bottom_in = PBGPIO(4,'IN')
		self.__pin_green_in = PBGPIO(27,'IN')

		self.__pin_dome_out = PBGPIO(18,'OUT')
		self.__pin_orange_top_out = PBGPIO(23,'OUT')
		self.__pin_orange_bottom_out = PBGPIO(24,'OUT')
		self.__pin_green_out = PBGPIO(25,'OUT')

		# load config
		self.cfg = cfgp.ConfigParser()
		self.cfg.read("booth.cfg")

		self.__cfgs = self.cfg.items("shooting")

		self.__countdown = self.cfg.getint("shooting", "countdown")
		self.__print_ctdn = self.cfg.getint("shooting", "print_screen")

		self.__lastCollage = ''
		self.__absScriptPath = os.path.abspath(os.path.dirname(sys.argv[0]))

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


		pg.mouse.set_visible(False)
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
		self.__bgimagepath = self.cfg.get(style, "bgimage")
		self.__view_box = map(int, self.cfg.get(style, "box").split(","))
		self.__resolution = map(int, self.cfg.get(style, "resolution").split(","))

		# self.__fgsmall = pg.transform.scale(pg.image.load(self.cfg.get(style, "fgimage")), self.__view_box[2:])
		# self.__fg = pg.transform.scale(pg.image.load(self.cfg.get(style, "fgimage")), self.__resolution)

	def show(self, file):
		picture = pg.image.load(file)
		self.__surface.blit(picture, (30, 40))
		pg.display.flip()

	def showFullscreen(self, file):
		
		picture = pg.transform.scale(pg.image.load(file).convert_alpha(), self.__screen_size)
		self.__surface.blit(picture, (0, 0))
		pg.display.flip()

	def showFullscreenWithoutResize(self, file):
		
		picture = pg.image.load(file)
		self.__surface.blit(picture, (0, 0))
		pg.display.flip()

	def event_loop(self):
		if(self.__pin_dome_in.get()):
			if self.__state == ST_IDLE:
				self.__state = ST_PRESHOOT

		if self.__pin_green_in.get():
			if self.__state == ST_PREPRINT:
				self.__state == ST_PRINT
		if self.__pin_orange_top_in.get():
			if self.__state == ST_PREPRINT:
				self.__count_prints = self.__count_prints +1
				if(self.__count_prints>3):
					self.__count_prints = 3
		if self.__pin_orange_bottom_in.get():
			if self.__state == ST_PREPRINT:
				self.__count_prints = self.__count_prints -1
				if(self.__count_prints<1):
					self.__count_prints = 1


		for event in pg.event.get():
			if event.type == pg.KEYDOWN:
				if event.key == ord('q'):
					self.__done = True
				elif event.key == ord('a'):
					if self.__state == ST_IDLE:
						self.__state = ST_PRESHOOT
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
		
		print(dt.datetime.now())
		outpath = "{0}/collage_{1}_{2}.jpg".format(self.__photopath, self.__startupDateTimeString, self.__serienCount)
		self.__lastCollage = outpath
		pstring = list()
		background = Image.open('{0}/{1}'.format(self.__absScriptPath, self.__bgimagepath))

		for pic in range(0, self.__num_pics):
			pass
			foreground = Image.open('{0}/{1}/image_{2}_{3}_{4}.jpg'.format(self.__absScriptPath, self.__photopath, self.__startupDateTimeString, self.__serienCount, pic))
			size = (int(self.__pics_pos[pic][2])-int(self.__pics_pos[pic][0])), (int(self.__pics_pos[pic][3])-int(self.__pics_pos[pic][1]))
			foreground.thumbnail(size,Image.ANTIALIAS)
			background.paste(foreground, (int(self.__pics_pos[pic][0]), int(self.__pics_pos[pic][1])))


		background.save('{}'.format(outpath))
		size = (self.__screen_width, self.__screen_height)
		background.thumbnail(size,Image.ANTIALIAS)
		background.save('{}'.format('tmp/preview.jpg'))
		print(dt.datetime.now())
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
		# pass
			
	def render(self):
		self.__surface.fill([0, 0, 0])
		
		if self.__state == ST_SLEEP:
			pass
		elif self.__state == ST_IDLE:
			diff = dt.datetime.now() - self.__blink_start
			cnt = self.__blink_sec - diff.seconds
			if cnt < 0:
				self.__pin_dome_out.toggle()
				# self.__pin_green_out.toggle()
				# self.__pin_orange_bottom_out.toggle()
				# self.__pin_orange_top_out.toggle()
				# self.__numberdisplay.allPlusOne()
				self.__blink_start = dt.datetime.now()

			self.render_live("preview/preview.jpg")
		elif self.__state == ST_PRESHOOT:
			self.__state = ST_SHOOT
			self.__serienCount = self.__serienCount+1
			now = dt.datetime.now()
			self.__photopath = dt.datetime.now().strftime("photos/%Y-%m-%d")
			self.__mkdir(self.__photopath)
			self.__cnt_images = len(self.__pics_pos)
			self.__cnt_start = dt.datetime.now()
		elif self.__state == ST_SHOOT:
			diff = dt.datetime.now() - self.__cnt_start
			pic = len(self.__pics_pos) - self.__cnt_images
			self.render_live("preview/preview_{0}.jpg".format(pic))
			diff = dt.datetime.now() - self.__cnt_start
			cnt = self.__countdown - diff.seconds
			if cnt > 0:
				self.__numberdisplay.setTopNumber(cnt)
				lbl_cnt = self.__cnt_font.render(str(max(0, cnt)), 1, (200, 0, 0))
				self.__surface.blit(lbl_cnt, (300, 40))
			else:

				
				self.__numberdisplay.setTopNumber(0)
				self.__camera.capture_image("{0}/image_{1}_{2}_{3}.jpg".format(self.__photopath, self.__startupDateTimeString, self.__serienCount, pic))
				self.__numberdisplay.setDownNumber(pic+1)
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
						self.__state = ST_PREPRINT
						self.__blink_start = dt.datetime.now()
						self.__print_start = dt.datetime.now()
						self.__count_prints = 1
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
						self.__state = ST_PREPRINT
						self.__blink_start = dt.datetime.now()
						self.__print_start = dt.datetime.now()
						self.__count_prints = 1
		elif self.__state == ST_PREPRINT:
			# self.render_live(self.__lastCollage)
			# self.showFullscreen(self.__lastCollage)

			self.showFullscreenWithoutResize('tmp/preview.jpg')
			
			diff = dt.datetime.now() - self.__blink_start
			cnt = self.__blink_sec - diff.seconds
			if cnt < 0:
				# self.__pin_dome_out.toggle()
				self.__pin_green_out.toggle()
				self.__camera.capture_preview('tmp/preview.jpg')
				self.__blink_start = dt.datetime.now()
			# self.__state = ST_IDLE

			diff = dt.datetime.now() - self.__print_start
			cnt = self.__print_ctdn - diff.seconds
			# print(cnt)

			if cnt < 0:
				self.__state = ST_IDLE
				self.__pin_green_out.reset()
				pass
			else:
				#todo show text
				pass
			
			
			self.__numberdisplay.setDownNumber(self.__count_prints)
		elif self.__state == ST_PRINT:
			# subprocess.call("lp -d {0} {1}".format(self.cfg.get("booth", "printername"), self.__lastCollage), shell=True)
			print('print')
			self.__state = ST_IDLE


	def main(self):
		# self.__camera = piggyphoto.Camera()
		self.__camera = PseudoCamera()
		
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
