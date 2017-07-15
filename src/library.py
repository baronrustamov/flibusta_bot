from pony_tables import *
from pony.orm import *

import config

lib_db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD,
            db=config.LIB_DATABASE)
lib_db.generate_mapping()


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


@db_session
def to_send_book(book, authors=None):
    res = f'<b>{book.title}</b>'
    authors = authors if authors else authors_by_book_id(book.id)
    if authors:
        for a in authors:
            res += f' | {book.lang}\n<b>{a.normal_name}</b>\n'
    else:
        res += '\n'
    if book.file_type == 'fb2':
        return res + f'⬇ fb2: /fb2_{book.id}\n⬇ epub: /epub_{book.id}\n⬇ mobi: /mobi_{book.id}\n\n'
    else:
        return res + f'⬇ {book.file_type}: /{book.file_type}_{book.id}\n\n'


@db_session
def to_share_book(book):
    url = 'https://telegram.me/flibusta_rebot?start='
    res = f'<b>{book.title}</b>'
    authors = authors_by_book_id(book.id)
    if authors:
        for a in authors:
            res += f' | {book.lang}\n<b>{a.normal_name}</b>\n'
    else:
        res += '\n'
    if book.file_type == 'fb2':
        return res + (f'⬇ fb2: <a href="{url}fb2_{book.id}">/fb2_{book.id}</a>\n'
                      f'⬇ epub: <a href="{url}epub_{book.id}">/epub_{book.id}</a>\n'
                      f'⬇ mobi: <a href="{url}mobi_{book.id}">/mobi_{book.id}</a>\n')
    else:
        book.file_type = book.file_type.lower
        return res + (f'⬇ {book.file_type}: <a href="{url}{book.file_type}_{book.id}">'
                      f'/{book.file_type}_{book.id}</a>\n')


@db_session
def books_by_title(title, user):
    return lang_filter(Book.select_by_sql(
        "SELECT * FROM book WHERE MATCH (title) AGAINST ($t IN BOOLEAN MODE)",
        {'t': title}), user)


@db_session
def books_by_author(id_, user):
    return sorted(lang_filter(select(b for a in Author if a.id == id_ for b in a.books)[:], user),
                  key=sort_by_alphabet)


@db_session
def authors_by_name(name):
    return sorted(Author.select_by_sql(
        "SELECT * FROM author WHERE MATCH (first_name, middle_name, last_name) AGAINST ($n IN BOOLEAN MODE)",
        {'n': name}), key=sort_by_books_count, reverse=True)


@db_session
def book_by_id(id_):
    book = select(b for b in Book if b.id == id_)[:]
    if book:
        return book[0]


@db_session
def get_file_id(book_id, file_type):
    id_ = select(f for f in FileId if f.book_id == book_id and f.file_type == file_type)[:]
    if id_:
        return id_[0]


@db_session
def set_file_id(book_id, file_type, file_id):
    id_ = select(f for f in FileId if f.book_id == book_id and f.file_type == file_type)[:]
    if id_:
        id_ = id_[0]
    else:
        id_ = FileId(book_id=book_id, file_type=file_type, file_id=file_id)


@db_session
def authors_by_book_id(id_):
    return select(a for b in Book if b.id == id_ for a in b.authors)[:]


@db_session
def author_by_id(id_):
    author = select(a for a in Author if a.id == id_)[:]
    if author:
        return author[0]
