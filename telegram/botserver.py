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
import threading
import urllib.parse

import dotainput.local_config
import dotainput.streamer
import dotainput.util
from telegram.bot_api import BotApi


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
}


GLIMPSE_CHAT_ID = 8999690


class BotServer:
    """
    Acts as a server for commands sent from the Telegram chats, and maintains
    the state for the bot (tracked players).
    """

    def __init__(self):
        print('Initializing server...')
        # Map of 32-bit to 64-bit account IDs for Glimpse chat.
        self.account_lookup = \
            dict((4294967295 & a, a) for a in default_account_ids_64bit)

        # Lock for steam_conn
        self._steam_conn_lock = threading.Lock()
        self._steam_conn = \
            dotainput.util.create_steamapi_connection()

        self._updatehandler_port = 443
        self.server_address = ('', self._updatehandler_port)

        class UpdateHandler(http.server.BaseHTTPRequestHandler):
            """
            HTTP Handler for requests from the telegram plugin.
            """
            def do_POST(b_self):
                print('POST RECEIVED')
                length = int(b_self.headers["Content-Length"])
                post_data = urllib.parse.parse_qs(
                    b_self.rfile.read(length).decode("utf-8")
                )
                chat = post_data["chat"]
                text = post_data["text"]
                print(chat, text)
                if text.starts_with("/help"):
                    print("HI")

            def do_GET(b_self):
                print('GET???!?')

            def do_HEAD(b_self):
                print('HEAD??!?')

            # TODO (dz) this method is old, remove it
            # def do_GET(b_self):
            #     addplayers_re = re.compile("/telegram-addplayer\?id_64=(\d+)")
            #     removeplayers_re = re.compile(
            #         "/telegram-removeplayer\?id_64=(\d+)"
            #     )
            #     try:
            #         if b_self.path == "/telegram-poll":
            #             #  Send reply back to client
            #             next_msg = self.get_next_message()
            #             if next_msg is not None:
            #                 b_self._respond(next_msg)
            #             else:
            #                 b_self._respond("NONE")
            #         elif b_self.path == "/telegram-latest":
            #             next_msg = self.peek_next_message()
            #             b_self._respond("Queued message: %s" % next_msg)
            #         elif addplayers_re.match(b_self.path):
            #             v = int(addplayers_re.match(b_self.path).group(1))
            #             logging.info("adding player %s" % v)
            #             k = 4294967295 & v
            #             name = self.lookup_name(v)
            #             self.account_lookup[k] = v
            #             b_self._respond("Added player: %s" % name)
            #         elif removeplayers_re.match(b_self.path):
            #             id_64 = \
            #                 int(removeplayers_re.match(b_self.path).group(1))
            #             k = 4294967295 & id_64
            #             self.account_lookup.pop(k, None)
            #             b_self._respond("Removed player: %s" %
            #                             self.lookup_name(id_64))
            #         elif b_self.path == "/telegram-listplayers":
            #             print("Listing players.")
            #             player_names = [
            #                 self.lookup_name(p)
            #                 for p in self.account_lookup.values()]
            #             b_self._respond("Tracked players:\n%s" %
            #                           "\n".join(player_names))
            #         else:
            #             b_self._respond("Unknown path: %s" % b_self.path)
            #     except Exception as e:
            #         b_self._respond("Internal error processing: %s" % str(e))

        self._httpd = http.server.HTTPServer(
            self.server_address,
            UpdateHandler
        )

        self._bot_api = BotApi()

    def start(self):
        """
        Register webhooks for commands from chat, and start the server to
        receive them (See BotHandler).
        """
        target_url = '45.55.20.153:%s' % self._updatehandler_port
        self._bot_api.create_webhook(target_url)
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
            self._bot_api.send_message(message)

    def lookup_name(self, aid_64):
        """
        Look up the display name of a player given their 64 bit ID.

        :param aid_64: 64 bit ID of player to look up.
        :return: Player name, or "Player <aid_64>" if an error was encountered.
        """
        self._steam_conn_lock.acquire()
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
            self._steam_conn_lock.release()
            return players[0]["personaname"]
        except Exception as err:
            logging.error(
                "Got an error when looking up name for %s. Error: %s" %
                (aid_64, str(err))
            )
            self._steam_conn_lock.release()
            self._steam_conn = \
                dotainput.util.create_steamapi_connection()
            return "Player number: %s" % aid_64
