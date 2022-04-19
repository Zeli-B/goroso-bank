from asyncio import wait
from typing import Optional

from discord import User, Message, Embed
from discord.ext.commands import Cog, Bot
from discord_slash import SlashCommandOptionType, SlashContext
from discord_slash.cog_ext import cog_slash
from discord_slash.utils.manage_commands import create_option

from const import DEVELOPERS, GUILDS, CURRENCY_NAME, YELLOW, AQUA, PERIOD
from economy import market
from economy.models import Owner, Word
from economy.util import get_ranking_by_money, add_log, get_log, get_ranking_by_word, get_ranking_by_property
from util import eul_reul, i_ga, get_keys, format_money


class GeneralCog(Cog):
    def __init__(self, bot):
        self.bot: Bot = bot

        self.words = Word.get_all()

    async def handle_word_cost(self, owner: Owner, message: Message):
        if owner is None:
            return
        content = message.content

        censored = False
        used_words = list()

        for word in sorted(self.words, key=lambda x: len(x.word), reverse=True):
            if censored:
                break
            while word.word in content:
                content = content.replace(word.word, ' ', 1)
                word_owner = Owner.get_by_id(word.owner_id)
                if word_owner.id == owner.id:
                    continue
                fee = word.get_fee()
                used_words.append(word)
                if owner.money < fee:
                    censored = True
                    break
                else:
                    rate = word.preferences[owner.id] if owner.id in word.preferences else 1
                    if rate:
                        owner.set_money(owner.money - fee * rate)
                        word_owner.set_money(word_owner.money + fee * rate * 1.1)
                    add_log(message.author.id, word.id)

        if censored:
            content = message.content
            for word in used_words:
                content = content.replace(word.word, '**[수정됨]**')
            tasks = (message.channel.send(f':warning: __{message.author.display_name}__님의 소지금이 부족하여 '
                                          f'메시지의 일부가 수정되었습니다.\n> {content}'),
                     message.delete())
            await wait(tasks)

    @Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return
        owner = Owner.get_by_id(message.author.id)
        if owner is not None:
            await self.handle_word_cost(owner, message)

            # give money by the key count
            keys = 0
            for letter in message.content:
                if Word.is_valid(letter, no_length=True):
                    keys += get_keys(letter)
            if keys > 0:
                owner.set_money(owner.money + keys * 0.009)

    @cog_slash(
        name='money',
        description='소지금을 확인합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='user',
                description='소지금을 확인할 사용자',
                option_type=SlashCommandOptionType.USER,
                required=False
            )
        ]
    )
    async def money(self, ctx: SlashContext, user: Optional[User] = None):
        if user is None:
            user = ctx.author

        owner = Owner.get_by_id(user.id)
        if owner is None:
            await ctx.send(f':warning: __{user.display_name}__ 사용자를 찾을 수 없습니다.')
            return
        await ctx.send(f':white_check_mark: __{user.display_name}__님의 소지금: __{format_money(owner.money)}__, '
                       f'총 자본: __{format_money(owner.get_property())}__',
                       delete_after=PERIOD)

    @cog_slash(
        name='newcomer',
        description='새로운 사용자를 추가합니다.',
        guild_ids=GUILDS,
    )
    async def newcomer(self, ctx: SlashContext):
        if Owner.is_owner(ctx.author.id):
            await ctx.send(f':warning: __{ctx.author.display_name}__님은 이미 있는 사용자입니다.')
            return
        Owner.new(ctx.author.id)
        await ctx.send(f':white_check_mark: 새로운 사용자 __{ctx.author.display_name}__{eul_reul(ctx.author.display_name)} '
                       f'추가했습니다.',
                       delete_after=PERIOD)

    @cog_slash(
        name='user',
        description='사용자 정보를 확인합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='user',
                description='정보를 확인할 사용자',
                option_type=SlashCommandOptionType.USER,
                required=False
            )
        ]
    )
    async def user(self, ctx: SlashContext, user: Optional[User] = None):
        if user is None:
            user = ctx.author
        owner = Owner.get_by_id(user.id)
        if owner is None:
            await ctx.send(f':warning: __{user.display_name}__ 사용자를 찾을 수 없습니다.', delete_after=PERIOD)
            return

        message = await ctx.send(f':hourglass: __{user.display_name}__님의 정보를 가져오는 중입니다...')

        embed = Embed(title=f'{user.display_name}님의 정보', color=YELLOW)
        embed.add_field(name='소지금', value=f'{format_money(owner.money)}')
        embed.add_field(name='출품한 단어 수', value=f'{len(owner.words)}개')
        embed.add_field(name=f'총자본', value=format_money(owner.get_property()))
        if owner.words:
            words = list()
            for word in owner.words:
                words.append(f'{word.word}({round(word.price)})')
                if market.is_on_sale(word.id):
                    words[-1] = f'__{words[-1]}__'
            words = ', '.join(words)
            i = 1
            while words:
                embed.add_field(name=f'등록된 단어 목록 {i}', value=words[:2000], inline=False)
                words = words[2000:]
                i += 1

        await message.edit(content=f':white_check_mark: __{user.display_name}__님의 정보', embed=embed,
                           delete_after=PERIOD)

    @cog_slash(
        name='register',
        description='단어를 등록합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='price',
                description='단어를 등록하는데 필요한 금액 (나중에 변경할 수 없음)',
                option_type=SlashCommandOptionType.FLOAT,
                required=True
            ),
            create_option(
                name='word',
                description='등록할 단어',
                option_type=SlashCommandOptionType.STRING,
                required=True
            )
        ]
    )
    async def register(self, ctx: SlashContext, price: float, word: str):
        if Word.is_duplicate(word):
            await ctx.send(f':warning: __{word}__ 단어는 이미 등록되어 있습니다.', delete_after=PERIOD)
            return
        if price <= 0:
            await ctx.send(f':warning: 단어의 가격은 0 {CURRENCY_NAME}{eul_reul(CURRENCY_NAME)} 넘어야 합니다. '
                           f'(`{price}`라고 입력하셨습니다.)', delete_after=PERIOD)
            return
        if not Word.is_valid(word):
            await ctx.send(f':warning: 단어에는 완성형 한글만 사용할 수 있고, 두 글자 이상이어야 합니다!', delete_after=PERIOD)
            return
        owner = Owner.get_by_id(ctx.author.id)
        if owner is None:
            await ctx.send(f':warning: 단어를 만들기 전에 사용자를 등록해야 합니다! 사용자 등록을 하려면 `/newcomer`를 입력하세요.',
                           delete_after=PERIOD)
            return
        if owner.money < price:
            await ctx.send(f':warning: __{ctx.author.display_name}__님의 소지금이 부족합니다! '
                           f'(현재 __{format_money(owner.money)}__만큼을 가지고 있습니다.)', delete_after=PERIOD)
            return
        owner.set_money(owner.money - price)
        word = Word.new(owner, word, price)
        await ctx.send(f':white_check_mark: __{word.word}__ 단어를 등록했습니다.', embed=word.get_embed(ctx),
                       delete_after=PERIOD)

        self.words = Word.get_all()

    @cog_slash(
        name='cancel',
        description='단어 특허 출원을 취소합니다. (수수료 10%가 발생합니다.)',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='word',
                description='취소할 단어',
                option_type=SlashCommandOptionType.STRING,
                required=True
            )
        ]
    )
    async def cancel(self, ctx: SlashContext, word: str):
        economy_word = Word.get_by_word(word)
        if economy_word is None:
            await ctx.send(f':warning: __{word}__ 단어를 찾을 수 없습니다.', delete_after=PERIOD)
            return
        if economy_word.owner_id != ctx.author.id:
            await ctx.send(f':warning: __{economy_word.word}__ 단어는 __{ctx.author.display_name}__님이 등록한 단어가 아닙니다.',
                           delete_after=PERIOD)
            return

        if market.is_on_sale(economy_word.id):
            market.withhold(economy_word.id)
        Word.remove_word(word)
        owner = Owner.get_by_id(ctx.author.id)
        owner.set_money(owner.money + economy_word.price * 0.9)
        await ctx.send(f':white_check_mark: __{economy_word.word}__ 단어를 삭제했습니다.', delete_after=PERIOD)

        self.words = Word.get_all()

    @cog_slash(
        name='word',
        description='단어에 대한 세부 정보를 확인합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='word',
                description='정보를 확인할 단어',
                option_type=SlashCommandOptionType.STRING,
                required=True
            )
        ]
    )
    async def word(self, ctx: SlashContext, word: str):
        economy_word = Word.get_by_word(word)
        if economy_word is None:
            await ctx.send(f':warning: __{word}__ 단어를 찾을 수 없습니다.', delete_after=PERIOD)
            return
        message = await ctx.send(f':hourglass: __{word}__ 단어 정보를 불러오는 중입니다...')
        embed = economy_word.get_embed(ctx)
        embed.add_field(name='판매중', value=':o: 구매 가능' if market.is_on_sale(economy_word.id) else ':x: 구매 불가능')
        await message.edit(content=f':white_check_mark: __{word}__ 단어 정보를 불러왔습니다!',
                           embed=embed, delete_after=PERIOD)

    @cog_slash(
        name='rank',
        description='랭킹을 확인합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='kind',
                description='랭킹을 확인할 종류',
                option_type=SlashCommandOptionType.STRING,
                required=True,
                choices=['money', 'word', 'property']
            )
        ]
    )
    async def rank(self, ctx: SlashContext, kind: str):
        message = await ctx.send(f':hourglass: __{kind}__ 랭킹을 불러오는 중입니다...')
        field = list()
        if kind == 'money':
            for i, owner in enumerate(get_ranking_by_money(10)):
                user = self.bot.get_user(owner.id)
                field.append(f'{i + 1}. {user.display_name} ({format_money(owner.money)})')
        elif kind == 'word':
            for i, (word, fee, proceed) in enumerate(get_ranking_by_word(10)):
                user = self.bot.get_user(word.owner_id)
                field.append(f'{i + 1}. {word.word} '
                             f'({user.display_name}, {format_money(proceed)} / {format_money(fee)})')
        elif kind == 'property':
            for i, owner in enumerate(get_ranking_by_property(10)):
                user = self.bot.get_user(owner.id)
                field.append(f'{i + 1}. {user.display_name} ({format_money(owner.get_property())})')

        if not field:
            await ctx.send(f':warning: __{kind}__ 랭킹을 확인할 수 없습니다! 종류를 잘못 입력했거나 아직 사용자 또는 단어가 없습니다!',
                           delete_after=PERIOD)
            return
        embed = Embed(title=f'__{kind}__ 랭킹', color=YELLOW)
        embed.add_field(name='순위', value='\n'.join(field), inline=False)
        await message.edit(content=f':white_check_mark: __{kind}__ 랭킹을 불러왔습니다!', embed=embed, delete_after=PERIOD)

    @cog_slash(
        name='prices',
        description='단어의 가격을 확인합니다.',
        guild_ids=GUILDS,
    )
    async def prices(self, ctx: SlashContext):
        content = ':white_check_mark: 단어의 가격은 길이에 따라 다르며, 길이가 짧은 단어는 가격이 낮아집니다.'

        prices = list()
        for i in range(1, 11):
            rate = Word.get_price_rate(i)
            prices.append(f'> 길이가 {i}글자인 단어는 특허 등록 비용의 {rate * 100:.2f}%로, '
                          f'약 {round(1 / rate)}회 사용할 때 본전을 찾을 수 있습니다.')

        content += '\n' + '\n'.join(prices) + '\n'

        await ctx.send(content, delete_after=PERIOD)

    @cog_slash(
        name='exhibit',
        description='단어를 시장에 내놓습니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='word',
                description='내놓을 단어',
                option_type=SlashCommandOptionType.STRING,
                required=True
            ),
            create_option(
                name='price',
                description='내놓을 가격',
                option_type=SlashCommandOptionType.FLOAT,
                required=True
            )
        ]
    )
    async def exhibit(self, ctx: SlashContext, word: str, price: float):
        economy_word = Word.get_by_word(word)
        if economy_word is None:
            await ctx.send(f':warning: __{word}__ 단어를 찾을 수 없습니다.', delete_after=PERIOD)
            return
        if economy_word.owner_id != ctx.author_id:
            user = self.bot.get_user(economy_word.owner_id)
            await ctx.send(f':warning: __{economy_word.word}__ 단어를 소유하고 있지 않습니다. '
                           f'__{economy_word.word}__ 단어는 __{user.display_name}__님이 소유하고 있습니다.',
                           delete_after=PERIOD)
            return
        if market.is_on_sale(economy_word.id):
            await ctx.send(f':warning: __{economy_word.word}__ 단어는 이미 시장에 내놓여있습니다.', delete_after=PERIOD)
            return
        if price <= 0:
            await ctx.send(f':warning: 단어의 가격은 0보다 커야 합니다.', delete_after=PERIOD)
            return

        market.exhibit(economy_word, price)

        await ctx.send(f':white_check_mark: __{economy_word.word}__ 단어를 시장에 __{format_money(price)}__에 내놓았습니다.',
                       delete_after=PERIOD)

    @cog_slash(
        name='withhold',
        description='단어 출품을 취소합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='word',
                description='내놓은 단어',
                option_type=SlashCommandOptionType.STRING,
                required=True
            )
        ]
    )
    async def withhold(self, ctx: SlashContext, word: str):
        economy_word = Word.get_by_word(word)
        if economy_word is None:
            await ctx.send(f':warning: __{word}__ 단어를 찾을 수 없습니다.', delete_after=PERIOD)
            return
        if economy_word.owner_id != ctx.author_id:
            user = self.bot.get_user(economy_word.owner_id)
            await ctx.send(f':warning: __{economy_word.word}__ 단어를 소유하고 있지 않습니다. '
                           f'__{economy_word}__ 단어는 __{user.display_name}__님이 소유하고 있습니다.', delete_after=PERIOD)
            return
        if not market.is_on_sale(economy_word.id):
            await ctx.send(f':warning: __{economy_word.word}__ 단어는 시장에 내놓지 않았습니다.', delete_after=PERIOD)
            return

        owner = Owner.get_by_id(ctx.author_id)
        market.withhold(economy_word.id)
        owner.set_money(owner.money + economy_word.price)

        await ctx.send(f':white_check_mark: __{economy_word.word}__ 단어 출품을 취소했습니다.', delete_after=PERIOD)

        self.words = Word.get_all()

    @cog_slash(
        name='market',
        description='시장에 내놓은 단어를 확인합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='sort',
                description='정렬 방식을 선택합니다. (기본: `recent`)',
                option_type=SlashCommandOptionType.STRING,
                required=False,
                choices=['recent', 'price']
            )
        ]
    )
    async def market(self, ctx: SlashContext, sort: str = 'recent'):
        if sort == 'price':
            words = market.get_words_by_price()
        else:
            words = market.get_recent_words()

        if len(words) == 0:
            await ctx.send(f':warning: 시장에 내놓은 단어가 없습니다.', delete_after=PERIOD)
            return

        embed = Embed(title='시장', color=AQUA, description='정렬: ' + sort)
        for word in words:
            price = market.get_price(word.id)
            embed.add_field(name=f'{word.word} ({format_money(price)})',
                            value=f'**판매가**  {format_money(price)}\n'
                                  f'**원가**  {format_money(word.price)}\n'
                                  f'**현 소유자** {self.bot.get_user(word.owner_id).display_name}')
        await ctx.send(embed=embed, delete_after=PERIOD)

    @cog_slash(
        name='buy',
        description='시장에 내놓은 단어를 구매합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='word',
                description='구매할 단어',
                option_type=SlashCommandOptionType.STRING,
                required=True
            )
        ]
    )
    async def buy(self, ctx: SlashContext, word: str):
        economy_word = Word.get_by_word(word)
        if economy_word is None:
            await ctx.send(f':warning: __{word}__ 단어를 찾을 수 없습니다.', delete_after=PERIOD)
            return
        if not market.is_on_sale(economy_word.id):
            await ctx.send(f':warning: __{economy_word.word}__ 단어는 시장에 내놓지 않았습니다.', delete_after=PERIOD)
            return
        if economy_word.owner_id == ctx.author_id:
            await ctx.send(f':warning: __{economy_word.word}__ 단어는 이미 소유하고 있습니다.', delete_after=PERIOD)
            return
        buyer = Owner.get_by_id(ctx.author_id)
        price = market.get_price(economy_word.id)
        if buyer.money < price:
            await ctx.send(f':warning: 돈이 부족합니다. '
                           f'현재 가지고 있는 돈은 __{format_money(buyer.money)}__이고 '
                           f'단어는 __{format_money(price)}__이므로 '
                           f'__{format_money(price - buyer.money)}__{i_ga(CURRENCY_NAME)} 더 필요합니다.',
                           delete_after=PERIOD)
            return
        owner = Owner.get_by_id(economy_word.owner_id)
        buyer.set_money(buyer.money - price)
        owner.set_money(owner.money + price)
        market.buy(economy_word, buyer)
        await ctx.send(f':white_check_mark: __{economy_word.word}__ 단어를 구매했습니다.', delete_after=PERIOD)

        self.words = Word.get_all()

    @cog_slash(
        name='remit',
        description='돈을 송금합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='to',
                description='송금할 사람',
                option_type=SlashCommandOptionType.USER,
                required=True
            ),
            create_option(
                name='amount',
                description='송금할 금액',
                option_type=SlashCommandOptionType.FLOAT,
                required=True
            )
        ]
    )
    async def remit(self, ctx: SlashContext, to: User, amount: float):
        if amount <= 0:
            await ctx.send(f':warning: 송금할 금액은 0보다 커야 합니다.', delete_after=PERIOD)
            return
        if to.id == ctx.author_id:
            await ctx.send(f':warning: 자기 자신에게는 송금할 수 없습니다.', delete_after=PERIOD)
            return
        if amount > Owner.get_by_id(ctx.author_id).money:
            await ctx.send(
                f':warning: 돈이 부족합니다. '
                f'현재 가지고 있는 돈은 __{format_money(Owner.get_by_id(ctx.author_id).money)}__이고 '
                f'송금할 금액은 __{format_money(amount)}__이므로 '
                f'__{format_money(amount - Owner.get_by_id(ctx.author_id).money)}__{i_ga(CURRENCY_NAME)} '
                f'더 필요합니다.',
                delete_after=PERIOD)
            return
        from_owner = Owner.get_by_id(ctx.author_id)
        to_owner = Owner.get_by_id(to.id)
        from_owner.set_money(from_owner.money - amount)
        to_owner.set_money(to_owner.money + amount)
        await ctx.send(f':white_check_mark: __{format_money(amount)}__{eul_reul(CURRENCY_NAME)} 송금했습니다.',
                       delete_after=PERIOD)

    @cog_slash(
        name='log',
        description='단어 검출 기록을 확인합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='type_',
                description='기록의 종류를 선택합니다. (기본: `all`)',
                option_type=SlashCommandOptionType.STRING,
                required=False,
                choices=['i_paid', 'i_got', 'all']
            ),
            create_option(
                name='count',
                description='기록의 개수를 선택합니다. (기본: `10`)',
                option_type=SlashCommandOptionType.INTEGER,
                required=False
            )
        ]
    )
    async def log(self, ctx: SlashContext, type_: str = 'all', count: int = 10):
        message = await ctx.send(':hourglass: 기록을 가져오는 중입니다...')
        records = get_log(ctx.author_id, type_, count)
        lines = list()
        for i, (id_, datetime, user_id, word_id) in enumerate(records):
            user = self.bot.get_user(user_id)
            word = Word.get_by_id(word_id)
            lines.append(f'{i + 1}. {datetime}, {user.display_name}: {word.word}')
        embed = Embed(title='기록', description='\n'.join(lines), color=YELLOW)
        await message.edit(content=f':white_check_mark: `{type_}` 기록을 가져왔습니다.', embed=embed, delete_after=PERIOD)

    @cog_slash(
        name='discount',
        description='특정한 사용자에게 단어 사용 할인을 적용합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='user',
                description='할인을 적용할 사용자',
                option_type=SlashCommandOptionType.USER,
                required=True
            ),
            create_option(
                name='word',
                description='할인을 적용할 단어',
                option_type=SlashCommandOptionType.STRING,
                required=True
            ),
            create_option(
                name='discount',
                description='할인을 적용할 할인율 (0 ~ 100, 100으로 하면 전액 할인. 0으로 하면 할인을 취소합니다.)',
                option_type=SlashCommandOptionType.FLOAT,
                required=True
            )
        ]
    )
    async def discount(self, ctx: SlashContext, user: User, word: str, discount: float):
        if discount < 0 or discount > 100:
            await ctx.send(':warning: 할인은 0 ~ 100 사이의 값을 입력해야 합니다.', delete_after=PERIOD)
            return
        word = Word.get_by_word(word)
        if word is None:
            await ctx.send(':warning: 존재하지 않는 단어입니다.', delete_after=PERIOD)
            return
        if word.owner_id != ctx.author_id:
            await ctx.send(':warning: 자신의 단어만 할인을 적용할 수 있습니다.', delete_after=PERIOD)
            return
        preference_rate = 1 - discount / 100
        word.apply_preference(user.id, preference_rate)
        if preference_rate != 1:
            await ctx.send(f':white_check_mark: __{user.display_name}__에게 __{word.word}__ 단어를 '
                           f'__{discount}%__ 할인으로 적용했습니다.', delete_after=PERIOD)
        else:
            await ctx.send(f':white_check_mark: __{user.display_name}__에게 __{word.word}__ 단어의 할인을 취소했습니다.',
                           delete_after=PERIOD)
        self.words = Word.get_all()

    @cog_slash(
        name='debug_remove',
        description='사용자를 삭제합니다.',
        guild_ids=GUILDS,
    )
    async def debug_remove(self, ctx: SlashContext):
        if ctx.author.id not in DEVELOPERS:
            await ctx.send(f':warning: __{ctx.author.display_name}__님은 권한이 없습니다.', delete_after=PERIOD)
            return
        Owner.remove_owner(ctx.author.id)
        await ctx.send(f':white_check_mark: __{ctx.author.display_name}__ 사용자를 삭제했습니다.', delete_after=PERIOD)

    @cog_slash(
        name='debug_set_money',
        description='사용자의 소지금을 설정합니다.',
        guild_ids=GUILDS,
        options=[
            create_option(
                name='money',
                description='설정할 소지금',
                option_type=SlashCommandOptionType.FLOAT,
                required=True,
            ),
            create_option(
                name='user',
                description='소지금을 설정할 사용자',
                option_type=SlashCommandOptionType.USER,
                required=False
            )
        ]
    )
    async def debug_set_money(self, ctx: SlashContext, money: float, user: Optional[User] = None):
        if ctx.author.id not in DEVELOPERS:
            await ctx.send(f':warning: __{ctx.author.display_name}__님은 권한이 없습니다.', delete_after=PERIOD)
            return
        if user is None:
            user = ctx.author
        owner = Owner.get_by_id(user.id)
        if owner is None:
            await ctx.send(f':warning: __{user.display_name}__ 사용자를 찾을 수 없습니다.', delete_after=PERIOD)
            return
        owner.set_money(money)
        await ctx.send(f':white_check_mark: __{user.display_name}__님의 소지금을 '
                       f'__{format_money(money)}__로 설정했습니다.', delete_after=PERIOD)


def setup(bot: Bot):
    bot.add_cog(GeneralCog(bot))
