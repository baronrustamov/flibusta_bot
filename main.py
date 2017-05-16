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
import time
import logging
import requests
import shutil

# yandex metric lib
import botan

# bot's modules and config files
import config
from catalog import Library, Book
from debug_utils import timeit
from users_db import Database
from ftp_file_controller import Controller
from webhook_check import Checker

# bot's consts
ELEMENTS_ON_PAGE = 7
BOOKS_CHANGER = 5

bot = telebot.TeleBot(config.TOKEN)
lib = Library()
db = Database()

logger = telebot.logger

if config.DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


def track(uid, msg, name):  # botan tracker
    if type(msg) is Message:
        return botan.track(config.BOTAN_TOKEN, uid,
                           {'message': {
                               'user': {
                                   'id': msg.from_user.id,
                                   'first_name': msg.from_user.first_name,
                                   'username': msg.from_user.username,
                                   'last_name': msg.from_user.last_name
                               },
                               'text': msg.text
                           }
                           },
                           name=name)
    if type(msg) is CallbackQuery:
        return botan.track(config.BOTAN_TOKEN, uid,
                           {'callback_query': {
                               'user': {
                                   'id': msg.from_user.id,
                                   'first_name': msg.from_user.first_name,
                                   'username': msg.from_user.username,
                                   'last_name': msg.from_user.last_name
                               },
                               'text': msg.message.reply_to_message.text
                           }
                           },
                           name=name)
    if type(msg) is InlineQuery:
        return botan.track(config.BOTAN_TOKEN, uid,
                           {'inline_query': {
                               'user': {
                                   'id': msg.from_user.id,
                                   'first_name': msg.from_user.first_name,
                                   'username': msg.from_user.username,
                                   'last_name': msg.from_user.last_name
                               },
                               'query': msg.query
                           }},
                           name=name)


def normalize(book: Book, type_: str) -> str:  # remove chars that don't accept in Telegram Bot API
    filename = ''
    if book.author:
        if book.author.short:
            filename += book.author.short + '_-_'
    filename += book.title
    filename = transliterate.translit(filename, 'ru', reversed=True)
    filename = filename.replace('(', '').replace(')', '').replace(',', '').replace('…', '').replace('.', '')
    filename = filename.replace('’', '').replace('!', '').replace('"', '').replace('?', '').replace('»', '')
    filename = filename.replace('«', '').replace('\'', '').replace(':', '')
    filename = filename.replace('—', '-').replace('/', '_').replace('№', 'N')
    filename = filename.replace(' ', '_').replace('–', '-').replace('á', 'a').replace(' ', '_')
    return filename + '.' + type_


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
        bot.reply_to(msg, start_msg)
        track(msg.from_user.id, msg, 'start')
    else:
        type_, id_ = rq.split('_')
        send_book(msg, type_, book_id=int(id_))
        track(msg.from_user.id, msg, 'get_shared_book')


@bot.message_handler(commands=['vote'])
def vote_foo(msg: Message):  # send vote link
    vote_msg = "https://t.me/storebot?start=flibusta_rebot"
    bot.reply_to(msg, vote_msg)
    track(msg.from_user.id, msg, 'vote')


@bot.message_handler(commands=['help'])
def help_foo(msg: Message):  # send help message
    help_msg = ("Лучше один раз увидеть, чем сто раз услышать.\n"
                "https://youtu.be/HV6Wm87D6_A")
    bot.reply_to(msg, help_msg)
    track(msg.from_user.id, msg, 'help')


@bot.message_handler(commands=['info'])
def info(msg: Message):  # send information message
    info_msg = (f"Каталог книг от {config.DB_DATE}\n"
                "Связь с создателем проекта @kurbezz\n"
                f"Версия бота {config.VERSION}\n"
                "Github: https://goo.gl/V0Iw7m")
    bot.reply_to(msg, info_msg, disable_web_page_preview=True)
    track(msg.from_user.id, msg, 'info')


@bot.callback_query_handler(func=lambda x: re.search(r'b_([0-9])+', x.data) is not None)
@timeit
def search_by_title(callback: CallbackQuery):  # search books by title
    msg = callback.message
    if len(msg.reply_to_message.text) < 4:
        bot.edit_message_text('Слишком короткий запрос!', chat_id=msg.chat.id, message_id=msg.message_id)
    user_sets = db.get_lang_settings(callback.from_user.id)
    books = lib.book_by_title(msg.reply_to_message.text, user_sets)
    if books is None:
        bot.edit_message_text('Книги не найдены!', chat_id=msg.chat.id, message_id=msg.message_id)
        track(msg.from_user.id, callback, 'search_by_title')
        return
    bot.send_chat_action(msg.chat.id, 'typing')
    try:
        _, page = callback.data.split('_')
    except ValueError as err:
        logger.debug(err)
        return
    page = int(page)
    if len(books) % ELEMENTS_ON_PAGE == 0:
        page_max = len(books) // ELEMENTS_ON_PAGE
    else:
        page_max = len(books) // ELEMENTS_ON_PAGE + 1
    msg_text = ''
    for book in books[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]:
        msg_text += book.to_send
    msg_text += f'<code>Страница {page}/{page_max}</code>'
    keyboard = get_keyboard(page, page_max, 'b')
    if keyboard:
        bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                              reply_markup=keyboard)
    else:
        bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML')
    track(msg.from_user.id, callback, 'search_by_title')


@bot.callback_query_handler(func=lambda x: re.search(r'ba_([0-9])+', x.data) is not None)
@timeit
def books_by_author(callback: CallbackQuery):  # search books by author (use callback query)
    msg = callback.message
    _, id_ = msg.reply_to_message.text.split('_')
    id_ = int(id_)
    user_sets = db.get_lang_settings(callback.from_user.id)
    books = lib.book_by_author(id_, user_sets)
    if books is None:
        bot.edit_message_text('Книги не найдены!', chat_id=msg.chat.id, message_id=msg.message_id)
        track(msg.from_user.id, callback, 'search_by_title')
        return
    _, page = callback.data.split('_')
    page = int(page)
    bot.send_chat_action(msg.chat.id, 'typing')
    if len(books) % ELEMENTS_ON_PAGE == 0:
        page_max = len(books) // ELEMENTS_ON_PAGE
    else:
        page_max = len(books) // ELEMENTS_ON_PAGE + 1
    msg_text = ''
    for book in books[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]:
        msg_text += book.to_send
    msg_text += f'<code>Страница {page}/{page_max}</code>'
    keyboard = get_keyboard(page, page_max, 'ba')
    if keyboard:
        bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                              reply_markup=keyboard)
    else:
        bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML')
    track(msg.from_user.id, callback, 'books_by_author')


@bot.callback_query_handler(func=lambda x: re.search(r'a_([0-9])+', x.data) is not None)
@timeit
def search_by_authors(callback: CallbackQuery):  # search authors
    msg = callback.message
    authors = lib.author_by_name(msg.reply_to_message.text)
    if authors is None:
        bot.send_message(msg.chat.id, 'Автор не найден!')
        track(msg.from_user.id, callback, 'search_by_authors')
        return
    _, page = callback.data.split('_')
    page = int(page)
    bot.send_chat_action(msg.chat.id, 'typing')
    if len(authors) % ELEMENTS_ON_PAGE == 0:
        page_max = len(authors) // ELEMENTS_ON_PAGE
    else:
        page_max = len(authors) // ELEMENTS_ON_PAGE + 1
    msg_text = ''
    for author in authors[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]:
        msg_text += author.to_send
    msg_text += f'<code>Страница {page}/{page_max}</code>'
    keyboard = get_keyboard(page, page_max, 'a')
    if keyboard:
        bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                              reply_markup=keyboard)
    else:
        bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML')
    track(msg.from_user.id, callback, 'search_by_authors')


@bot.message_handler(regexp='/a_([0-9])+')
@timeit
def books_by_author(msg: Message):  # search books by author (use messages)
    _, id_ = msg.text.split('_')
    id_ = int(id_)
    user_sets = db.get_lang_settings(msg.from_user.id)
    books = lib.book_by_author(id_, user_sets)
    if books is None:
        bot.reply_to(msg, 'Ошибка! Книги не найдены!')
        track(msg.from_user.id, msg, 'books_by_author')
        return
    bot.send_chat_action(msg.chat.id, 'typing')
    if len(books) % ELEMENTS_ON_PAGE == 0:
        page_max = len(books) // ELEMENTS_ON_PAGE
    else:
        page_max = len(books) // ELEMENTS_ON_PAGE + 1
    msg_text = ''
    for book in books[0:ELEMENTS_ON_PAGE]:
        msg_text += book.to_send
    msg_text += f'<code>Страница {1}/{page_max}</code>'
    keyboard = get_keyboard(1, page_max, 'ba')
    if keyboard:
        bot.reply_to(msg, msg_text, parse_mode='HTML', reply_markup=keyboard)
    else:
        bot.reply_to(msg, msg_text, parse_mode='HTML')
    track(msg.from_user.id, msg, 'books_by_author')


@bot.message_handler(commands=['donate'])
def donation(msg: Message):  # send donation information
    text = "О том, как поддержать проект можно узнать "
    text += '<a href="http://telegra.ph/Pozhertvovaniya-02-11">тут</a>.'
    bot.reply_to(msg, text, parse_mode='HTML')


@bot.message_handler(regexp='^/fb2_([0-9])+$')
def send_fb2(message: Message):  # fb2 books handler
    return send_book(message, 'fb2')


@bot.message_handler(regexp='^/epub_([0-9])+$')
def send_epub(message: Message):  # epub books handler
    return send_book(message, 'epub')


@bot.message_handler(regexp='^/mobi_([0-9])+$')
def send_mobi(message: Message):  # mobi books handler
    return send_book(message, 'mobi')


@bot.message_handler(regexp='^/djvu_([0-9])+$')
def send_djvu(message: Message):  # djvu books handler
    return send_book(message, 'djvu')


@bot.message_handler(regexp='^/pdf_([0-9])+$')
def send_pdf(message: Message):  # pdf books handler
    return send_book(message, 'pdf')


@bot.message_handler(regexp='^/doc_([0-9])+$')
def send_doc(message: Message):  # doc books handler
    return send_book(message, 'doc')


def send_by_file_id(foo):  # try to send document by file_id
    def try_send(msg, type_, book_id=None):
        if not book_id:
            _, book_id = msg.text.split('_')
            book_id = int(book_id)
        file_id = lib.get_file_id(book_id, type_)  # try to get file_id from BD
        if file_id:
            return foo(msg, type_, book_id=book_id, file_id=file_id)  # if file_id not found
        else:
            return foo(msg, type_, book_id=book_id)
    return try_send


def download(type_, book_id, msg):
    try:
        if type_ in ['fb2', 'epub', 'mobi']:
            r = requests.get(f"http://flibusta.is/b/{book_id}/{type_}")
        else:
            r = requests.get(f"http://flibusta.is/b/{book_id}/download")
    except requests.exceptions.ConnectionError as err:
        telebot.logger.exception(err)
        return None
    if '<!DOCTYPE html' in str(r.content[:100]):  # if bot get html file with error message
        try:  # try download file from tor
            if type_ in ['fb2', 'epub', 'mobi']:
                r = requests.get(f"http://flibustahezeous3.onion/b/{book_id}/{type_}",
                                 proxies=config.PROXIES)
            else:
                r = requests.get(f"http://flibustahezeous3.onion/b/{book_id}/download",
                                 proxies=config.PROXIES)
        except requests.exceptions.ConnectionError as err:
            telebot.logger.exception(err)
            bot.reply_to(msg, "Ошибка подключения к серверу! Попробуйте позднее.")
            return None
    if '<!DOCTYPE html' in str(r.content[:100]) or '<html>' in str(r.content[:100]):  # send message to user when get
        bot.reply_to(msg, 'Ошибка!')  # html file
        return None
    return r


@timeit
@send_by_file_id
def send_book(msg: Message, type_: str, book_id=None, file_id=None):  # download from flibusta server and
    track(msg.from_user.id, msg, 'download')                          # send document to user
    if book_id is None:
        _, book_id = msg.text.split('_')
        book_id = int(book_id)
    book = lib.book_by_id(book_id)
    if book is None:
        bot.reply_to(msg, 'Книга не найдена!')
        return
    caption = ''
    if book.author:
        if book.author.short:
            caption += book.author.normal_name
    caption += '\n' + book.title
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton('Поделиться',
                             switch_inline_query=f"share_{book_id}"))
    if file_id:
        try:
            bot.send_document(msg.chat.id, file_id, reply_to_message_id=msg.message_id,
                              caption=caption, reply_markup=markup)
        except Exception as err:
            logger.debug(err)
        else:
            return
    r = download(type_, book_id, msg)
    if r is None:
        return
    bot.send_chat_action(msg.chat.id, 'upload_document')
    filename = normalize(book, type_)
    with open(filename, 'wb') as f:
        f.write(r.content)
    if type_ == 'fb2':  # if type "fb2" extract file from archive
        os.rename(filename, filename.replace('.fb2', '.zip'))
        try:
            zip_obj = zipfile.ZipFile(filename.replace('.fb2', '.zip'))
        except zipfile.BadZipFile as err:
            logger.debug(err)
            return
        extracted = zip_obj.namelist()[0]
        zip_obj.extract(extracted)
        zip_obj.close()
        os.rename(extracted, filename)
        os.remove(filename.replace('.fb2', '.zip'))
    file_size = lib.get_file_size(book_id)
    if file_size < 50 * 1024 * 1024:
        try:
            res = bot.send_document(msg.chat.id, open(filename, 'rb'), reply_to_message_id=msg.message_id,
                                    caption=caption, reply_markup=markup)
        except requests.ConnectionError as err:
            logger.debug(err)
        else:
            lib.set_file_id(book_id, res.document.file_id, type_)
        finally:
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass
            return
    try:
        shutil.move(filename, './ftp')
    except shutil.Error:
        try:
            os.remove(filename)
        except FileNotFoundError:
            pass
        lib.update_life_time(filename)
    else:
        lib.set_life_time(filename)

    life_time = lib.get_life_time(filename)
    if life_time is None:  # todo: сообщение об ошибке
        return
    text = 'Не могу загрузить сюда файл, но у меня есть ссылка для скачивания: \n'
    text += f'📎  <a href="http://35.164.29.201/ftp/download.php?filename={filename}">Скачать</a>\n'
    text += 'Ссылка будет доступна 3 часа ( начиная с ' + time.strftime("%H:%M") + ' MSK)'

    keyboard = InlineKeyboardMarkup().row(
        InlineKeyboardButton('Обновить ссылку', callback_data=f'updatelink_{book_id}_{type_}')
    )
    bot.reply_to(msg, text, parse_mode='HTML', reply_markup=keyboard)


@bot.inline_handler(func=lambda x: re.search(r'share_([0-9])+$', x.query) is not None)
@timeit
def inline_share(query: InlineQuery):  # share book to others user with use inline query
    track(query.from_user.id, query, 'share_book')
    _, book_id = query.query.split('_')
    result = list()
    book = lib.book_by_id(book_id)
    if book is None:
        return
    result.append(InlineQueryResultArticle('1', 'Поделиться',
                                           InputTextMessageContent(book.to_share, parse_mode='HTML',
                                                                   disable_web_page_preview=True), ))
    bot.answer_inline_query(query.id, result)


@bot.inline_handler(func=lambda query: query.query)
@timeit
def inline_hand(query: InlineQuery):  # inline search
    track(query.from_user.id, query, 'inline_search')
    user_sets = db.get_lang_settings(query.from_user.id)
    books = lib.book_by_title(query.query, user_sets)
    if books is None:
        bot.answer_inline_query(query.id, [InlineQueryResultArticle(
            '1', 'Книги не найдены!', InputTextMessageContent('Книги не найдены!')
        )]
                                )
        return
    book_index = 1
    result = list()
    for book in books[0:min(len(books) - 1, 50 - 1)]:
        result.append(InlineQueryResultArticle(str(book_index), book.title,
                                               InputTextMessageContent(book.to_share, parse_mode='HTML',
                                                                       disable_web_page_preview=True)))
        book_index += 1
    bot.answer_inline_query(query.id, result)


def make_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user_set = db.get_lang_settings(user_id)
    keyboard = InlineKeyboardMarkup()
    if user_set['allow_uk'] == 0:
        keyboard.row(InlineKeyboardButton('Украинский: 🅾 выключен!', callback_data='uk_on'))
    else:
        keyboard.row(InlineKeyboardButton('Украинский: ✅ включен!', callback_data='uk_off'))
    if user_set['allow_be'] == 0:
        keyboard.row(InlineKeyboardButton('Белорусский: 🅾 выключен!', callback_data='be_on'))
    else:
        keyboard.row(InlineKeyboardButton('Белорусский: ✅ включен!', callback_data='be_off'))
    return keyboard


@bot.message_handler(commands=['settings'])
def settings(msg: Message):  # send settings message
    keyboard = make_settings_keyboard(msg.from_user.id)
    bot.reply_to(msg, 'Настройки: ', reply_markup=keyboard)


@bot.callback_query_handler(func=lambda x: re.search(r'^(uk|be)_(on|off)$', x.data) is not None)
def lang_setup(query: CallbackQuery):  # language settings
    lang, set_ = query.data.split('_')
    if set_ == 'on':
        db.set_land_settings(query.from_user.id, lang, 1)
    else:
        db.set_land_settings(query.from_user.id, lang, 0)
    keyboard = make_settings_keyboard(query.from_user.id)
    bot.edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id,
                                  reply_markup=keyboard)


@bot.callback_query_handler(func=lambda x: re.search(r'updatelink_*', x.data) is not None)
def update_file_link(query: CallbackQuery):
    _, book_id, type_ = query.data.split('_')
    msg = query.message
    book_id = int(book_id)
    book = lib.book_by_id(book_id)
    filename = normalize(book, type_)
    lib.set_life_time(filename)

    if filename not in os.listdir(config.FTP_DIR):
        r = download(type_, book_id, msg)
        if not r:
            return
        with open(filename, 'wb') as f:
            f.write(r.content)
        if type_ == 'fb2':
            os.rename(filename, filename.replace('.fb2', '.zip'))
            try:
                zip_obj = zipfile.ZipFile(filename.replace('.fb2', '.zip'))
            except zipfile.BadZipFile as err:
                logger.debug(err)
                return
            extracted = zip_obj.namelist()[0]
            zip_obj.extract(extracted)
            zip_obj.close()
            os.rename(extracted, filename)
            os.remove(filename.replace('.fb2', '.zip'))

            shutil.move(filename, './ftp')

    text = 'Не могу загрузить сюда файл, но у меня есть ссылка для скачивания: \n'
    text += f'📎  <a href="http://35.164.29.201/ftp/download.php?filename={filename}">Скачать</a>\n'
    text += 'Ссылка будет доступна 3 часа (начиная с ' + time.strftime("%H:%M") + ' MSK)'

    keyboard = InlineKeyboardMarkup().row(
        InlineKeyboardButton('Обновить ссылку', callback_data=f'updatelink_{book_id}_{type_}')
    )

    bot.edit_message_text(text, chat_id=msg.chat.id, message_id=msg.message_id,
                          reply_markup=keyboard, parse_mode='HTML')
    track(msg.from_user.id, query, 'search_by_authors')


@bot.message_handler(func=lambda message: True)
def search(msg: Message):
    track(msg.from_user.id, msg, 'receive_message')
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('По названию', callback_data='b_1'),
                 InlineKeyboardButton('По авторам', callback_data='a_1')
                 )
    bot.reply_to(msg, 'Поиск: ', reply_markup=keyboard)


ftp = Controller()
ftp.start()

if config.WEBHOOK:
    import flask

    app = flask.Flask(__name__)

    checker = Checker(bot)


    @app.route('/', methods=['GET', 'POST'])
    def index():
        return ''


    @app.route(config.WEBHOOK_URL_PATH, methods=['POST'])
    def webhook():
        if flask.request.headers.get('content-type') == 'application/json':
            json_string = flask.request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            checker.update()
            return ''
        else:
            flask.abort(403)


    bot.remove_webhook()

    time.sleep(0.3)

    bot.set_webhook(url=config.WEBHOOK_URL_BASE + config.WEBHOOK_URL_PATH,
                    certificate=open(config.WEBHOOK_SSL_CERT, 'r'))

    checker.start()

    try:
        app.run(host=config.WEBHOOK_LISTEN,
                port=config.WEBHOOK_PORT,
                ssl_context=(config.WEBHOOK_SSL_CERT, config.WEBHOOK_SSL_PRIV),
                debug=config.DEBUG)
    except KeyboardInterrupt:
        pass

    checker.stop()

    bot.remove_webhook()
else:
    bot.polling()

ftp.stop()
