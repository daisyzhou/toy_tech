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
import http
import json
import threading

import dotainput.local_config

import boto.sqs
import zmq

# TODO make these not global (encapsulate this into a class)
# Variables that need to be accessed across threads:
# Accounts of people we care about
account_ids = {
    76561197997336439,  # dzbug
    76561198111698495,  # instapicking PL
    76561198159705679,  # dz's unranked smurf
    71754942,  # random TODO remove
    76561198101955961,
    76561198043613137,
    76561198038807629,
}
# YOU NEED TO ACQUIRE THE LOCK msg_lock BEFORE READING OR MODIFYING next_msg.
msg_lock = threading.Lock()
next_msg = None


# Set up server to zmq (client is LUA Telegram plugin)
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")


# Loop that listens for client.
def listen_and_reply():
    while True:
        #  Wait for next request from client
        message = socket.recv()
        print("Received request: %s" % message)

        #  Send reply back to client
        global msg_lock
        global next_msg
        msg_lock.acquire()
        if next_msg is not None:
            socket.send_string(next_msg)
        else:
            socket.send_string("NONE")
        print("Sent response: %s" % next_msg)
        next_msg = None
        msg_lock.release()


# Set up SQS connection
aws_conn = boto.sqs.connect_to_region(
    "us-west-1",
    aws_access_key_id=dotainput.local_config.AWSAccessKeyId,
    aws_secret_access_key=dotainput.local_config.AWSSecretKey)
sqs_queue = aws_conn.get_queue("dota_match_ids")


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
                interesting_players = [p for p in players if p in account_ids]
                if len(interesting_players) > 0:
                    message = "{players} just finished match {dotabuff_link}."\
                        .format(
                            players=",".join(str(p) for p in interesting_players),
                            dotabuff_link=
                                "http://www.dotabuff.com/matches/{match}".format(
                                    match=match["match_id"]
                                )
                        )
                    messages.append(message)
                sqs_queue.delete_message(match_message)
            except Exception:
                print("Match ID %s caused exception." % str(match_message.get_body()))
        if len(messages) != 0:
            global next_msg
            global msg_lock
            msg_lock.acquire()
            if next_msg is None:
                next_msg = "\n\n".join(messages)
            else:
                next_msg = next_msg + "\n\n" + "\n\n".join(messages)
            msg_lock.release()


# Main functionality (this should go in a main method ...)
processing_thread_1 = threading.Thread(target=process_queue)
processing_thread_2 = threading.Thread(target=process_queue)
server_thread = threading.Thread(target=listen_and_reply)

server_thread.start()
processing_thread_1.start()
processing_thread_2.start()