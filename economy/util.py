from datetime import datetime
from typing import List

from economy.models import Owner, Word
from util import database


def get_ranking_by_money(count: int = 10) -> List[Owner]:
    """ Get ranking by money """
    cursor = database.cursor()
    cursor.execute('SELECT id FROM owner ORDER BY money DESC LIMIT ?', (count,))
    return [Owner.get_by_id(row[0]) for row in cursor.fetchall()]


def get_ranking_by_word(count: int = 10):
    """
    Get ranking by word
    :param count: count of the rows
    :return: list of the converted rows with Word, fee, and fee_total
    """
    cursor = database.cursor()
    words = dict()
    for row in cursor.execute('SELECT user_id, word_id FROM word_use'):
        if row[1] not in words:
            word = Word.get_by_id(row[1])
            words[row[1]] = [word, word.get_fee(), 0.0]
        else:
            words[row[1]][2] += words[row[1]][1]
    return list(sorted(words.values(), key=lambda x: x[2], reverse=True))[:count]


def add_log(user_id: int, word_id: int):
    """ Add log """
    now = datetime.now()
    cursor = database.cursor()
    cursor.execute('INSERT INTO word_use (datetime, user_id, word_id) VALUES (?, ?, ?)', (now, user_id, word_id))
    database.commit()


def get_log(owner_id: int, type_: str, count: int) -> List[tuple]:
    """
    Get the word detection log
    :param owner_id: owner id of the user
    :param type_: 'i_paid', 'i_got', or 'all'
    :param count: the count of rows
    :return: the history
    """
    owner = Owner.get_by_id(owner_id)
    cursor = database.cursor()
    if type_ == 'i_paid':
        cursor.execute('SELECT * '
                       'FROM word_use '
                       'WHERE user_id = ? '
                       'ORDER BY datetime DESC '
                       'LIMIT ?',
                       (owner.id, count))
    elif type_ == 'i_got':
        cursor.execute('SELECT * '
                       'FROM word_use '
                       'WHERE word_id IN (SELECT id FROM word WHERE owner_id = ?) '
                       'ORDER BY datetime DESC '
                       'LIMIT ?',
                       (owner.id, count))
    elif type_ == 'all':
        cursor.execute('SELECT * '
                       'FROM word_use '
                       'ORDER BY datetime DESC '
                       'LIMIT ?',
                       (count,))

    return cursor.fetchall()
