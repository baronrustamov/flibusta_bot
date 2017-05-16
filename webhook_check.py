import threading
import time
from telebot.apihelper import get_webhook_info as get_webhook_info
from telebot import logger

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
            webhook = get_webhook_info(config.TOKEN)
            webhook['pending_update_count']
        except Exception as e:
            logger.debug(e)
        else:
            if int(webhook['pending_update_count']) > 10:
                self.update_webhook()
                self.update()
        if time.time() - self.last_update > 1800:
            logger.debug("<< Update webhook >>")
            try:
                self.update_webhook()
            except Exception as e:
                logger.debug(e)
            else:
                self.update()

    def update_webhook(self):
        self.bot.remove_webhook()
        time.sleep(3)
        self.bot.set_webhook(url=config.WEBHOOK_URL_BASE + config.WEBHOOK_URL_PATH,
                             certificate=open(config.WEBHOOK_SSL_CERT, 'r'))

    def stop(self):
        print('<< Closing webhook checker... >>')
        self.exit.set()
