from os import listdir

from discord import Intents
from discord.ext.commands import Bot
from discord_slash import SlashCommand

from const import get_secret

intents = Intents.default()
intents.members = True
bot = Bot(command_prefix='GOROSO_BANK', intents=intents)
slash = SlashCommand(bot, sync_commands=True)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


for file in listdir('cogs'):
    if file.endswith('.py') and not file.startswith('_'):
        bot.load_extension(f'cogs.{file[:-3]}')
        print(f'Cog loaded: {file[:-3]}')

bot.run(get_secret('token'))
