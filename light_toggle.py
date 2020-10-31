#!/usr/bin/env python3

# this script is linked in i3/config to a keyboard key

import yeelight

for i in yeelight.discover_bulbs():
	yeelight.Bulb(i["ip"]).toggle()

