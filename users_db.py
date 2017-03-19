import pymysql
from telebot import logger

import config


class Database:
    def __init__(self):
        self.conn = None
        self.__connect()

    def __connect(self):
        while True:
            try:
                self.conn = pymysql.connect(host=config.MYSQL_HOST,
                                            database=config.USERS_DATABASE,
                                            user=config.MYSQL_USER,
                                            password=config.MYSQL_PASSWORD)
            except pymysql.Error as err:
                logger.debug(err)
            else:
                return

    def fetchone(self, sql, args):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, args)
                return cursor.fetchone()
        except pymysql.Error as err:
            logger.debug(err)
            self.conn.ping(reconnect=True)
            return None

    def fetchall(self, sql, args):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, args)
                return cursor.fetchall()
        except pymysql.Error as err:
            logger.debug(err)
            self.conn.ping(reconnect=True)
            return None

    def __create_lang_settings(self, user_id):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute('INSERT INTO settings (user_id, allow_uk, allow_be) VALUES (%s, %s, %s)',
                               (user_id, 0, 0))
            self.conn.commit()
        except pymysql.Error as err:
            logger.debug(err)
            self.conn.ping(reconnect=True)

    def set_land_settings(self, user_id, lang, status):
        try:
            with self.conn.cursor() as cursor:
                if lang == 'uk':
                    cursor.execute('UPDATE settings SET allow_uk = %s WHERE settings.user_id = %s',
                                   (status, user_id))
                elif lang == 'be':
                    cursor.execute('UPDATE settings SET allow_be = %s WHERE settings.user_id = %s',
                                   (status, user_id))
            self.conn.commit()
        except pymysql.Error as err:
            logger.debug(err)
            self.conn.ping(reconnect=True)

    def get_lang_settings(self, user_id):
        try:
            res = self.fetchone("SELECT allow_uk, allow_be FROM settings WHERE user_id=%s", (user_id,))
        except pymysql.Error as err:
            logger.debug(err)
            self.conn.ping(reconnect=True)
            return {'allow_uk': 0, 'allow_be': 0}
        else:
            if res:
                return {'allow_uk': res[0], 'allow_be': res[1]}
            else:
                self.__create_lang_settings(user_id)
                return {'allow_uk': 0, 'allow_be': 0}
