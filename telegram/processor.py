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
import traceback

import dotainput.local_config
import dotainput.stream.streamer

import boto.sqs
import boto.sqs.message


logging.basicConfig(
    filename='processor.log',
    level=logging.INFO,
    format='%(asctime)s %(message)s'
)


# TODO make these not global (encapsulate this into a class)
# Variables that need to be accessed across threads:
# Accounts of people we care about
account_ids_64_bit = {
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
}


# Map of 32-bit to 64-bit account IDs
account_lookup = dict((4294967295 & a, a) for a in account_ids_64_bit)


# YOU NEED TO ACQUIRE THE LOCK msg_lock BEFORE READING OR MODIFYING next_msg.
msg_lock = threading.Lock()
next_msg = None


# Lock for steam_conn
conn_lock = threading.Lock()
steam_conn = dotainput.stream.streamer.Streamer.create_steamapi_connection()


# Set up server for the LUA Telegram plugin
class BotHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/telegram-poll":
            #  Send reply back to client
            global msg_lock
            global next_msg
            msg_lock.acquire()
            if next_msg is not None:
                logging.info("Sending response: %s" % next_msg)
                self._send_text(next_msg)
            else:
                logging.debug("Sending response: %s" % next_msg)
                self._send_text("NONE")
            next_msg = None
            msg_lock.release()
        if self.path == "/telegram-latest":
            self._send_text("queued messages: %s" % next_msg)

    def _send_text(self, text):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(text, encoding="utf-8"))


server_address = ('', 8000)
httpd = http.server.HTTPServer(server_address, BotHandler)


# Loop that listens for client.
def listen_and_reply():
    httpd.serve_forever()


# Set up SQS connection
aws_conn = boto.sqs.connect_to_region(
    "us-west-1",
    aws_access_key_id=dotainput.local_config.AWSAccessKeyId,
    aws_secret_access_key=dotainput.local_config.AWSSecretKey)
sqs_queue = aws_conn.get_queue("dota_match_ids")
sqs_queue.set_message_class(boto.sqs.message.RawMessage)


# Loop that processes match IDs from SQS
def process_queue():
    while True:
        match_messages = sqs_queue.get_messages(10)
        messages = []
        for match_message in match_messages:
            try:
                match = json.loads(match_message.get_body())
                players = [
                    player["account_id"]
                    for player in match["players"]
                    if "account_id" in player # Bots have no account_id
                ]
                interesting_players = [
                    p for p in players if p in list(account_lookup.keys())
                ]
                if len(interesting_players) > 0:
                    player_names = [
                        lookup_name(account_lookup[aid_32])
                        for aid_32 in interesting_players
                    ]
                    message = "{players} just finished match {dotabuff_link}."\
                        .format(
                            players=",".join(str(p) for p in player_names),
                            dotabuff_link="http://www.dotabuff.com/matches/"
                                    "{match}".format(
                                        match=match["match_id"]
                                )
                        )
                    logging.info("Found interesting game: %s" % message)
                    messages.append(message)
                sqs_queue.delete_message(match_message)
            except Exception as e:
                logging.error("Match ID %s caused exception %s" %
                              (str(match_message.get_body()),
                               str(e)))
                traceback.print_last()
        if len(messages) != 0:
            global next_msg
            global msg_lock
            msg_lock.acquire()
            if next_msg is None:
                next_msg = "\n\n".join(messages)
            else:
                next_msg = next_msg + "\n\n" + "\n\n".join(messages)
            msg_lock.release()


def lookup_name(aid_64):
    conn_lock.acquire()
    steam_conn.request(
        "GET",
        "/ISteamUser/GetPlayerSummaries/v0002"
        "?key={key}&steamids={aid_64}".format(
            key=dotainput.local_config.DOTA2_API_KEY,
            aid_64=aid_64
        )
    )
    try:
        response = steam_conn.getresponse().read()
        playerinfo = json.loads(response.decode("utf-8"))
        players = playerinfo["response"]["players"]
        assert len(players) == 1, "only requested one steam ID"
        conn_lock.release()
        return players[0]["personaname"]
    except Exception as err:
        logging.error("Got an error when looking up name for %s. Error: %s" %
                      (aid_64, str(err)))
        traceback.print_last()
        conn_lock.release()
        return "Player number: %s" % aid_64


# Main functionality (this should go in a main method ...)
processing_thread_1 = threading.Thread(target=process_queue)
processing_thread_2 = threading.Thread(target=process_queue)
server_thread = threading.Thread(target=listen_and_reply)

server_thread.start()
processing_thread_1.start()
processing_thread_2.start()