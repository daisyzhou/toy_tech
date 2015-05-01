__author__ = 'daisy'

import dotainput.local_config

import boto.sqs
import boto.sqs.message

import http.client
import json
import socket
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
        Starts the Streamer; may not be started if it is already running.
        :param poll_interval: Number of milliseconds after which to poll for new
          matches.  Default is 500.  Valve suggests rate limiting within
          applications to at most one request per second.
        :return:
        """
        self.running = True
        self._aws_conn = boto.sqs.connect_to_region(
            "us-west-1",
            aws_access_key_id=dotainput.local_config.AWSAccessKeyId,
            aws_secret_access_key=dotainput.local_config.AWSSecretKey)
        self._queue = self._aws_conn.get_queue("dota_match_ids")
        self._connection = self.create_steamapi_connection()
        self.poll_interval = poll_interval / 1000
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
        self._aws_conn.close()

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
                print("Received empty response (BadStatusLine), "
                      "waiting & continuing...")
                self._connection.close()
                self._connection.connect()
                time.sleep(self.poll_interval)
                continue
            except socket.timeout:
                print("Connection timed out, "
                      "waiting & continuing...")
                self._connection.close()
                self._connection.connect()
                time.sleep(self.poll_interval)
                continue

            match_history = json.loads(response.decode("utf-8"))
            if "matches" not in match_history["result"]:
                # Reached end for now.
                print("No new matches, continuing ...")
                time.sleep(self.poll_interval)
                continue

            json_matches = match_history["result"]["matches"]
            if len(json_matches) == 0:
                print("No matches in 'matches' field of result, this is "
                      "unexpected.")
                continue
            self._most_recent_streamed_match = \
                json_matches[-1]["match_seq_num"]

            match_ids = [m["match_id"] for m in json_matches]

            # Batch the matches into batches of 10 to send to SQS
            i = 0
            while i < len(json_matches):
                j = 0
                messages = []
                while (j < 10) and (j + i < len(match_ids)):
                    match = json_matches[i + j]
                    messages.append((match["match_id"], json.dumps(match), 0))
                    j += 1
                self._queue.write_batch(messages)
                i += j + 1
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

    @staticmethod
    def create_steamapi_connection():
        return http.client.HTTPConnection(
            "api.steampowered.com",
            timeout=10
        )