#!/usr/bin/env python
 
import max7219.led as led

device = led.sevensegment()
# device.write_number(deviceId=0, value=888)
device.write_number(deviceId=0, value=888)