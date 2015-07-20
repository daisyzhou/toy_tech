import http
import requests
import dotainput.local_config

class BotApi(object):
    """
    A wrapper for the specific parts dota-stalker-bot needs from the telegram
    API: https://core.telegram.org/bots/api
    """
    def __init__(self):
        self._token = dotainput.local_config.BOT_API_KEY

    def create_webhook(self, target_url):
        r = requests.get('https://api.telegram.org/bot%s/setWebhook?url=%s' % (self._token, target_url))
        print('Webhook requested. response: %s' % r)

    def send_message(self, chat_id, message):
        r = requests.get('https://api.telegram.org/bot%s/send_message?chat_id=%s&text=%s' % (chat_id, message))
        print('Message sent. response: %s' % r)