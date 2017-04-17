import pymysql
import time
import datetime
from typing import List
from telebot import logger
import mysql_class

import config


class Author:
    def __init__(self, id_, last_name, first_name, middle_name):
        self.id = id_
        self.last_name = last_name
        self.first_name = first_name
        self.middle_name = middle_name
        self.books_count = None

    @property
    def normal_name(self) -> str:
        temp = ''
        if self.last_name:
            temp = self.last_name
        if self.first_name:
            if temp:
                temp += " "
            temp += self.first_name
        if self.middle_name:
            if temp:
                
                temp += " "
            temp += self.middle_name
        if temp:
            return temp

    @property
    def short(self) -> str:
        temp = ''
        if self.last_name:
            temp += self.last_name
        if self.first_name:
            if temp:
                temp += " "
            temp += self.first_name[0]
        if self.middle_name:
            if temp:
                temp += " "
            temp += self.middle_name[0]
        return temp

    @property
    def to_send(self) -> str:
        return f'👤 <b>{self.normal_name}</b>\n/a_{self.id}\n\n'


class Book:
    def __init__(self, book: tuple, author: Author):
        self.author = author
        self.title = book[0]  # type: str
        self.subtitle = book[1]  # type: str
        self.lang = book[2]  # type: str
        self.id_ = book[3]
        self.file_type = book[4]  # type: str

    @property
    def to_send(self) -> str:
        res = f'<b>{self.title}</b>'
        if self.author:
            res += f' | {self.lang}\n<b>{self.author.normal_name}</b>\n'
        else:
            res += '\n'
        if self.file_type == 'fb2':
            return res + f'⬇ fb2: /fb2_{self.id_}\n⬇ epub: /epub_{self.id_}\n⬇ mobi: /mobi_{self.id_}\n\n'
        else:
            return res + f'⬇ {self.file_type}: /{self.file_type}_{self.id_}\n\n'

    @property
    def to_share(self) -> str:
        url = 'https://telegram.me/flibusta_rebot?start='
        res = f'<b>{self.title}</b>'
        if self.author:
            res += f' | {self.lang}\n<b>{self.author.normal_name}</b>\n'
        else:
            res += '\n'
        if self.file_type == 'fb2':
            return res + (f'⬇ fb2: <a href="{url}fb2_{self.id_}">/fb2_{self.id_}</a>\n'
                          f'⬇ epub: <a href="{url}epub_{self.id_}">/epub_{self.id_}</a>\n'
                          f'⬇ mobi: <a href="{url}mobi_{self.id_}">/mobi_{self.id_}</a>\n')
        else:
            self.file_type = self.file_type.lower
            return res + (f'⬇ {self.file_type}: <a href="{url}{self.file_type}_{self.id_}">'
                          f'/{self.file_type}_{self.id_}</a>\n')


def for_search(arg: str) -> str:
    args = arg.split()
    if len(args) == 1:
        return arg
    else:
        result = '+' + args[0]
        for a in args[1:]:
            result += ' +' + a
        return result


def sort_by_alphabet(obj: Book) -> str:
    if obj.title:
        return obj.title.replace('«', '').replace('»', '').replace('"', '')
    else:
        return ''


def sort_by_books_count(obj: Author) -> int:
    if obj.books_count:
        return obj.books_count
    else:
        return 0


def lang_filter(books: List[Book], lang_sets) -> List[Book]:
    langs = ['ru']
    for key in lang_sets.keys():
        if lang_sets[key]:
            _, lang = key.split('_')
            langs.append(lang)
    return [book for book in books if book.lang in langs]


class Library(mysql_class.MYSQLClass):
    def __init__(self):
        super().__init__()
        self.database = config.MYSQL_DATABASE
        self._connect()

    def __add_author_info(self, books):
        result = []
        for book in books:
            author = self.author_by_id(book[3])
            result.append(
                Book(book, author)
            )
        return result

    def author_books_count(self, id_: int) -> int:
        return self.fetchone(
            'SELECT count(*) FROM libavtor WHERE AvtorId=%s;', (id_,)
        )[0]

    def author_by_id(self, id_):
        author_id = self.fetchone("SELECT AvtorId FROM libavtor WHERE BookId=%s;", (id_,))
        if author_id:
            author = self.fetchone(
                ("SELECT LastName, FirstName, MiddleName "
                 "FROM libavtorname WHERE AvtorId=%s"), (author_id[0],)
            )
            if author:
                return Author(id, *author)
            else:
                return None

    def book_by_id(self, id_):
        book = self.fetchall(
            ("SELECT Title, Title1, Lang, BookId, FileType "
             "FROM libbook WHERE BookId=%s;"), (id_,)
        )
        if book:
            book = book[0]
            author = self.author_by_id(book[3])
            return Book(book, author)
        else:
            return None

    def book_by_author(self, id_, lang_sets):
        book_ids = self.fetchall(
            'SELECT BookId FROM libavtor WHERE AvtorId=%s;', (id_,)
        )
        if book_ids:
            books = []
            for book_id in [x[0] for x in book_ids]:
                book = self.book_by_id(book_id)
                if book:
                    books.append(book)
            if books:
                books = lang_filter(books, lang_sets)
                if books:
                    return sorted(books, key=sort_by_alphabet)
        return None

    def book_by_title(self, title, lang_sets):
        books = self.fetchall(
            ("SELECT Title, Title1, Lang, BookId, FileType FROM libbook WHERE "
             'MATCH (Title) AGAINST (%s IN BOOLEAN MODE)'), (for_search(title),)
        )
        if books:
            books = lang_filter(self.__add_author_info(books), lang_sets)
            if books:
                return books
        return None

    def author_by_name(self, author):
        row = self.fetchall(("SELECT AvtorId, FirstName, MiddleName, LastName "
                             "FROM libavtorname "
                             "WHERE MATCH (FirstName, MiddleName, LastName) "
                             "AGAINST (%s IN BOOLEAN MODE)"), (for_search(author),)
                            )
        if row:
            res = []  # type: List[Author]
            for author in row:
                if self.author_books_count(author[0]):
                    res.append(Author(*author))
            if res:
                for a in res:
                    a.books_count = self.author_books_count(a.id)
                return sorted(res, key=sort_by_books_count, reverse=True)
        return None

    def get_file_id(self, book_id, type_):
        file_id = self.fetchone('SELECT file_id FROM fileids WHERE book_id=%s && file_type=%s',
                                (book_id, type_))
        if file_id:
            return file_id[0]
        else:
            return None

    def set_file_id(self, book_id, file_id, type_):
        try:
            with self.conn.cursor() as cursor:
                if not self.get_file_id(book_id, type_):
                    cursor.execute('INSERT INTO fileids (book_id, file_type, file_id) VALUES (%s, %s, %s)',
                                   (book_id, type_, file_id))
                else:
                    cursor.execute('UPDATE fileids SET file_id=%s WHERE book_id=%s && file_type=%s',
                                   (file_id, book_id, type_))
                self.conn.commit()
        except pymysql.Error as err:
            logger.debug(err)

    def get_file_size(self, book_id):
        size = self.fetchone('SELECT FileSize FROM libbook WHERE BookId=%s', (book_id,))
        if size:
            return size[0]
        else:
            return 0

    def get_life_time(self, filename):
        life_time = self.fetchone('SELECT time FROM fileLifeTime WHERE filename=%s', (filename,))
        if life_time:
            return life_time[0]
        else:
            return None

    def set_life_time(self, filename):
        life_time = self.get_life_time(filename)
        if life_time:
            self.update_life_time(filename)
        else:
            dt = datetime.datetime.fromtimestamp(time.time() + config.LIFE_TIME)
            time_ = dt.strftime('%Y-%m-%d %H:%M:%S')
            try:
                with self.conn.cursor() as cursor:
                    cursor.execute('INSERT INTO fileLifeTime (filename, time) VALUES (%s, %s)',
                                   (filename, time_))
                self.conn.commit()
            except pymysql.Error as err:
                logger.debug(err)

    def update_life_time(self, filename):
        dt = datetime.datetime.fromtimestamp(time.time() + config.LIFE_TIME)
        time_ = dt.strftime('%Y-%m-%d %H:%M:%S')
        try:
            with self.conn.cursor() as cursor:
                x = cursor.execute("UPDATE fileLifeTime SET time=%s WHERE filename=%s",
                                   (time_, filename))
            self.conn.commit()
        except pymysql.Error as err:
            logger.debug(err)
