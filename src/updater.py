import requests
import gzip
import os
import argparse
from pony.orm import *


from database.tables import Book, Author


import config

TOR_URL = 'http://flibustahezeous3.onion'
BASIC_URL = 'http://flibusta.is'

files = ['lib.libavtor.sql',
         'lib.libbook.sql',
         'lib.libavtorname.sql']

db = Database('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD)


@db_session
def create_db():
    print('Creating databases...')
    db.execute(f'CREATE DATABASE {config.LIB_DATABASE} CHARACTER SET utf8 COLLATE utf8_general_ci;'
               f'CREATE DATABASE {config.USERS_DATABASE} CHARACTER SET utf8 COLLATE utf8_general_ci;')


def delete_tables(ch_tables):
    print('Deleting tables...')
    if 'lib' in ch_tables:
        from database.tables import l_db
        l_db.drop_all_tables(with_all_data=True)
    if 'users' in ch_tables:
        from database.tables import u_db
        u_db.drop_all_tables(with_all_data=True)


def download():
    for file in files:
        print('Downloading ' + file + ' ...')
        try:
            r = requests.get(BASIC_URL + '/sql/' + file + '.gz')
        except Exception as e:
            print(e)
            try:
                r = requests.get(TOR_URL + '/sql/' + file + '.gz',
                                 proxies=config.PROXIES)
            except Exception as e:
                print(e)
                return
        with open(file + '.gz', "wb") as f:
            f.write(r.content)
        if not os.path.exists('../databases/'):
            os.mkdir('../databases/')
        with gzip.open(file + '.gz', "rb") as ziped:
            with open('../databases/' + file, "wb") as f:
                f.write(ziped.read())
        os.remove(file + '.gz')
    return True


@db_session
def add(id_):
    print(f'Processing... {id_}')
    book = db.get(f'SELECT BookId, Title, Lang, FileType FROM temp.libbook WHERE BookId={id_};')
    new_book = Book(id=book[0], title=book[1], lang=book[2], file_type=book[3])
    author_ids = db.select(f'SELECT AvtorId FROM temp.libavtor WHERE BookId={id_};')
    for a_id in author_ids:
        author = get(a for a in Author if a.id == a_id)
        if not author:
            info = db.get(
                f'SELECT FirstName, MiddleName, LastName FROM temp.libavtorname WHERE AvtorId={a_id};')
            if not info:
                continue
            author = Author(id=a_id, first_name=info[0], middle_name=info[1], last_name=info[2])
        author.books.add(new_book)


@db_session
def _creating_temp_database():
    print('Creating temp database...')
    db.execute(f'CREATE DATABASE temp;')


def _import_files():
    print('Import files...')
    for file_ in files:
        print(f'Import {file_}')
        os.system(f"mysql -u{config.MYSQL_USER} -p{config.MYSQL_PASSWORD} temp < ../databases/{file_}")


@db_session
def _clean_up_data():
    print('Clean up data...')
    db.execute("DELETE FROM temp.libbook WHERE Deleted<>0 OR (Lang<>'ru' AND Lang<>'uk' AND Lang<>'be')"
               "OR (FileType<>'djvu' AND FileType<>'pdf' AND FileType<>'doc' AND FileType<>'fb2'"
               "AND FileType<>'epub' AND FileType<>'mobi');")


@db_session
def _drop_temp():
    print('Drop temp table...')
    db.execute('DROP DATABASE temp;')


@db_session
def _update():
    return db.select('SELECT temp.libbook.BookId FROM temp.libbook;')


def update():
    _creating_temp_database()

    _import_files()

    _clean_up_data()

    print('Update data...')
    for i in _update():
        add(i)


@db_session
def update_fulltext():
    print('Update fulltext...')
    from database.tables import l_db
    l_db.execute("ALTER TABLE book ADD FULLTEXT FULLTEXT_TITLE (title);")
    l_db.execute("ALTER TABLE author ADD FULLTEXT FULLTEXT_AUTHOR (first_name, middle_name, last_name);")


def __create_parser():
    parser = argparse.ArgumentParser('Script for work with database')

    create_group = parser.add_argument_group('Create block')
    create_group.add_argument('--c-db', '--create-database', action='store_true', help='Create databases')
    create_group.add_argument('--c-tb', '--create-tables', action='store_true', help='Create tables')
    create_group.add_argument('--c-l-tb', '--create-lib-tables', action='store_true', help='Create library tables')
    create_group.add_argument('--c-u-tb', '--create-users-tables', action='store_true', help='Create users tables')

    delete_group = parser.add_argument_group('Delete block')
    delete_group.add_argument('--d-tb', '--delete-tables', action='store_true', help='Delete tables')
    delete_group.add_argument('--d-l-tb', '--delete-lib-tables', action='store_true', help='Delete library tables')
    delete_group.add_argument('--d-u-tb', '--delete-users-tables', action='store_true', help='Delete users tables')

    update_group = parser.add_argument_group('Update database block')
    update_group.add_argument('--u', '--update', action='store_true', help='Date update')
    update_group.add_argument('--u-f', '--update-fulltext', action='store_true', help='Fulltext update')

    download_group = parser.add_argument_group('Download block')
    download_group.add_argument('--d', '--download', action='store_true', help='Download DB files')

    return parser


if __name__ == '__main__':
    args = __create_parser().parse_args()

    if args.c_db:
        create_db()

    elif args.u:
        update()
    elif args.u_f:
        update_fulltext()

    elif args.d_tb:
        delete_tables(['lib', 'users'])
    elif args.d_l_tb:
        delete_tables(['lib'])
    elif args.d_u_tb:
        delete_tables(['users'])

    elif args.d:
        download()
