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
        self.running = False
        self._most_recent_streamed_match = None

    def start(self, poll_interval=500):
        """
        Starts the Streamer; may not be started if it has already started.
        :param poll_interval: Number of milliseconds after which to poll for new
          matches.  Default is 500.  Valve suggests rate limiting within
          applications to at most one request per second.
        :return:
        """
        self.poll_interval = poll_interval / 1000
        self.running = True
        self._connection = http.client.HTTPConnection("api.steampowered.com")
        self._poll_thread = threading.Thread(target=self._poll_continuously)
        self._poll_thread.start()

    def stop(self):
        """
        Stops the Streamer.  Closes all connections.
        :return:
        """
        self.running = False
        self._poll_thread.join()
        self._connection.close()

    def _poll_continuously(self):
        """
        Loops continuously and polls if self._started = True.  Does not return
        until self._started = False.

        Relies on time.sleep to poll, so may fall behind if processing takes too
        long.
        """
        # TODO add logic to start at the last requested match; etc.
        while self.running:
            if self._most_recent_streamed_match is None:
                self._most_recent_streamed_match = \
                    self._get_recent_match_seq_num()
            self._connection.request(
                "GET",
                "/IDOTA2Match_570/GetMatchHistoryBySequenceNum/V001/"
                "?key={key}&start_at_match_seq_num={match_seq_num}"
                .format(
                    key=dota.local_config.DOTA2_API_KEY,
                    match_seq_num=self._most_recent_streamed_match + 1
                )
            )
            response = self._connection.getresponse()
            match_history = json.loads(response.read().decode("utf-8"))
            matches = match_history["result"]["matches"]
            self._most_recent_streamed_match = \
                matches[len(matches) - 1]["match_seq_num"]
            # TODO remove print
            print("first: {n}".format(n=matches[0]["match_seq_num"]))
            print("last:  {n}".format(n=self._most_recent_streamed_match))
            time.sleep(self.poll_interval)

    def _get_recent_match_seq_num(self):
        """
        :return: A match_seq_num of a recent match to start streaming from.
        """
        self._connection.request(
            "GET",
            "/IDOTA2Match_570/GetMatchHistory/V001/"
            "?key={key}"
            "&matches_requested=1"
            .format(
                key=dota.local_config.DOTA2_API_KEY
            )
        )
        response = self._connection.getresponse()
        decoded = json.loads(response.read().decode("utf-8"))
        return decoded["result"]["matches"][-1]["match_seq_num"]