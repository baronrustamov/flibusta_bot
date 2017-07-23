import threading
import time
from telebot import logger
from requests import RequestException

import config


class Checker(threading.Thread):
    def __init__(self, bot):
        threading.Thread.__init__(self)
        self.bot = bot
        self.last_update = time.time()
        self.exit = threading.Event()

    def run(self):
        self.exit.clear()
        time.sleep(30)
        while True:
            if self.exit.is_set():
                break
            self.check()
            self.exit.wait(300)

    def update(self):
        self.last_update = time.time()

    def check(self):
        try:
            info = self.bot.get_webhook_info()
        except RequestException as e:
            if config.DEBUG:
                logger.debug(e)
            self.update_webhook()
            self.update()
        else:
            if info.pending_update_count > 10:
                self.update_webhook()
                self.update()

    def update_webhook(self):
        self.bot.remove_webhook()
        time.sleep(3)
        self.bot.set_webhook(url=config.WEBHOOK_URL_BASE + config.WEBHOOK_URL_PATH,
                             certificate=open(config.WEBHOOK_SSL_CERT, 'r'))

    def stop(self):
        print('<< Closing webhook checker... >>')
        self.exit.set()
