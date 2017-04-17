import pymysql
from telebot import logger

import config


class MYSQLClass:
    def __init__(self):
        self.conn = None
        self.database = None

    def __del__(self):
        if self.conn:
            self.conn.close()

    def _connect(self):
        while True:
            try:
                self.conn = pymysql.connect(host=config.MYSQL_HOST,
                                            database=self.database,
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
            self.conn.ping(reconnect=True)
            return None

    def fetchall(self, sql, args):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, args)
                res = cursor.fetchall()
            return res
        except pymysql.Error as err:
            logger.debug(err)
            self.conn.ping(reconnect=True)
            return None