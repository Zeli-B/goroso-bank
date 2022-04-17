from typing import Optional, List

from economy.models import Word, Owner
from util import database


def exhibit(word: Word, price: float):
    """
    Exhibits a word in the market.
    :param word: The word to exhibit.
    :param price: The price of the word.
    :return: None
    """
    cursor = database.cursor()
    cursor.execute('INSERT INTO market VALUES (?, ?)', (word.id, price))
    database.commit()


def withhold(word_id: int):
    """
    Withholds a word from the market.
    :param word_id: The word to withhold.
    :return: None
    """
    cursor = database.cursor()
    cursor.execute('DELETE FROM market WHERE word_id = ?', (word_id,))
    database.commit()


def buy(word: Word, owner: Owner):
    """
    Buys a word from the market.
    :param word: The word to buy.
    :param owner: The owner of the word.
    :return: None
    """
    withhold(word.id)
    cursor = database.cursor()
    cursor.execute('UPDATE word SET owner_id = ? WHERE id = ?', (owner.id, word.id))
    database.commit()


def is_on_sale(word_id: int) -> bool:
    """ Check if the word is on the market """
    cursor = database.cursor()
    cursor.execute('SELECT * FROM market WHERE word_id = ?', (word_id,))
    return cursor.fetchone() is not None


def get_price(word_id: int) -> Optional[float]:
    """ Get the price of a word """
    if not is_on_sale(word_id):
        return None
    cursor = database.cursor()
    cursor.execute('SELECT price FROM market WHERE word_id = ?', (word_id,))
    return cursor.fetchone()[0]


def get_recent_words(count: int = 10) -> List[Word]:
    """ Get the most recent words on the market """
    cursor = database.cursor()
    cursor.execute('SELECT word_id FROM market ORDER BY word_id DESC LIMIT ?', (count,))
    return [Word.get_by_id(word_id) for (word_id,) in cursor.fetchall()]


def get_words_by_price(count: int = 10) -> List[Word]:
    """ Get the most expensive words on the market """
    cursor = database.cursor()
    cursor.execute('SELECT word_id FROM market ORDER BY price DESC LIMIT ?', (count,))
    return [Word.get_by_id(word_id) for (word_id,) in cursor.fetchall()]
