__author__ = 'daisy'

from dotainput.stream import streamer

import logging

logging.basicConfig(
    filename='streamer.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s'
)

s = streamer.Streamer()
s.start(poll_interval=1000)