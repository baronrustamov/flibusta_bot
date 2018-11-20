import os

import transliterate as transliterate
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from filbusta_server import Book, Author, BytesResult

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

from django.core.wsgi import get_wsgi_application
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

application = get_wsgi_application()

from db.models import TelegramUser, PostedBook

ELEMENTS_ON_PAGE = 7
BOOKS_CHANGER = 5


def get_keyboard(page: int, pages_count: int, keyboard_type: str) -> InlineKeyboardMarkup or None:
    if pages_count == 1:
        return None
    keyboard = InlineKeyboardMarkup()

    first_row = []
    second_row = []

    if page > 1:
        prev_page = max(1, page - BOOKS_CHANGER)
        if prev_page != page - 1:
            second_row.append(InlineKeyboardButton(f'<< {prev_page}',
                                                   callback_data=f'{keyboard_type}_{prev_page}'))
        first_row.append(InlineKeyboardButton('<', callback_data=f'{keyboard_type}_{page-1}'))

    if page != pages_count:
        next_page = min(pages_count, page + BOOKS_CHANGER)
        if next_page != page + 1:
            second_row.append(InlineKeyboardButton(f'>> {next_page}',
                                                   callback_data=f'{keyboard_type}_{next_page}'))
        first_row.append(InlineKeyboardButton('>', callback_data=f'{keyboard_type}_{page+1}'))

    keyboard.row(*first_row)
    keyboard.row(*second_row)

    return keyboard


def normalize(book: Book, file_type: str) -> str:  # remove chars that don't accept in Telegram Bot API
    filename = '_'.join([a.short for a in book.authors]) + '_-_' if book.authors else ''
    filename += book.title if book.title[-1] != ' ' else book.title[:-1]
    filename = transliterate.translit(filename, 'ru', reversed=True)

    for c in "(),….’!\"?»«':":
        filename = filename.replace(c, '')

    for c, r in (('—', '-'), ('/', '_'), ('№', 'N'), (' ', '_'), ('–', '-'), ('á', 'a'), (' ', '_')):
        filename = filename.replace(c, r)

    return filename + '.' + file_type


class Sender:
    def __init__(self, bot: TeleBot):
        self.bot = bot

    @staticmethod
    def remove_cache(type_: str, id_: int):
        try:
            PostedBook.objects.get(file_type=type_, book_id=id_).delete()
        except ObjectDoesNotExist:
            pass

    def send_book(self, msg: Message, book_id: int, file_type: str):
        try:
            book = Book.get_by_id(book_id)
        except ObjectDoesNotExist:
            self.bot.reply_to(msg, "Книга не найдена!")
            return
        try:
            try:
                pb = PostedBook.objects.get(book_id=book_id, file_type=file_type)
                self.bot.send_document(msg.chat.id, pb.file_id, reply_to_message_id=msg.message_id,
                                       caption=book.caption, reply_markup=book.share_markup)
            except MultipleObjectsReturned:
                PostedBook.objects.filter(book_id=book_id, file_type=file_type).delete()
                raise ObjectDoesNotExist
        except ObjectDoesNotExist:
            self.bot.send_chat_action(msg.chat.id, "upload_document")
            book_bytes = Book.download(book_id, file_type)  # type: BytesResult
            if not book_bytes:
                return self.bot.reply_to(msg, "Ошибка! Попробуйте позже :(")
            if book_bytes.size > 30 * 1000000:
                return self.bot.send_message(msg.chat.id, book.caption, reply_to_message_id=msg.message_id,
                                             reply_markup=book.get_download_markup(file_type))
            book_bytes.name = normalize(book, file_type)
            send_response = self.bot.send_document(msg.chat.id, book_bytes, reply_to_message_id=msg.message_id,
                                                   caption=book.caption, reply_markup=book.share_markup)
            PostedBook.objects.create(book_id=book_id, file_type=file_type, file_id=send_response.document.file_id
                                      ).save()

    def search_books(self, msg: Message, page: int):
        user = TelegramUser.objects.get(user_id=msg.chat.id)
        allowed_langs = []
        if user.settings is not None:
            if user.settings.allow_uk:
                allowed_langs.append("uk")
            if user.settings.allow_be:
                allowed_langs.append("be")
        self.bot.send_chat_action(msg.chat.id, 'typing')
        books = Book.search(msg.reply_to_message.text, allowed_langs)
        if not books:
            self.bot.edit_message_text('Книги не найдены!', chat_id=msg.chat.id, message_id=msg.message_id)
            return
        page_count = len(books) // ELEMENTS_ON_PAGE + (1 if len(books) % ELEMENTS_ON_PAGE != 0 else 1)
        msg_text = ''.join(book.to_send_book for book in books[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]
                           ) + f'<code>Страница {page}/{page_count}</code>'
        self.bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                                   reply_markup=get_keyboard(page, page_count, 'b'))

    def search_authors(self, msg: Message, page: int):
        self.bot.send_chat_action(msg.chat.id, 'typing')
        authors = Author.search(msg.reply_to_message.text)
        if not authors:
            self.bot.send_message(msg.chat.id, 'Автор не найден!')
            return
        page_max = len(authors) // ELEMENTS_ON_PAGE + (1 if len(authors) % ELEMENTS_ON_PAGE != 0 else 1)
        msg_text = ''.join(author.to_send for author in authors[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]
                           ) + f'<code>Страница {page}/{page_max}</code>'
        self.bot.edit_message_text(msg_text, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode='HTML',
                                   reply_markup=get_keyboard(page, page_max, 'a'))

    def search_books_by_author(self, msg: Message, author_id: int, page: int):
        user = TelegramUser.objects.get(user_id=msg.chat.id)
        allowed_langs = []
        if user.settings is not None:
            if user.settings.allow_uk:
                allowed_langs.append("uk")
            if user.settings.allow_be:
                allowed_langs.append("be")
        self.bot.send_chat_action(msg.chat.id, 'typing')
        books = Book.by_author(author_id, allowed_langs)
        if not books:
            self.bot.reply_to(msg, 'Ошибка! Книги не найдены!')
            return
        page_max = len(books) // ELEMENTS_ON_PAGE + (1 if len(books) % ELEMENTS_ON_PAGE != 0 else 1)
        msg_text = ''.join([book.to_send_book
                            for book in books[ELEMENTS_ON_PAGE * (page - 1):ELEMENTS_ON_PAGE * page]]
                           ) + f'<code>Страница {page}/{page_max}</code>'
        if not msg.reply_to_message:
            self.bot.reply_to(msg, msg_text, parse_mode='HTML', reply_markup=get_keyboard(1, page_max, 'ba'))
        else:
            self.bot.edit_message_text(msg_text, msg.chat.id, msg.message_id, parse_mode='HTML',
                                       reply_markup=get_keyboard(page, page_max, 'ba'))
