import json

CURRENCY_NAME = '로소'
CURRENCY_SYMBOL = 'R'

YELLOW = 0xffbb00
AQUA = 0x03a9fc

PERIOD = 20

GUILDS = [935817966757478452]
DEVELOPERS = [366565792910671873]


def get_secret(path: str) -> str:
    with open('res/secret.json', 'r') as file:
        data = json.load(file)
    path = path.split('.')
    while path:
        data = data[path.pop(0)]
    return data
