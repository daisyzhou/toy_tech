__author__ = 'daisy'

from dotainput.stream import streamer
import time

s = streamer.Streamer()
s.start(poll_interval=1000)