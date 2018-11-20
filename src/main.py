import os
import re
import time

from telebot import AsyncTeleBot
import telebot.types as ttypes
import analytics

from aiohttp import web

import config
import strings
from send import Sender

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

from db.models import TelegramUser, Settings
from django.db.models import ObjectDoesNotExist

proxies = {
    'http': 'socks5://kurbezz:97340098@18.222.81.181:1080',
    'https': 'socks5://kurbezz:97340098@18.222.81.181:1080'
}

# apihelper.proxy = proxies


bot = AsyncTeleBot(config.BOT_TOKEN, num_threads=4)
sender = Sender(bot)


last_update = time.time()


def update_user(msg: ttypes.Message):
    try:
        user = TelegramUser.objects.get(user_id=msg.from_user.id)
        user.first_name = msg.from_user.first_name
        user.last_name = msg.from_user.last_name
        user.username = msg.from_user.username
    except ObjectDoesNotExist:
        user = TelegramUser.objects.create(
            user_id=msg.from_user.id, first_name=msg.from_user.first_name, 
            last_name=msg.from_user.last_name, username=msg.from_user.username
        )
    user.save()


@bot.message_handler(commands=["start"])
def start_handler(msg: ttypes.Message):
    update_user(msg)
    try:
        file_type, book_id = (msg.text.split(' ')[1].split("_"))
        sender.send_book(msg, int(book_id), file_type)
        analytics._analyze(msg.text, "get_shared_book", msg.from_user.id)
    except (ValueError, IndexError):
        bot.reply_to(msg, strings.start_message.format(name=msg.from_user.first_name))
        analytics._analyze(msg.text, "start", msg.from_user.id)


@bot.message_handler(commands=["help"])
@analytics.analyze("help")
def help_handler(msg: ttypes.Message):
    bot.reply_to(msg, strings.help_msg)


@bot.message_handler(commands=["info"])
@analytics.analyze("info")
def info_handler(msg: ttypes.Message):
    bot.reply_to(msg, strings.info_msg, disable_web_page_preview=True)


@bot.message_handler(commands=["vote"])
@analytics.analyze("vote")
def vote_handler(msg: ttypes.Message):
    bot.reply_to(msg, strings.vote_msg)


def make_settings_keyboard(user_id: int) -> ttypes.InlineKeyboardMarkup:
    user = TelegramUser.objects.get(user_id=user_id)
    if user.settings is None:
        user.settings = Settings.objects.create()
        user.settings.save()
        user.save()
    keyboard = ttypes.InlineKeyboardMarkup()
    if not user.settings.allow_uk:
        keyboard.row(ttypes.InlineKeyboardButton("Украинский: 🅾 выключен!", callback_data="uk_on"))
    else:
        keyboard.row(ttypes.InlineKeyboardButton("Украинский: ✅ включен!", callback_data="uk_off"))
    if not user.settings.allow_be:
        keyboard.row(ttypes.InlineKeyboardButton("Белорусский: 🅾 выключен!", callback_data="be_on"))
    else:
        keyboard.row(ttypes.InlineKeyboardButton("Белорусский: ✅ включен!", callback_data="be_off"))
    return keyboard


@bot.message_handler(commands=["settings"])
@analytics.analyze("settings")
def settings(msg: ttypes.Message):
    update_user(msg)
    bot.reply_to(msg, "Настройки: ", reply_markup=make_settings_keyboard(msg.from_user.id))


@bot.callback_query_handler(func=lambda x: re.search(r"^(uk|be)_(on|off)$", x.data) is not None)
@analytics.analyze("settings_change")
def lang_setup(query: ttypes.CallbackQuery):
    user = TelegramUser.objects.get(user_id=query.from_user.id)
    lang, set_ = query.data.split('_')
    if lang == "uk":
        user.settings.allow_uk = (set_ == "on")
    elif lang == "be":
        user.settings.allow_be = (set_ == "on")
    user.settings.save()
    keyboard = make_settings_keyboard(query.from_user.id)
    bot.edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                  reply_markup=keyboard)


@bot.message_handler(regexp='/a_([0-9])+')
@analytics.analyze("get_books_by_author")
def search_books_by_author(msg: ttypes.Message):
    update_user(msg)
    sender.search_books_by_author(msg, int(msg.text.split('_')[1]), 1)


@bot.message_handler(commands=['donate'])
@analytics.analyze("donation")
def donation(msg: ttypes.Message):
    bot.reply_to(msg, strings.donate_msg, parse_mode='HTML')


@bot.message_handler(regexp='^/(fb2|epub|mobi|djvu|pdf|doc)_[0-9]+$')
@analytics.analyze("download")
def get_book_handler(msg: ttypes.Message):
    file_type, book_id = msg.text.replace('/', '').split('_')
    sender.send_book(msg, int(book_id), file_type)


@bot.message_handler(func=lambda message: True)
@analytics.analyze("new_search_query")
def search(msg: ttypes.Message):
    update_user(msg)
    keyboard = ttypes.InlineKeyboardMarkup()
    keyboard.add(
        ttypes.InlineKeyboardButton("По названию", callback_data="b_1"),
        ttypes.InlineKeyboardButton("По авторам", callback_data="a_1")
        )
    bot.reply_to(msg, "Поиск: ", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda x: re.search(r'^b_([0-9]+)', x.data) is not None)
@analytics.analyze("search_book_by_title")
def search_books_by_title(callback: ttypes.CallbackQuery):
    msg: ttypes.Message = callback.message
    if not msg.reply_to_message or not msg.reply_to_message.text:
        return bot.send_message("Ошибка :( Попробуйте еще раз!")
    sender.search_books(msg, int(callback.data.split('_')[1]))


@bot.callback_query_handler(func=lambda x: re.search(r'^a_([0-9])+', x.data) is not None)
@analytics.analyze("search_authors")
def search_authors(callback: ttypes.CallbackQuery):
    msg: ttypes.Message = callback.message
    if not msg.reply_to_message or not msg.reply_to_message.text:
        return bot.send_message("Ошибка :( Попробуйте еще раз!")
    sender.search_authors(msg, int(callback.data.split('_')[1]))


@bot.callback_query_handler(func=lambda x: re.search(r'^ba_([0-9]+)', x.data) is not None)
@analytics.analyze("get_books_by_author")
def get_books_by_author(callback: ttypes.CallbackQuery):
    msg: ttypes.Message = callback.message
    if not msg.reply_to_message or not msg.reply_to_message.text:
        return bot.send_message("Ошибка :( Попробуйте еще раз!")
    update_user(msg.reply_to_message)
    sender.search_books_by_author(msg, int(msg.reply_to_message.text.split('_')[1]), int(callback.data.split('_')[1]))


@bot.callback_query_handler(
    func=lambda x: re.search(r'remove_cache', x.data) is not None)
@analytics.analyze("remove_cache")
def remove_cache(callback: ttypes.CallbackQuery):
    msg = bot.send_message(callback.from_user.id, strings.cache_removed)
    reply_to: ttypes.Message = callback.message.reply_to_message
    file_type, book_id = reply_to.text.replace('/', '').split('_')
    sender.remove_cache(file_type, int(book_id))
    msg.wait()
    sender.send_book(reply_to, int(book_id), file_type)


async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        bot.process_new_updates([ttypes.Update.de_json(request_body_dict)])
        global last_update
        last_update = time.time()
        return web.Response()
    else:
        return web.Response(status=403)


check_can_run = True


def check_last_update():
    global last_update
    global check_can_run

    def update():
        global last_update

        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH)
        last_update = time.time()

    while check_can_run:
        if time.time() - last_update > 15 * 60:
            update()
        time.sleep(3 * 60)


if __name__ == "__main__":
    bot.remove_webhook()

    app = web.Application()
    app.router.add_post('/{token}/', handle)

    WEBHOOK_URL_BASE = config.WEBHOOK_HOST
    WEBHOOK_URL_PATH = "/{}/".format(config.BOT_TOKEN)

    bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH)

    # check_thread = threading.Thread(target=check_last_update)
    # check_thread.start()

    web.run_app(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT
    )

    # check_can_run = False
    # check_thread.join()
