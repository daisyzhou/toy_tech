import dotainput.local_config
import dotainput.util
from telegram.botserver import BotServer

import http.client
import json
import logging
import socket
import threading
import time


class Streamer:
    """
    Processes matches from the Dota 2 web API
    (see http://dev.dota2.com/showthread.php?t=58317 and
    https://wiki.teamfortress.com/wiki/WebAPI#Dota_2) and calls process on each.

    This class is not thread-safe.
    """

    def __init__(self):
        self.running = False
        self._most_recent_streamed_match = None
        self._processor = BotServer()

    def start(self, poll_interval=100):
        """
        Starts the Streamer; may not be started if it is already running.
        :param poll_interval: Number of milliseconds after which to poll for new
          matches.  Default is 1000.  Valve suggests rate limiting within
          applications to at most one request per second.
        """
        self.running = True
        self._connection = dotainput.util.create_steamapi_connection()
        self.poll_interval = poll_interval / 1000
        self._poll_thread = threading.Thread(target=self._poll_continuously)
        self._poll_thread.start()
        self._processor.start()

    def stop(self):
        """
        Stops the Streamer.  Closes all connections.
        :return:
        """
        self.running = False
        self._poll_thread.join()
        self._connection.close()

    def _reconnect_connection(self, num_attempts=0):
        """
        Reconnect the steam API connection, because sometimes it fails...
        Retries up to 'num_attempts' times, waiting for self.poll_interval in
        between each retry.  'num_attempts' of -1 signifies to retry forever.

        Raises the socket.timeout if it times out for num_attempts times.

        :param num_attempts: Number of times to attempt to retry.  Default 10.
        """
        try:
            self._connection.close()
            self._connection.connect()
            time.sleep(self.poll_interval)
        # Except all exceptions... I don't have time for this
        except (socket.timeout, ConnectionRefusedError, Exception) as e:
            if num_attempts == -1:
                logging.warning("Reconnect failed, retrying forever.")
                self._reconnect_connection(num_attempts=-1)
            elif num_attempts > 1:
                logging.warning("Reconnect failed, retrying %d more times" %
                                (num_attempts - 1))
                self._reconnect_connection(num_attempts - 1)
            else:
                logging.error("Reconnect failed.")
                raise e

    def _poll_continuously(self):
        """
        Loops continuously and polls if self._started = True.  Does not return
        until self._started = False.

        Relies on time.sleep to poll, so may fall behind if processing takes too
        long.
        """
        while self.running:
            if self._most_recent_streamed_match is None:
                self._most_recent_streamed_match = \
                    self._get_recent_match_seq_num()
            self._connection.request(
                "GET",
                "/IDOTA2Match_570/GetMatchHistoryBySequenceNum/V001/"
                "?key={key}&start_at_match_seq_num={match_seq_num}"
                .format(
                    key=dotainput.local_config.DOTA2_API_KEY,
                    match_seq_num=self._most_recent_streamed_match + 1
                )
            )
            try:
                response = self._connection.getresponse().read()
            except http.client.BadStatusLine:
                logging.info("Received empty response (BadStatusLine), "
                      "waiting & continuing...")
                self._reconnect_connection(num_attempts=-1)
                continue
            except socket.timeout:
                logging.info("Connection timed out, "
                      "waiting & continuing...")
                self._reconnect_connection(num_attempts=-1)
                continue
            except ConnectionResetError:
                logging.info("Connection reset, waiting & continuing...")
                self._reconnect_connection(num_attempts=-1)

            try:
                match_history = json.loads(response.decode("utf-8"))
            except ValueError as e:
                logging.error(
                    "Error while decoding JSON response: %s. Error:\n%s"
                    % (response, e)
                )
                continue
            if "result" not in match_history:
                logging.warning("JSON Malformed result: %s" % match_history)
                continue
            if "matches" not in match_history["result"]:
                # Reached end for now.
                logging.info("No new matches, continuing ...")
                time.sleep(self.poll_interval)
                continue

            json_matches = match_history["result"]["matches"]
            if len(json_matches) == 0:
                logging.warning("No matches in 'matches' field of result, this "
                                "is unexpected. json received was:\n%s" %
                                match_history)
                continue
            self._most_recent_streamed_match = \
                json_matches[-1]["match_seq_num"]

            for match in json_matches:
                self._processor.process_match(match)
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
                key=dotainput.local_config.DOTA2_API_KEY
            )
        )
        response = self._connection.getresponse()
        decoded = json.loads(response.read().decode("utf-8"))
        time.sleep(self.poll_interval)  # Rate limit for the API
        return decoded["result"]["matches"][-1]["match_seq_num"]
