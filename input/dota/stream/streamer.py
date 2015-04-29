__author__ = 'daisy'

import dota.local_config

import boto.sqs
import boto.sqs.message

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

    def start(self, poll_interval=1000):
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
            aws_access_key_id=dota.local_config.AWSAccessKeyId,
            aws_secret_access_key=dota.local_config.AWSSecretKey)
        self._queue = self._aws_conn.get_queue("dota_match_ids")
        self._connection = http.client.HTTPConnection(
            "api.steampowered.com",
            timeout=5 
        )
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
                    key=dota.local_config.DOTA2_API_KEY,
                    match_seq_num=self._most_recent_streamed_match + 1
                )
            )
            response = self._connection.getresponse()
            match_history = json.loads(response.read().decode("utf-8"))
            json_matches = match_history["result"]["matches"]
            if len(json_matches) == 0:
                continue
            self._most_recent_streamed_match = \
                json_matches[-1]["match_seq_num"]
<<<<<<< HEAD:input/dota/stream/streamer.py
            # TODO remove print
            print("first: {n}".format(n=json_matches[0]["match_seq_num"]))
            print("last:  {n}".format(n=self._most_recent_streamed_match))
=======
>>>>>>> af96c8f... Attempting to run for real:dotainput/stream/streamer.py

            match_ids = [m["match_id"] for m in json_matches]

            # Batch the match_ids into batches of 10 to send to SQS
            i = 0
            while i < len(match_ids):
                j = 0
                messages = []
                while (j < 10) and (j + i < len(match_ids)):
                    m_id = match_ids[i+j]
                    messages.append((m_id, m_id, 0))
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
                key=dota.local_config.DOTA2_API_KEY
            )
        )
        response = self._connection.getresponse()
        decoded = json.loads(response.read().decode("utf-8"))
        return decoded["result"]["matches"][-1]["match_seq_num"]