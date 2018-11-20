import copy
import io
import json
import weakref
from typing import List
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import FLIBUSTA_SERVER


class NoContent(Exception):
    pass


class BytesResult(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.size = len(content)
        self.name = ""


class Author:
    def __init__(self, obj: dict):
        self.obj = obj

    @property
    def id(self):
        return self.obj["id"]

    @id.setter
    def id(self, id_):
        self.obj["id"] = id_

    @property
    def first_name(self):
        return self.obj["first_name"]

    @first_name.setter
    def first_name(self, first_name):
        self.obj["first_name"] = first_name

    @property
    def last_name(self):
        return self.obj["last_name"]

    @last_name.setter
    def last_name(self, last_name):
        self.obj["last_name"] = last_name

    @property
    def middle_name(self):
        return self.obj["middle_name"]

    @middle_name.setter
    def middle_name(self, middle_name):
        self.obj["middle_name"] = middle_name

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

    @staticmethod
    def by_id(author_id: int) -> "Author":
        response = requests.get(f"{FLIBUSTA_SERVER}/author/{author_id}")
        if response.status_code == 204:
            raise NoContent
        return Author(response.json())

    @staticmethod
    def search(query: str) -> List["Author"]:
        response = requests.get(f"{FLIBUSTA_SERVER}/author/search/{query}")
        return [Author(a) for a in response.json()]


class Book:
    def __init__(self, obj: dict):
        self.obj = obj

    @property
    def id(self):
        return self.obj["id"]

    @id.setter
    def id(self, id_):
        self.obj["id"] = id_

    @property
    def title(self):
        return self.obj["title"]

    @title.setter
    def title(self, title):
        self.obj["title"] = title

    @property
    def lang(self):
        return self.obj["lang"]

    @lang.setter
    def lang(self, lang):
        self.obj["lang"] = lang

    @property
    def file_type(self):
        return self.obj["file_type"]

    @file_type.setter
    def file_type(self, file_type):
        self.obj["file_type"] = file_type

    @property
    def authors(self):
        return [Author(a) for a in self.obj["authors"]] if self.obj.get("authors", None) else None

    @authors.setter
    def authors(self, authors):
        self.obj["authors"] = authors

    @property
    def caption(self) -> str:
        return self.title + '\n' + '\n'.join([author.normal_name for author in self.authors])

    @property
    def share_markup(self) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("Не открывается!", callback_data=f"remove_cache"),
            InlineKeyboardButton("Поделиться", switch_inline_query=f"share_{self.id}")
        )
        return markup

    def get_download_markup(self, file_type: str) -> InlineKeyboardMarkup:
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton('Скачать', url=self.get_download_link(file_type)))
        return markup

    @property
    def to_send_book(self) -> str:
        res = f'<b>{self.title}</b> | {self.lang}\n'
        if self.authors:
            for a in self.authors:
                res += f'<b>{a.normal_name}</b>\n'
        else:
            res += '\n'
        if self.file_type == 'fb2':
            return res + f'⬇ fb2: /fb2_{self.id}\n⬇ epub: /epub_{self.id}\n⬇ mobi: /mobi_{self.id}\n\n'
        else:
            return res + f'⬇ {self.file_type}: /{self.file_type}_{self.id}\n\n'

    @staticmethod
    def get_by_id(book_id: int) -> "Book":
        response = requests.get(f"{FLIBUSTA_SERVER}/book/{book_id}")
        if response.status_code == 204:
            raise NoContent
        return Book(response.json())

    @staticmethod
    def search(query: str, allowed_langs=None) -> List["Book"]:
        if allowed_langs is None:
            allowed_langs = list()
        if allowed_langs:
            response = requests.get(f"{FLIBUSTA_SERVER}/book/search/{query}/{json.dumps(allowed_langs)}")
        else:
            response = requests.get(f"{FLIBUSTA_SERVER}/book/search/{query}")
        return [Book(b) for b in response.json()]

    @staticmethod
    def by_author(author_id: int, allowed_langs=None) -> List["Book"]:
        if allowed_langs is None:
            allowed_langs = list()
        if allowed_langs:
            response = requests.get(f"{FLIBUSTA_SERVER}/book/author/{author_id}/{json.dumps(allowed_langs)}")
        else:
            response = requests.get(f"{FLIBUSTA_SERVER}/book/author/{author_id}")
        return [Book(b) for b in response.json()]

    def get_download_link(self, file_type: str) -> str:
        return f"{FLIBUSTA_SERVER}/book/download/{self.id}/{file_type}"

    @staticmethod
    def download(book_id: int, file_type: str) -> BytesResult or None:
        r = requests.get(f"{FLIBUSTA_SERVER}/book/download/{book_id}/{file_type}")
        if r.status_code != 200:
            return None
        return BytesResult(r.content)
