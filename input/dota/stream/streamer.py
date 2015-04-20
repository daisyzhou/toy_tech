__author__ = 'daisy'

import dota.local_config
import http.client
import json
import threading
import time


class Streamer:
    """
    Processes matches from the Dota 2 web API
    (see http://dev.dota2.com/showthread.php?t=58317 and
    https://wiki.teamfortress.com/wiki/WebAPI#Dota_2) and transforms polling
    requests into a stream.

    This class is not thread-safe.
    """

    def __init__(self):
        self._started = False

    def start(self, poll_interval=500):
        """
        Starts the Streamer; may not be started if it has already started.
        :param poll_interval: Number of milliseconds after which to poll for new
          matches.  Default is 500.  Valve suggests rate limiting within
          applications to at most one request per second.
        :return:
        """
        self.poll_interval = poll_interval / 1000
        self._started = True
        self._connection = http.client.HTTPConnection("api.steampowered.com")
        self._poll_thread = threading.Thread(target=self._poll_continuously)
        self._poll_thread.start()

    def stop(self):
        """
        Stops the Streamer.  Closes all connections.
        :return:
        """
        self._started = False
        self._poll_thread.join()
        self._connection.close()

    def _poll_continuously(self):
        """
        Loops continuously and polls if self._started = True.  Does not return
        until self._started = False.
        """
        # TODO add logic to start at the last requested match; etc.
        while (self._started == True):
            self._connection.request(
                "GET",
                "/IDOTA2Match_570/GetMatchHistory/V001/?key={key}".format(
                    key=dota.local_config.DOTA2_API_KEY)
            )
            response = self._connection.getresponse()
            match_history = json.loads(response.read().decode("utf-8"))
            print(match_history["result"]["total_results"])  # TODO remove print
            time.sleep(self.poll_interval)
