__author__ = 'daisy'

from dota.stream import streamer
import time

s = streamer.Streamer()
s.start()
time.sleep(10)
s.stop()