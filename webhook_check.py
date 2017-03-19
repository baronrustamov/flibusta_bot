import threading
import time
from telebot.apihelper import get_webhook_info as get_webhook_info

import config


class Checker(threading.Thread):
    def __init__(self, bot):
        threading.Thread.__init__(self)
        self.bot = bot
        self.exit = threading.Event()

    def run(self):
        self.exit.clear()
        time.sleep(30)
        while True:
            if self.exit.is_set():
                break
            self.check()
            self.exit.wait(90)

    def check(self):
        webhook = get_webhook_info(config.TOKEN)
        try:
            webhook['pending_update_count']
        except KeyError:
            pass
        else:
            if int(webhook['pending_update_count']) > 10:
                self.bot.remove_webhook()
                time.sleep(0.3)
                self.bot.set_webhook(url=config.WEBHOOK_URL_BASE + config.WEBHOOK_URL_PATH,
                                     certificate=open(config.WEBHOOK_SSL_CERT, 'r'))

    def stop(self):
        print('<< Closing webhook checker... >>')
        self.exit.set()
