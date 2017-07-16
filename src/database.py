import requests
import gzip
import os
import argparse
from pony import orm

import config

TOR_URL = 'http://flibustahezeous3.onion'
BASIC_URL = 'http://flibusta.is'

files = ['lib.libavtor.sql',
         'lib.libbook.sql',
         'lib.libavtorname.sql']


def create_db():
    print('Creating databases...')
    db = orm.Database('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD)
    with orm.db_session:
        db.execute(f'CREATE DATABASE {config.LIB_DATABASE} CHARACTER SET utf8 COLLATE utf8_general_ci;'
                   f'CREATE DATABASE {config.USERS_DATABASE} CHARACTER SET utf8 COLLATE utf8_general_ci;')


def create_tables():
    print('Creating tables...')
    from pony_tables import lib_db, user_db
    lib_db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER,
                passwd=config.MYSQL_PASSWORD, db=config.LIB_DATABASE)
    lib_db.generate_mapping(create_tables=True)
    lib_db.disconnect()
    user_db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER,
                 passwd=config.MYSQL_PASSWORD, db=config.USERS_DATABASE)
    user_db.generate_mapping(create_tables=True)
    user_db.disconnect()


def delete_tables():
    print('Deleting tables...')
    from pony_tables import lib_db, user_db
    lib_db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER,
                passwd=config.MYSQL_PASSWORD, db=config.LIB_DATABASE)
    lib_db.generate_mapping()
    lib_db.drop_all_tables()
    lib_db.disconnect()
    user_db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER,
                 passwd=config.MYSQL_PASSWORD, db=config.LIB_DATABASE)
    user_db.generate_mapping()
    user_db.drop_all_tables()
    user_db.disconnect()


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
        with gzip.open(file + '.gz', "rb") as ziped:
            with open('./databases/' + file, "wb") as f:
                f.write(ziped.read())
        os.remove(file + '.gz')
    return True


def update():
    print('Creating temp database...')
    db = orm.Database('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD)
    with orm.db_session:
        db.execute(f'CREATE DATABASE temp;')
    db.disconnect()

    print('Import files...')
    for file_ in files:
        print(f'Import {file_}')
        os.system(f"mysql -u{config.MYSQL_USER} -p{config.MYSQL_PASSWORD} temp < ./databases/{file_}")

    print('Clean up date...')
    db = orm.Database('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD, db='temp')
    with orm.db_session:
        db.execute("DELETE FROM libbook WHERE Deleted<>0 OR (Lang<>'ru' AND Lang<>'uk' AND Lang<>'be')"
                   "OR (FileType<>'djvu' AND FileType<>'pdf' AND FileType<>'doc' AND FileType<>'fb2'"
                   "AND FileType<>'epub' AND FileType<>'mobi');")
    db.disconnect()

    print('Update date...')
    from pony_tables import lib_db, Author, Book
    lib_db.bind('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD,
                db=config.LIB_DATABASE, charset='utf8')
    lib_db.generate_mapping(create_tables=False)
    temp_db = orm.Database('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD,
                           db = 'temp')
    with orm.db_session:
        ids = temp_db.select('SELECT bookId FROM temp.libbook;')
        ids_len = len(ids)
        for i, id_ in enumerate(ids):
            print(f'Processing... {i}/{ids_len}')
            book = temp_db.get(f'SELECT BookId, Title, Lang, FileType FROM temp.libbook WHERE BookId={id_};')
            new_book = Book(id=book[0], title=book[1], lang=book[2], file_type=book[3])
            orm.commit()
            author_ids = temp_db.select(f'SELECT AvtorId FROM temp.libavtor WHERE BookId={id_};')
            for a_id in author_ids:
                author = orm.select(a for a in Author if a.id == a_id)[:]
                if author:
                    author = author[0]
                else:
                    info = temp_db.get(
                        f'SELECT FirstName, MiddleName, LastName FROM temp.libavtorname WHERE AvtorId={a_id};')
                    if not info:
                        continue
                    author = Author(id=a_id, first_name=info[0], middle_name=info[1], last_name=info[2])
                author.books.add(new_book)
                orm.commit()
        temp_db.execute('DROP DATABASE temp;')
        temp_db.commit()
    temp_db.disconnect()
    lib_db.disconnect()


def update_fulltext():
    print('Update fulltext...')
    db = orm.Database('mysql', host=config.MYSQL_HOST, user=config.MYSQL_USER, passwd=config.MYSQL_PASSWORD,
                      db=config.LIB_DATABASE)
    with orm.db_session:
        db.execute("ALTER TABLE book ADD FULLTEXT FULLTEXT_TITLE (title);")
        db.execute("ALTER TABLE author ADD FULLTEXT FULLTEXT_AUTHOR (first_name, middle_name, last_name);")
    db.disconnect()


def __create_parser():
    parser = argparse.ArgumentParser('Script for work with database')

    create_group = parser.add_argument_group('Create block')
    create_group.add_argument('--c-db', '--create-database', action='store_true', help='Create databases')
    create_group.add_argument('--c-tb', '--create-tables', action='store_true', help='Create tables')

    delete_group = parser.add_argument_group('Delete block')
    delete_group.add_argument('--d-tb', '--delete-tables', action='store_true', help='Delete tables')

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
    elif args.c_tb:
        create_tables()

    elif args.u:
        update()
    elif args.u_f:
        update_fulltext()

    elif args.d_tb:
        delete_tables()

    elif args.d:
        download()
