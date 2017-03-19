import pymysql
import time
import threading
import os

from telebot import logger
import config



class Controller(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.exit = threading.Event()
        self.conn = None
        self.__connect()

    def __connect(self):
        while True:
            try:
                self.conn = pymysql.connect(host=config.MYSQL_HOST,
                                            database=config.MYSQL_DATABASE,
                                            user=config.MYSQL_USER,
                                            password=config.MYSQL_PASSWORD,
                                            charset='utf8mb4')
            except pymysql.Error as err:
                logger.debug(err)
            else:
                return

    def fetchone(self, sql, args):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, args)
                res = cursor.fetchone()
            return res
        except pymysql.Error as err:
            logger.debug(err)
            return None

    def get_life_time(self, filename):
        life_time = self.fetchone('SELECT time FROM fileLifeTime WHERE filename=%s', (filename,))
        if life_time:
            return life_time[0]
        else:
            return None

    def delete_file(self, file):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute('DELETE FROM fileLifeTime WHERE filename=%s', (file,))
            self.conn.commit()
        except pymysql.Error as err:
            logger.debug(err)
        os.remove(config.FTP_DIR + '/' + file)

    def run(self):
        self.exit.clear()
        while True:
            if self.exit.is_set():
                break
            files = os.listdir(config.FTP_DIR)
            files.remove('download.php')
            for file in files:
                life_time = self.get_life_time(file)
                if life_time:
                    if time.time() > life_time.timestamp():
                        self.delete_file(file)
                else:
                    os.remove(config.FTP_DIR + '/' + file)
            self.exit.wait(60)

    def stop(self):
        print('<< Closing ftp controller... >>')
        self.exit.set()
