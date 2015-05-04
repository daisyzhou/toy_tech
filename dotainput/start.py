__author__ = 'daisy'

import logging

from dotainput import streamer

logging.basicConfig(
    filename='streamer.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s'
)

s = streamer.Streamer()
s.start(poll_interval=1000)