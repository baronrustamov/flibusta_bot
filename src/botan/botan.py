import requests
import json
from telebot.types import Message, CallbackQuery, InlineQuery
import config

TRACK_URL = 'https://api.botan.io/track'
SHORTENER_URL = 'https://api.botan.io/s/'


def track(token, uid, message, name='Message'):
    try:
        r = requests.post(
            TRACK_URL,
            params={"token": token, "uid": uid, "name": name},
            data=json.dumps(message),
            headers={'Content-type': 'application/json'},
        )
        return r.json()
    except requests.exceptions.Timeout:
        # set up for a retry, or continue in a retry loop
        return False
    except (requests.exceptions.RequestException, ValueError) as e:
        # catastrophic error
        print(e)
        return False


def shorten_url(url, botan_token, user_id):
    try:
        return requests.get(SHORTENER_URL, params={
            'token': botan_token,
            'url': url,
            'user_ids': str(user_id),
        }).text
    except requests.exceptions:
        return url


def track_message(uid, msg: Message, name):  # botan tracker
    return track(config.BOTAN_TOKEN, uid,
                 {msg.from_user.id: {
                     'user': {
                         'username': msg.from_user.username,
                         'first_name': msg.from_user.first_name,
                         'last_name': msg.from_user.last_name
                     },
                     'text': msg.text
                 }
                 },
                 name=name)


def track_callback(uid, callback: CallbackQuery, name):
    return track(config.BOTAN_TOKEN, uid,
                 {callback.from_user.id: {
                     'user': {
                         'username': callback.from_user.username,
                         'first_name': callback.from_user.first_name,
                         'last_name': callback.from_user.last_name
                     },
                     'text': callback.message.text
                 }
                 },
                 name=name)


def track_inline(uid, inline: InlineQuery, name):
    return track(config.BOTAN_TOKEN, uid,
                 {inline.from_user.id: {
                     'user': {
                         'username': inline.from_user.username,
                         'first_name': inline.from_user.first_name,
                         'last_name': inline.from_user.last_name
                     },
                     'text': inline.query
                 }
                 },
                 name=name)
