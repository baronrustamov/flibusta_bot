# pyTelegramBotAPI lib
import telebot  # https://github.com/eternnoir/pyTelegramBotAPI
from telebot.types import (InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, InlineQuery,
                           InlineQueryResultArticle, InputTextMessageContent)

# transcription translate lib
import transliterate  # https://github.com/barseghyanartur/transliterate

# standard libs
import os
import re
import zipfile
import requests
import ssl
import logging
from logging.handlers import RotatingFileHandler
from threading import RLock

# yandex metric lib
from botan import *

# bot's modules and config files
import config
from database.library import *
from database.tables import Book
from database.users import get_user, set_lang_settings
from webhook_check import Checker

# bot's consts
ELEMENTS_ON_PAGE = 7
BOOKS_CHANGER = 5

bot = telebot.AsyncTeleBot(config.TOKEN)

logger = telebot.logger

if config.DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

work_with_hd = RLock()

logging.basicConfig(handlers=[RotatingFileHandler('../logs/bot.log', mode='a', maxBytes=25 * 1024 * 1024)])


def normalize(book: Book, type_: str) -> str:  # remove chars that don't accept in Telegram Bot API
    filename = ''
    authors = authors_by_book_id(book.id)
    if authors:
        filename = '_'.join([a.short for a in authors]) + '_-_'
    filename += book.title
    return transliterate.translit(filename, 'ru', reversed=True).replace('(', '').replace(')', '').replace(
        ',', '').replace('…', '').replace('.', '').replace('’', '').replace('!', '').replace('"', '').replace(
        '?', '').replace('»', '').replace('«', '').replace('\'', '').replace(':', '').replace('—', '-').replace(
        '/', '_').replace('№', 'N').replace(' ', '_').replace('–', '-').replace('á', 'a').replace(
        ' ', '_') + '.' + type_


def get_keyboard(page: int, pages: int, t: str) -> InlineKeyboardMarkup or None:  # make keyboard for current page
    if pages == 1:
        return None
    keyboard = InlineKeyboardMarkup()
    row = []
    if page == 1:
        row.append(InlineKeyboardButton('≻', callback_data=f'{t}_2'))
        if pages >= BOOKS_CHANGER:
            next_l = min(pages, page + BOOKS_CHANGER)
            row.append(InlineKeyboardButton(f'{next_l} >>',
                                            callback_data=f'{t}_{next_l}'))
        keyboard.row(*row)
    elif page == pages:
        if pages >= BOOKS_CHANGER:
            previous_l = max(1, page - BOOKS_CHANGER)
            row.append(InlineKeyboardButton(f'<< {previous_l}',
                                            callback_data=f'{t}_{previous_l}'))
        row.append(InlineKeyboardButton('<', callback_data=f'{t}_{pages-1}'))
        keyboard.row(*row)
    else:
        if pages >= BOOKS_CHANGER:
            next_l = min(pages, page + BOOKS_CHANGER)
            previous_l = max(1, page - BOOKS_CHANGER)

            if previous_l != page - 1:
                row.append(InlineKeyboardButton(f'<< {previous_l}',
                                                callback_data=f'{t}_{previous_l}'))

            row.append(InlineKeyboardButton('<', callback_data=f'{t}_{page-1}'))
            row.append(InlineKeyboardButton('>', callback_data=f'{t}_{page+1}'))

            if next_l != page + 1:
                row.append(InlineKeyboardButton(f'{next_l} >>',
                                                callback_data=f'{t}_{next_l}'))
            keyboard.row(*row)
        else:
            keyboard.row(InlineKeyboardButton('<', callback_data=f'{t}_{page-1}'),
                         InlineKeyboardButton('>', callback_data=f'{t}_{page+1}'))
    return keyboard


@bot.message_handler(commands=['start'])
def start(msg: Message):
    try:  # try get data that use in user share book
        _, rq = msg.text.split(' ')
    except ValueError:
        start_msg = ("Привет!\n"
                     "Этот бот поможет тебе загружать книги с флибусты.\n"
                     "Набери /help что бы получить помощь.\n"
                     "Настройки /settings.\n"
                     "Информация о боте /info.\n"
                     "Оставить отзыв /vote.\n"
                     "Материальная помощь /donate.\n")
        r = bot.reply_to(msg, start_msg)
        track_message(msg.from_user.id, msg, 'start')
        r.wait()
    else:
        type_, id_ = rq.split('_')
        bot_send_book(msg, type_, book_id=int(id_))
        track_message(msg.from_user.id, msg, 'get_shared_book')


@bot.message_handler(commands=['vote'])
def vote_foo(msg: Message):  # send vote link
    vote_msg = "https://t.me/storebot?start=flibusta_rebot"
    r = bot.reply_to(msg, vote_msg)
    track_message(msg.from_user.id, msg, 'vote')
    r.wait()


@bot.message_handler(commands=['help'])
def help_foo(msg: Message):  # send help message
    help_msg = ("Лучше один раз увидеть, чем сто раз услышать.\n"
                "https://youtu.be/HV6Wm87D6_A")
    r = bot.reply_to(msg, help_msg)
    track_message(msg.from_user.id, msg, 'help')
    r.wait()


@bot.message_handler(commands=['info'])
def info(msg: Message):  # send information message
    info_msg = (f"Каталог книг от {config.DB_DATE}\n"
                "Связь с создателем проекта @kurbezz\n"
                f"Версия бота {config.VERSION}\n"
                "Github: https://goo.gl/V0Iw7m")
    r = bot.reply_to(msg, info_msg, disable_web_page_preview=True)
    track_message(msg.from_user.id, msg, 'info')
    r.wait()


@bot.callback_query_handler(func=lambda x: re.search(r'b_([0-9])+', x.data) is not None)
def bot_search_by_title(callback: CallbackQuery):  # search books by title
    msg = callback.message
    if len(msg.reply_to_message.text) < 4:
        bot.edit_message_text('Слишком короткий запрос!', chat_id=msg.chat.id, message_id=msg.message_id)
    user = get_user(callback.from_user.id)
    books = books_by_title(msg.reply_to_message.text, user)
    if not books:
        bot.edit_message_text('Книги не найдены!', chat_id=msg.chat.id, message_id=msg.message_id)
        track_callback(msg.from_user.id, callback, 'search_by_title')
        return
    r_action = bot.send_chat_action(msg.chat.id, 'typing')
    try:
        page = int(callback.data.split('_')[1])
    except ValueError as err:
        logger.debug(err)
        return
    page_max = len(books) // ELEMENTS_ON_PAGE + (1 if not len(books) % ELEMENTS_ON_PAGE == 0 else 1)
    msg_text = ''.join(to_send_book(book) for book in books[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]) + \
               f'<code>Страница {page}/{page_max}</code>'
    r = bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                              reply_markup=get_keyboard(page, page_max, 'b'))
    track_callback(msg.from_user.id, callback, 'search_by_title')
    r_action.wait()
    r.wait()


@bot.callback_query_handler(func=lambda x: re.search(r'ba_([0-9])+', x.data) is not None)
def bot_books_by_author(callback: CallbackQuery):  # search books by author (use callback query)
    msg = callback.message
    id_ = int(msg.reply_to_message.text.split('_')[1])
    user = get_user(callback.from_user.id)
    books = books_by_author(id_, user)
    if not books:
        bot.edit_message_text('Книги не найдены!', chat_id=msg.chat.id, message_id=msg.message_id)
        track_callback(msg.from_user.id, callback, 'search_by_title')
        return
    page = int(callback.data.split('_')[1])
    r_action = bot.send_chat_action(msg.chat.id, 'typing')
    page_max = len(books) // ELEMENTS_ON_PAGE + (1 if not len(books) % ELEMENTS_ON_PAGE == 0 else 0)
    msg_text = ''.join([to_send_book(book, authors=[author_by_id(id_)])
                        for book in books[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]]) + \
               f'<code>Страница {page}/{page_max}</code>'
    r = bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                              reply_markup=get_keyboard(page, page_max, 'ba'))
    track_callback(msg.from_user.id, callback, 'books_by_author')
    r_action.wait()
    r.wait()


@bot.callback_query_handler(func=lambda x: re.search(r'a_([0-9])+', x.data) is not None)
def bot_search_by_authors(callback: CallbackQuery):  # search authors
    msg = callback.message
    authors = authors_by_name(msg.reply_to_message.text)
    if not authors:
        r = bot.send_message(msg.chat.id, 'Автор не найден!')
        track_callback(msg.from_user.id, callback, 'search_by_authors')
        r.wait()
        return
    page = int(callback.data.split('_')[1])
    r_action = bot.send_chat_action(msg.chat.id, 'typing')
    page_max = len(authors) // ELEMENTS_ON_PAGE + (1 if not len(authors) % ELEMENTS_ON_PAGE == 0 else 0)
    msg_text = ''.join(author.to_send for author in authors[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]) \
               + f'<code>Страница {page}/{page_max}</code>'
    r = bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                              reply_markup=get_keyboard(page, page_max, 'a'))
    track_callback(msg.from_user.id, callback, 'search_by_authors')
    r_action.wait()
    r.wait()


@bot.message_handler(regexp='/a_([0-9])+')
def bot_books_by_author(msg: Message):  # search books by author (use messages)
    id_ = int(msg.text.split('_')[1])
    user = get_user(msg.from_user.id)
    books = books_by_author(id_, user)
    if not books:
        r = bot.reply_to(msg, 'Ошибка! Книги не найдены!')
        track_message(msg.from_user.id, msg, 'books_by_author')
        r.wait()
        return
    r_action = bot.send_chat_action(msg.chat.id, 'typing')
    page_max = len(books) // ELEMENTS_ON_PAGE + (1 if not len(books) % ELEMENTS_ON_PAGE == 0 else 0)
    msg_text = ''.join([to_send_book(book, authors=[author_by_id(id_)])
                        for book in books[0:ELEMENTS_ON_PAGE]]) + f'<code>Страница {1}/{page_max}</code>'
    r = bot.reply_to(msg, msg_text, parse_mode='HTML', reply_markup=get_keyboard(1, page_max, 'ba'))
    track_message(msg.from_user.id, msg, 'books_by_author')
    r_action.wait()
    r.wait()


@bot.message_handler(commands=['donate'])
def donation(msg: Message):  # send donation information
    text = "О том, как поддержать проект можно узнать "' \
    ''<a href="http://telegra.ph/Pozhertvovaniya-02-11">тут</a>.'
    bot.reply_to(msg, text, parse_mode='HTML').wait()


@bot.message_handler(regexp='^(fb2|epub|mobi|djvu|pdf|doc)_[0-9]+$')
def get_book_handler(message: Message):
    type_, book_id = message.text.split(' ')
    return bot_send_book(message, type_, book_id=book_id)


def send_by_file_id(foo):  # try to send document by file_id
    def try_send(msg, type_, book_id=None):
        if not book_id:
            book_id = int(msg.text.split('_')[1])
        file_id = get_file_id(book_id, type_)  # try to get file_id from BD
        if file_id:
            return foo(msg, type_, book_id=book_id, file_id=file_id.file_id)  # if file_id not found
        else:
            return foo(msg, type_, book_id=book_id)

    return try_send


def download(type_, book_id, msg, with_proxies: bool = False):
    kwargs = {"url": ''}
    if with_proxies:
        kwargs.update({"proxies": config.PROXIES})
        kwargs["url"] = "http://flibustahezeous3.onion/b/"
    else:
        kwargs["url"] = "http://flibusta.is/b/"

    if type_ in ['fb2', 'epub', 'mobi']:
        kwargs["url"] += f"{book_id}/{type_}"
    else:
        kwargs["url"] += f"{book_id}/download"

    try:
        r = requests.get(**kwargs)
    except requests.exceptions.ConnectionError as err:
        telebot.logger.exception(err)
        if with_proxies:
            bot.reply_to(msg, "Ошибка подключения к серверу! Попробуйте позднее.").wait()
        else:
            return download(type_, book_id, msg, with_proxies=True)
    else:
        if 'text/html' in r.headers['Content-Type']:
            if with_proxies:
                bot.reply_to(msg, "Ошибка! Попробуйте через пару минут :(").wait()
            else:
                return download(type_, book_id, msg, with_proxies=True)
        return r


@send_by_file_id
def bot_send_book(msg: Message, type_: str, book_id=None, file_id=None):  # download from flibusta server and
    track_message(msg.from_user.id, msg, 'download')  # send document to user
    if book_id is None:
        book_id = int(msg.text.split('_')[1])
    book = book_by_id(book_id)
    if not book:
        bot.reply_to(msg, 'Книга не найдена!').wait()
        return
    caption = '\n'.join([author.normal_name for author in authors_by_book_id(book.id)]) + book.title
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('Поделиться',
                             switch_inline_query=f"share_{book_id}"))
    if file_id:
        try:
            bot.send_document(msg.chat.id, file_id, reply_to_message_id=msg.message_id,
                              caption=caption, reply_markup=markup).wait()
        except Exception as err:
            logger.debug(err)
        else:
            return

    r = download(type_, book_id, msg)
    if r is None: return

    r_action = bot.send_chat_action(msg.chat.id, 'upload_document')

    with work_with_hd:
        filename = normalize(book, type_)
        with open(filename, 'wb') as f:
            f.write(r.content)
        if type_ in ['fb2', 'pdf']:  # if type "fb2" or "pdf" extract file from archive
            os.rename(filename, filename.replace(type_, 'zip'))
            try:
                zip_obj = zipfile.ZipFile(filename.replace(type_, 'zip'))
            except zipfile.BadZipFile as err:
                logger.debug(err)
                return
            extracted = None
            for name in zip_obj.namelist():  # type: str
                if type_ in name.lower():
                    extracted = name
            zip_obj.extract(extracted)
            zip_obj.close()
            os.rename(extracted, filename)
            os.remove(filename.replace(type_, 'zip'))
        try:
            res = bot.send_document(msg.chat.id, open(filename, 'rb'), reply_to_message_id=msg.message_id,
                                    caption=caption, reply_markup=markup).wait()
        except requests.ConnectionError as err:
            logger.debug(err)
        else:
            if isinstance(res, tuple):
                print(res)
            set_file_id(book_id, type_, res.document.file_id)
        finally:
            os.remove(filename)
    r_action.wait()


@bot.inline_handler(func=lambda x: re.search(r'share_([0-9])+$', x.query) is not None)
def bot_inline_share(query: InlineQuery):  # share book to others user with use inline query
    track_inline(query.from_user.id, query, 'share_book')
    book_id = int(query.query.split('_')[1])
    book = book_by_id(book_id)
    if book is None:
        return
    bot.answer_inline_query(query.id, [InlineQueryResultArticle('1', 'Поделиться',
                                                                InputTextMessageContent(to_share_book(book),
                                                                                        parse_mode='HTML',
                                                                                        disable_web_page_preview=True),
                                                                )]).wait()


@bot.inline_handler(func=lambda query: query.query)
def bot_inline_hand(query: InlineQuery):  # inline search
    track_inline(query.from_user.id, query, 'inline_search')
    user = get_user(query.from_user.id)
    books = books_by_title(query.query, user)
    if not books:
        bot.answer_inline_query(query.id, [InlineQueryResultArticle(
            '1', 'Книги не найдены!', InputTextMessageContent('Книги не найдены!')
        )]
                                ).wait()
        return
    book_index = 1
    result = list()
    for book in books[0:min(len(books) - 1, 50 - 1)]:
        result.append(InlineQueryResultArticle(str(book_index), book.title,
                                               InputTextMessageContent(to_share_book(book), parse_mode='HTML',
                                                                       disable_web_page_preview=True)))
        book_index += 1
    bot.answer_inline_query(query.id, result).wait()


def make_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user = get_user(user_id)
    keyboard = InlineKeyboardMarkup()
    if not user.allow_uk:
        keyboard.row(InlineKeyboardButton('Украинский: 🅾 выключен!', callback_data='uk_on'))
    else:
        keyboard.row(InlineKeyboardButton('Украинский: ✅ включен!', callback_data='uk_off'))
    if not user.allow_be:
        keyboard.row(InlineKeyboardButton('Белорусский: 🅾 выключен!', callback_data='be_on'))
    else:
        keyboard.row(InlineKeyboardButton('Белорусский: ✅ включен!', callback_data='be_off'))
    return keyboard


@bot.message_handler(commands=['settings'])
def settings(msg: Message):  # send settings message
    keyboard = make_settings_keyboard(msg.from_user.id)
    bot.reply_to(msg, 'Настройки: ', reply_markup=keyboard).wait()


@bot.callback_query_handler(func=lambda x: re.search(r'^(uk|be)_(on|off)$', x.data) is not None)
def lang_setup(query: CallbackQuery):  # language settings
    lang, set_ = query.data.split('_')
    set_lang_settings(query.from_user.id, lang, set_ == "on")
    keyboard = make_settings_keyboard(query.from_user.id)
    bot.edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                  reply_markup=keyboard).wait()


@bot.message_handler(commands=["random"])
def random_book(msg: Message):
    bot.reply_to(msg, to_send_book(get_random_book()))


@bot.message_handler(func=lambda message: True)
def search(msg: Message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('По названию', callback_data='b_1'),
                 InlineKeyboardButton('По авторам', callback_data='a_1')
                 )
    r = bot.reply_to(msg, 'Поиск: ', reply_markup=keyboard)
    track_message(msg.from_user.id, msg, 'receive_message')
    r.wait()


bot.remove_webhook()

if config.WEBHOOK:
    from aiohttp import web

    app = web.Application()

    checker = Checker(bot)


    async def handle(request):
        if request.match_info.get('token') == config.TOKEN:
            request_body_dict = await request.json()
            update = telebot.types.Update.de_json(request_body_dict)
            bot.process_new_updates([update])
            return web.Response()
        else:
            return web.Response(status=403)


    app.router.add_post('/{token}/', handle)

    bot.set_webhook(url=config.WEBHOOK_URL_BASE + config.WEBHOOK_URL_PATH,
                    certificate=open(config.WEBHOOK_SSL_CERT, 'r'))

    checker.start()

    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.load_cert_chain(config.WEBHOOK_SSL_CERT, config.WEBHOOK_SSL_PRIV)

    web.run_app(app,
                host=config.WEBHOOK_LISTEN,
                port=config.WEBHOOK_PORT,
                ssl_context=context)

    checker.stop()

    bot.remove_webhook()
else:
    bot.polling(none_stop=True)
