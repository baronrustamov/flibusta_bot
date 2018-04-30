from pony.orm import *
import re
from random import choice


import config

db = Database()


class Book(db.Entity):
    id = PrimaryKey(int)
    title = Required(str, 256)
    authors = Set('Author', reverse='books')
    lang = Optional(str, 2)
    file_type = Optional(str, 4)

    @db_session
    def to_send_book(self, authors=None):
        res = f'<b>{self.title}</b> | {self.lang}\n'
        authors = authors if authors else Author.authors_by_book_id(self.id)
        if authors:
            for a in authors:
                res += f'<b>{a.normal_name}</b>\n'
        else:
            res += '\n'
        if self.file_type == 'fb2':
            return res + f'⬇ fb2: /fb2_{self.id}\n⬇ epub: /epub_{self.id}\n⬇ mobi: /mobi_{self.id}\n\n'
        else:
            return res + f'⬇ {self.file_type}: /{self.file_type}_{self.id}\n\n'

    @db_session
    def to_share_book(self):
        url = 'https://telegram.me/flibusta_rebot?start='
        res = f'<b>{self.title}</b> | {self.lang}\n'
        authors = Author.authors_by_book_id(self.id)
        if authors:
            for a in authors:
                res += f'<b>{a.normal_name}</b>\n'
        else:
            res += '\n'
        if self.file_type == 'fb2':
            return res + (f'⬇ fb2: <a href="{url}fb2_{self.id}">/fb2_{self.id}</a>\n'
                          f'⬇ epub: <a href="{url}epub_{self.id}">/epub_{self.id}</a>\n'
                          f'⬇ mobi: <a href="{url}mobi_{self.id}">/mobi_{self.id}</a>\n')
        else:
            self.file_type = self.file_type.lower
            return res + (f'⬇ {self.file_type}: <a href="{url}{self.file_type}_{self.id}">'
                          f'/{self.file_type}_{self.id}</a>\n')

    @classmethod
    @db_session
    def book_by_id(cls, id_):
        return get(b for b in Book if b.id == id_)

    @classmethod
    @db_session
    def books_by_author(cls, id_, user):
        return sorted(lang_filter(select(b for a in Author if a.id == id_ for b in a.books)[:], user),
                      key=sort_by_alphabet)

    @classmethod
    @db_session
    def books_by_title(cls, title, user):
        if title:
            title = for_search(title)
        return lang_filter(Book.select_by_sql(
            "SELECT * FROM book WHERE MATCH (title) AGAINST ($title IN BOOLEAN MODE)"), user)

    @classmethod
    @db_session
    def get_random_book(cls):
        book_ids = select(b.id for b in Book)[:]
        r_id = choice(book_ids)[0]
        return get(b for b in Book if b.id == r_id)


class FileId(db.Entity):
    book_id = Required(int)
    file_type = Required(str, 4)
    file_id = PrimaryKey(str, 64)

    @classmethod
    @db_session
    def get_file_id(cls, book_id, file_type):
        return get(f for f in FileId if f.book_id == book_id and f.file_type == file_type)

    @classmethod
    @db_session
    def set_file_id(cls, book_id, file_type, file_id):
        id_ = get(f for f in FileId if f.book_id == book_id and f.file_type == file_type)
        if not id_:
            id_ = FileId(book_id=book_id, file_type=file_type, file_id=file_id)


class Author(db.Entity):
    id = PrimaryKey(int)
    first_name = Optional(str, 99)
    last_name = Optional(str, 99)
    middle_name = Optional(str, 99)
    books = Set(Book, reverse='authors')

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

    @classmethod
    @db_session
    def authors_by_book_id(cls, id_):
        return select(a for b in Book if b.id == id_ for a in b.authors)[:]

    @classmethod
    @db_session
    def author_by_id(cls, id_):
        return get(a for a in Author if a.id == id_)

    @classmethod
    @db_session
    def authors_by_name(cls, name):
        if name:
            name = for_search(name)
        return sorted(Author.select_by_sql(
            "SELECT * FROM author WHERE MATCH (first_name, middle_name, last_name) AGAINST ($name IN BOOLEAN MODE)"),
            key=sort_by_books_count, reverse=True)


class User(db.Entity):
    id = PrimaryKey(int)
    allow_be = Required(bool, default=True)
    allow_uk = Required(bool, default=True)

    @classmethod
    @db_session
    def set_lang_settings(cls, id_, lang, status):
        user = select(u for u in User if u.id == id_)[:]
        if user:
            user = user[0]
        else:
            user = User(id=id_)
        if lang == 'uk':
            user.allow_uk = status
        if lang == 'be':
            user.allow_be = status

    @classmethod
    @db_session
    def get_user(cls, id_):
        user = select(u for u in User if u.id == id_)[:]
        if user:
            return user[0]
        else:
            return User(id=id_)


def lang_filter(books, user):
    langs = ['ru']
    if user.allow_uk:
        langs.append('uk')
    if user.allow_be:
        langs.append('be')
    return [book for book in books if book.lang in langs]


def sort_by_alphabet(obj: Book) -> str:
    if obj.title:
        return obj.title.replace('«', '').replace('»', '').replace('"', '')
    else:
        return ''


def sort_by_books_count(obj):
    return obj.books.count()


def for_search(arg):
    res = ''
    for r in re.findall(r'([\w]+)', arg):
        if len(r) >= 3:
            res += f'+{r} '
    return res


db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD,
          db=config.LIB_DATABASE)
db.generate_mapping(create_tables=True)
