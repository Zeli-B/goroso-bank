from typing import List, Optional, Dict

from discord import Embed
from discord_slash import SlashContext

from const import CURRENCY_SYMBOL, YELLOW
from util import database


class Owner:
    @staticmethod
    def is_owner(id_: int) -> bool:
        """
        Check if a user is an economy Owner.
        :param id_: Discord ID
        :return: True if user is an Owner, False otherwise
        """
        cursor = database.cursor()
        cursor.execute('SELECT id FROM owner WHERE id = ?', (id_,))
        return cursor.fetchone() is not None

    @staticmethod
    def get_by_id(id_: int) -> Optional['Owner']:
        """
        Get economy Owner by their Discord ID.
        :param id_: Discord ID
        :return: Owner object
        """
        cursor = database.cursor()
        cursor.execute('SELECT * FROM owner WHERE id = ?', (id_,))
        row = cursor.fetchone()
        if row is None:
            return
        return Owner(id_, row[1]).load_words()

    @staticmethod
    def new(id_: int):
        """
        Create a new economy Owner.
        :param id_: Discord ID
        :return: Owner object
        """
        if Owner.get_by_id(id_):
            raise ValueError(f'Owner with id {id_} already exists')
        cursor = database.cursor()
        cursor.execute('INSERT INTO owner (id) VALUES (?)', (id_,))
        database.commit()
        return Owner.get_by_id(id_)

    @staticmethod
    def remove_owner(id_: int):
        """
        Remove an owner.
        :param id_: Discord ID
        """
        cursor = database.cursor()
        cursor.execute('DELETE FROM owner WHERE id = ?', (id_,))
        cursor.execute('DELETE FROM word WHERE owner_id = ?', (id_,))
        database.commit()

    def __init__(self, id_: int, money: float):
        self.id = id_
        self.money = money

        self.words: List[Word] = list()

    def save(self) -> 'Owner':
        """ Save this owner to the database. """
        cursor = database.cursor()
        cursor.execute('UPDATE owner SET money = ? WHERE id = ?', (self.money, self.id))
        database.commit()
        return self

    def set_money(self, money: float) -> 'Owner':
        """
        Set the money of this owner.
        :param money: amount of money
        """
        self.money = money
        return self.save()

    def __str__(self):
        return f'Owner {self.id} ({self.money:.2f}{CURRENCY_SYMBOL}, {len(self.words)} words)'

    def __repr__(self):
        return f'Owner({self.id}, {self.money:.2f}{CURRENCY_SYMBOL}, {len(self.words)}words)'

    def load_words(self) -> 'Owner':
        """
        Load all words owned by this owner.
        :return: Owner object
        """
        self.words = list()
        cursor = database.cursor()
        cursor.execute('SELECT id FROM word WHERE owner_id = ?', (self.id,))
        for row in cursor.fetchall():
            self.words.append(Word.get_by_id(row[0]))
        return self


class Word:
    @staticmethod
    def is_valid(word: str) -> bool:
        """ Check if a word is valid. """
        if len(word) < 2:
            return False
        for letter in word:
            if not ('가' <= letter <= '힣'):
                return False
        return True

    @staticmethod
    def get_price_rate(length: int) -> float:
        return length ** 2 / 100

    @staticmethod
    def get_all() -> List['Word']:
        """
        Get all words.
        :return: List of Word objects
        """
        cursor = database.cursor()
        cursor.execute('SELECT id FROM word')
        words = list()
        for row in cursor.fetchall():
            words.append(Word.get_by_id(row[0]))
        return words

    @staticmethod
    def get_by_id(id_: int) -> 'Word':
        """
        Get economy Word by its ID.
        :param id_: economy Word ID
        :return: Word object
        :exception ValueError: if no Word with that ID exists
        """
        cursor = database.cursor()
        cursor.execute('SELECT * FROM word WHERE id = ?', (id_,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f'Word with id {id_} does not exist')
        return Word(id_, row[1], row[2], row[3])

    @staticmethod
    def get_by_word(word: str) -> Optional['Word']:
        """
        Get economy Word by its word.
        :param word: word content
        :return: Word object
        """
        cursor = database.cursor()
        cursor.execute('SELECT * FROM word WHERE word = ?', (word,))
        row = cursor.fetchone()
        if row is None:
            return
        return Word(row[0], row[1], row[2], row[3])

    @staticmethod
    def is_duplicate(word: str) -> bool:
        """
        Check if a word is already owned by someone.
        :param word: word content string
        """
        cursor = database.cursor()
        cursor.execute('SELECT id FROM word WHERE word = ?', (word,))
        row = cursor.fetchone()
        return row is not None

    @staticmethod
    def new(owner: Owner, text: str, price: float) -> 'Word':
        """
        Create a new economy Word.
        :param owner: owner of the word
        :param text: content of the word
        :param price: price of the word
        :exception ValueError: if the word is already owned by someone
        :exception ValueError: if the word is invalid
        """
        if Word.is_duplicate(text):
            raise ValueError(f'Word {text} already exists')
        if not Word.is_valid(text):
            raise ValueError(f'Word {text} is invalid.')

        cursor = database.cursor()
        cursor.execute('INSERT INTO word (word, owner_id, price) VALUES(?, ?, ?)', (text, owner.id, price))
        database.commit()
        return Word.get_by_word(text)

    @staticmethod
    def remove_word(word: str) -> None:
        """
        Remove a word.
        :param word: word content
        """
        cursor = database.cursor()
        cursor.execute('DELETE FROM word WHERE word = ?', (word,))
        database.commit()

    def __init__(self, id_: int, word: str, owner_id: int, price: float):
        self.id = id_
        self.word = word
        self.owner_id = owner_id
        self.price = price
        self.preferences: Dict[int, float] = dict()
        self.load_preferences()

    def __str__(self):
        return f'Word {self.word} ({self.owner_id})'

    def __repr__(self):
        return f'Word({self.id}, {self.word}, {self.owner_id}, {self.price})'

    def load_preferences(self) -> 'Word':
        """ Load the preferences of the word and store them in a dictionary. """
        self.preferences.clear()
        cursor = database.cursor()
        cursor.execute('SELECT * FROM preference WHERE word_id = ?', (self.id,))
        rows = cursor.fetchall()
        for row in rows:
            self.preferences[row[0]] = row[2]
        return self

    def apply_preference(self, owner_id: int, rate: float) -> 'Word':
        """
        Apply a preference to the word.
        :param owner_id: discord ID of the preference target
        :param rate: [0, 1]
        :return:
        """
        cursor = database.cursor()
        if rate == 1:
            cursor.execute('DELETE FROM preference WHERE word_id = ? AND owner_id = ?',
                           (self.id, owner_id))
        elif owner_id in self.preferences:
            cursor.execute('UPDATE preference SET rate = ? WHERE word_id = ? AND owner_id = ?',
                           (rate, self.id, owner_id))
        else:
            cursor.execute('INSERT INTO preference (word_id, owner_id, rate) VALUES(?, ?, ?)',
                           (self.id, owner_id, rate))
        database.commit()
        self.load_preferences()
        return self

    def get_fee(self) -> float:
        return Word.get_price_rate(len(self.word)) * self.price

    def get_embed(self, ctx: SlashContext) -> Embed:
        owner = ctx.guild.get_member(self.owner_id)
        embed = Embed(title=f'__{self.word}__ 단어 정보', color=YELLOW)
        embed.add_field(name='사용료', value=f'__**{self.get_fee():.2f} {CURRENCY_SYMBOL}**__', inline=False)
        embed.add_field(name='가격', value=f'{self.price:.1f} {CURRENCY_SYMBOL}')
        embed.add_field(name='소유자', value=f'{owner.display_name}')
        if self.preferences:
            lines = list()
            for user_id, rate in self.preferences.items():
                user = ctx.guild.get_member(user_id)
                if user is None:
                    continue
                lines.append(f'- {user.display_name}: {(1 - rate) * 100:.2f}%')
            embed.add_field(name='할인', value='\n'.join(lines), inline=False)
        return embed
