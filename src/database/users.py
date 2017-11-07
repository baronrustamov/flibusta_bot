from pony.orm import *
from .tables import User, u_db

import config

u_db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD,
          db=config.USERS_DATABASE)
u_db.generate_mapping(create_tables=True)


@db_session
def set_lang_settings(id_, lang, status):
    user = select(u for u in User if u.id == id_)[:]
    if user:
        user = user[0]
    else:
        user = User(id=id_)
    if lang == 'uk':
        user.allow_uk = status
    if lang == 'be':
        user.allow_be = status


@db_session
def get_user(id_):
    user = select(u for u in User if u.id == id_)[:]
    if user:
        return user[0]
    else:
        return User(id=id_)
