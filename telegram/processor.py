#
# Dota info server in Python
#   Binds REP socket to tcp://*:5555
#   Expects b"get_new_msg" from client, replies with the message for the client
#   to push to telegram, OR b"NONE" if there is no message.
#
#   Expected implementation:
#   * reads from SQS of all matches and filters them according to a static list
#   * generates the messages that need to be sent, and whenever the client
#     polls, concatenates them if there are more than one, and sends it back to
#     the client.

import http.server
import json
import logging
import re
import threading

import dotainput.local_config
import dotainput.streamer
import dotainput.util


logging.basicConfig(
    filename='processor.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s'
)


# Variables that need to be accessed across threads:
# Accounts of people we care about
default_account_ids_64bit = {
    76561197997336439,  # dzbug
    76561198111698495,  # instapicking PL
    76561198159705679,  # dz's unranked smurf
    76561198189446861,  # fox (Paul's smurf)
    76561198143189634,  # Allen's smurf
    76561197961774985,  # Franklin
    76561197979611387,  # Sidd
    76561197970342819,  # Aaron
    76561197993621342,  # Gilbert (Sloth)
    76561198013393830,  # RD
    76561197999544403,  # Hellfire
    76561198034473797,  # lutz
    76561198168192504,  # Gilbert's smurf (vvx)
    76561197972444552,  # Angra
    76561198089947113,  # Allen's smurf (shadow friend)
    76561197971215286,  # shadowing
}


class Processor:
    """
    Acts as a server for requests from the lua telegram plugin.

    Call the process_match method to process a match and potentially add it to
    the messages that will be sent via telegram.
    """

    def __init__(self):
        # Map of 32-bit to 64-bit account IDs
        self.account_lookup = \
            dict((4294967295 & a, a) for a in default_account_ids_64bit)

        # YOU NEED TO ACQUIRE THE LOCK msg_lock TO READ/MODIFY next_msg.
        self._msg_lock = threading.Lock()
        self._next_msg = None

        # Lock for steam_conn
        self._conn_lock = threading.Lock()
        self._steam_conn = \
            dotainput.util.create_steamapi_connection()

        self.server_address = ('', 8000)

        class BotHandler(http.server.BaseHTTPRequestHandler):
            """
            HTTP Handler for requests from the telegram plugin.
            """

            def do_GET(b_self):
                addplayers_re = re.compile("/telegram-addplayer\?id_64=(\d+)")
                removeplayers_re = re.compile(
                    "/telegram-removeplayer\?id_64=(\d+)"
                )
                try:
                    if b_self.path == "/telegram-poll":
                        #  Send reply back to client
                        next_msg = self.get_next_message()
                        if next_msg is not None:
                            b_self._respond(next_msg)
                        else:
                            b_self._respond("NONE")
                    elif b_self.path == "/telegram-latest":
                        next_msg = self.peek_next_message()
                        b_self._respond("Queued message: %s" % next_msg)
                    elif addplayers_re.match(b_self.path):
                        v = int(addplayers_re.match(b_self.path).group(1))
                        logging.info("adding player %s" % v)
                        k = 4294967295 & v
                        name = self.lookup_name(v)
                        self.account_lookup[k] = v
                        b_self._respond("Added player: %s" % name)
                    elif removeplayers_re.match(b_self.path):
                        id_64 = \
                            int(removeplayers_re.match(b_self.path).group(1))
                        k = 4294967295 & id_64
                        self.account_lookup.pop(k, None)
                        b_self._respond("Removed player: %s" %
                                        self.lookup_name(id_64))
                    elif b_self.path == "/telegram-listplayers":
                        print("Listing players.")
                        player_names = [
                            self.lookup_name(p)
                            for p in self.account_lookup.values()]
                        b_self._respond("Tracked players:\n%s" %
                                      "\n".join(player_names))
                    else:
                        b_self._respond("Unknown path: %s" % b_self.path)
                except Exception as e:
                    b_self._respond("Internal error processing: %s" % str(e))

            def _respond(b_self, text):
                logging.debug("Sending response: %s" % text)
                b_self.send_response(200)
                b_self.send_header('Content-type', 'text/html')
                b_self.end_headers()
                b_self.wfile.write(bytes(text, encoding="utf-8"))

        self._httpd = http.server.HTTPServer(
            self.server_address,
            BotHandler)

    def start(self):
        """
        Starts the HTTP server in a different thread.  Cannot be stopped ...
        yet.
        """
        threading.Thread(target=self._httpd.serve_forever).start()

    def process_match(self, match):
        """
        Process a single match.

        :param match: JSON representation of a match (from steam API).
        """
        players = [
            player["account_id"]
            for player in match["players"]
            if "account_id" in player # Bots have no account_id
        ]
        interesting_players = [
            p for p in players if p in list(self.account_lookup.keys())
        ]
        if len(interesting_players) > 0:
            player_names = [
                self.lookup_name(self.account_lookup[aid_32])
                for aid_32 in interesting_players
            ]
            message = "{players} just finished match {dotabuff_link}"\
                .format(
                    players=",".join(str(p) for p in player_names),
                    dotabuff_link="http://www.dotabuff.com/matches/"
                            "{match}".format(
                                match=match["match_id"]
                        )
                )
            logging.info("Found interesting game: %s" % message)
            self._msg_lock.acquire()
            if self._next_msg is None:
                self._next_msg = message
            else:
                self._next_msg = self._next_msg + "\n\n" + message
            self._msg_lock.release()

    def lookup_name(self, aid_64):
        """
        Look up the display name of a player given their 64 bit ID.

        :param aid_64: 64 bit ID of player to look up.
        :return: Player name, or "Player <aid_64>" if an error was encountered.
        """
        self._conn_lock.acquire()
        self._steam_conn.request(
            "GET",
            "/ISteamUser/GetPlayerSummaries/v0002"
            "?key={key}&steamids={aid_64}".format(
                key=dotainput.local_config.DOTA2_API_KEY,
                aid_64=aid_64
            )
        )
        try:
            response = self._steam_conn.getresponse().read()
            playerinfo = json.loads(response.decode("utf-8"))
            players = playerinfo["response"]["players"]
            assert len(players) == 1, "only requested one steam ID"
            self._conn_lock.release()
            return players[0]["personaname"]
        except Exception as err:
            logging.error(
                "Got an error when looking up name for %s. Error: %s" %
                (aid_64, str(err))
            )
            self._conn_lock.release()
            self._steam_conn = \
                dotainput.util.create_steamapi_connection()
            return "Player number: %s" % aid_64

    def get_next_message(self):
        """
        :return: The next message to be the response to telegram-poll, or None
        if no message is to be sent.  Resets the next message to None afterward.
        """
        self._msg_lock.acquire()
        response = self._next_msg
        self._next_msg = None
        self._msg_lock.release()
        return response

    def peek_next_message(self):
        """
        :return: the next message to be sent, without resetting it to None.
        """
        self._msg_lock.acquire()
        response = self._next_msg
        self._msg_lock.release()
        return response