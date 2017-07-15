import pymysql
import time
import threading
import os

from telebot import logger
import config


class Controller(threading.Thread, mysql_class.MYSQLClass):
    def __init__(self):
        threading.Thread.__init__(self)
        super(mysql_class.MYSQLClass).__init__()
        self.database = config.MYSQL_DATABASE
        self.exit = threading.Event()
        self.conn = None
        self._connect()

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
