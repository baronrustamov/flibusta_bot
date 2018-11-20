from chatbase import Message
from telebot.util import AsyncTask
import telebot.types as types

from config import CHATBASE_API_KEY


def analyze(intent: str, reply_msg=False):
    def make_wrapper(foo):
        def wrapper(*args, **kwargs):
            if isinstance(args[0], types.Message):
                if reply_msg:
                    _analyze(args[0].reply_to_message.text, intent, args[0].from_user.id)
                else:
                    _analyze(args[0].text, intent, args[0].from_user.id)
            elif isinstance(args[0], types.CallbackQuery):
                _analyze(args[0].message.text, intent, args[0].from_user.id)
            return foo(*args, **kwargs)
        return wrapper
    return make_wrapper


def _analyze(message: str, intent: str, user_id: int or str):
    msg = Message(
        api_key=CHATBASE_API_KEY,
        platform="telegram",
        message=message,
        intent=intent,
        user_id=user_id if type(user_id) == str else str(user_id),
        version="3"
    )
    return AsyncTask(msg.send).wait()
