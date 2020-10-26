import os
import time
import datetime

import schedule

# pip install suntime
# https://github.com/SatAgro/suntime
import suntime
# https://stackoverflow.com/questions/38986527/sunrise-and-sunset-time-in-python

# pip install yeelight
import yeelight
"""
command documentation: 
	https://www.yeelight.com/download/Yeelight_Inter-Operation_Spec.pdf
package documentation:
	https://yeelight.readthedocs.io/en/latest/index.html
"""

LATITUDE = 32.0853
LONGITUDE = 34.781769

brightness_high = 100
brightness_low  = 1

SLEEP_TIME = datetime.time(22, 0)

LOG_FILE = open(os.path.join(os.path.dirname(__file__), "log.log"), "a")

# utils
def log(s):
	print(s)
	LOG_FILE.write(s)
	LOG_FILE.write('\n')
	LOG_FILE.flush()


class LimitedList(list):
	def __init__(self, limit=100, *args, **kwargs):
		super(LimitedList, self).__init__(*args, **kwargs)
		self.limit = limit

	def append(self, *args, **kwargs):
		super().append(*args, **kwargs)
		# assuming only one object is appended at a time
		if len(self) > self.limit:
			self.pop(0)


class Bulbs(object):
	def __init__(self, *ips):
		self.init_bulbs(ips)

		self.old_properties = LimitedList()

	def init_bulbs(self, ips=()):
		if ips:
			self.ips = ips
		else:
			bulbs = yeelight.discover_bulbs()
			self.ips = sorted([i["ip"] for i in bulbs])

		self.bulbs = [yeelight.Bulb(ip) for ip in ips]

	def _foreach(self, method, *args, **kwargs):
		res = [
			method(b, *args, **kwargs)
			for b in self.bulbs
		]
		return res


	def get_properties(self, property_name=None):
		# retrieve new ones
		self.last_properties = self._foreach(yeelight.Bulb.get_properties)
		# store the time of retrieval
		now = datetime.datetime.now()
		for d in self.last_properties:
			d["time"] = now

		# save the last properties for documentation
		self.old_properties.append(self.last_properties)

		# return the requested value
		if property_name is None:
			return self.last_properties
		else:
			return [d[property_name] for d in self.last_properties]

	def turn_on(self):
		log("[*] bulbs - turning ON")
		return self._foreach(yeelight.Bulb.turn_on)
	def turn_off(self):
		log("[*] bulbs - turning OFF")
		return self._foreach(yeelight.Bulb.turn_off)
	def toggle(self):
		log("[*] bulbs - toggling")
		return self._foreach(yeelight.Bulb.toggle)
	def set_brightness(self, br):
		log(f"[*] bulbs - setting brightness - {br}")
		return self._foreach(yeelight.Bulb.set_brightness, br)

	def increase_brightness(self, amount=1):
		# get current brightness
		current_brightness = self.get_properties("bright")
		# increase the brightness for each bulb
		for bulb, bright in zip(self.bulbs, current_brightness):
			bulb.set_brightness(bright + amount)
	def decrease_brightness(self, amount=1):
		return self.increase_brightness(amount=-amount)


class SuntimeScheduler(object):
	def __init__(self, bulbs):
		self.sun = suntime.Sun(LATITUDE, LONGITUDE)
		self.bulbs = bulbs

		# set default values
		self.set_brightness_limits()

		# schedule the first job
		self.daily_reset()

	def loop(self):
		while True:
			schedule.run_pending()
			time.sleep(1)

	# should be scheduled every morning
	def daily_reset(self):
		log("[*] scheduler - daily reset")
		# remove all schedules
		schedule.clear()
		# reschedule self
		schedule.every().day.at("07:00").do(self.daily_reset)
		# schedule today's dim
		self.schedule_dim()

	def schedule_dim(self, sleep_time: datetime.time = SLEEP_TIME, date : datetime.date = None):
		"""
		This schedules decrease_brightness EVERY DAY.
		It is highly recommended to call 'schedule.clear()' before calling this function
		"""
		# get sunset time
		sunset = self.get_sunset_time(date)
		log(f"[*] scheduler - today's sunset - {sunset.strftime('%Y.%m.%d %H:%M:%S')}")
		# calculate chunks
		self.calculate_dim_time(sleep_time, date)

		# turn on at sunset
		schedule.every().day.at(sunset.strftime("%H:%M:%S")).do(self.turn_on)

		# schedule chunks
		for i in range(1, self.chunks+1):
			# get chunk time
			time_obj = sunset + datetime.timedelta(seconds=self.time_per_chunk*i)
			# convert to str format
			time_str = time_obj.strftime("%H:%M:%S")
			# schedule the brightness
			log(f"    [*] scheduler - br {self.brightness_high - i:02d} at {time_str}")
			schedule.every().day.at(time_str).do(self.bulbs.set_brightness, self.brightness_high - i)

	#
	# general utils
	#
	def get_sunrise_time(self, date : datetime.date = None):
		if date is None:
			return self.sun.get_sunrise_time().astimezone()
		else:
			return self.sun.get_local_sunrise_time(date).astimezone()
	def get_sunset_time(self, date : datetime.date = None):
		if date is None:
			return self.sun.get_sunset_time().astimezone()
		else:
			return self.sun.get_local_sunset_time(date).astimezone()

	def turn_on(self):
		self.bulbs.turn_on()
		self.bulbs.set_brightness(self.brightness_high)

	#
	# scheduling utils
	#
	def calculate_dim_time(self, sleep_time : datetime.time, date : datetime.date = None):
		"""
		return time from sunset to sleep_time in seonds
		"""
		# convert sleep time so sleep datetime
		sleep_time = datetime.datetime.combine(datetime.date.today(), sleep_time)

		# calculate time between sunset to sleep
		self.total_dim_time = (
			sleep_time.astimezone()
			 -
			self.get_sunset_time(date)
		).total_seconds()
		return self.total_dim_time

	def set_brightness_limits(self, high=100, low=1):
		self.brightness_high = high
		self.brightness_low  = low

	@property
	def chunks(self):
		return self.brightness_high - self.brightness_low
	
	@property
	def time_per_chunk(self):
		return self.total_dim_time // self.chunks

def main():
	bulbs = Bulbs()
	ss = SuntimeScheduler(bulbs)
	ss.loop()
	LOG_FILE.close()

if __name__ == '__main__':
	main()
