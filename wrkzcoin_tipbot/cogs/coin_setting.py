import itertools
import sys
import traceback

import store
from attrdict import AttrDict
from Bot import logchanbot
from cogs.utils import Utils
from disnake.ext import commands


class CoinSetting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    async def get_list_bans(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `bot_blocklist`
                    """
                    await cur.execute(
                        sql,
                    )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [i["user_id"] for i in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_coin_setting(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    coin_list = {}
                    sql = """
                    SELECT * FROM `coin_settings` 
                    WHERE `enable`=1
                    """
                    await cur.execute(
                        sql,
                    )
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        for each in result:
                            coin_list[each["coin_name"]] = each
                        return coin_list
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_coin_list_name(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `coin_name` 
                    FROM `coin_settings` 
                    WHERE `enable`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [each["coin_name"] for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    # This token hints is priority
    async def get_token_hints(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_alias_price` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        hints = {}
                        hint_names = {}
                        for each_item in result:
                            hints[each_item["ticker"]] = each_item
                            hint_names[each_item["name"].upper()] = each_item
                        self.bot.token_hints = hints
                        self.bot.token_hint_names = hint_names
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_advert_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_advert_list` WHERE `enable`=1 """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        self.bot.advert_list = result
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_coin_alias_name(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_alias_name` """
                    await cur.execute(sql, ())
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        alias_names = {
                            each_item["alt_name"].upper(): each_item["coin_name"]
                            for each_item in result
                        }
                        self.bot.coin_alias_names = alias_names
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def get_faucet_coin_list(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT `coin_name` FROM `coin_settings` 
                    WHERE `enable`=1 AND `enable_faucet`=%s
                    """
                    await cur.execute(sql, (1))
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        return [each["coin_name"] for each in result]
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def cexswap_get_list_enable_pairs(self):
        list_pairs = []
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * 
                    FROM `coin_settings` 
                    WHERE `enable`=1 AND `cexswap_enable`=1 """
                    await cur.execute(
                        sql,
                    )
                    result = await cur.fetchall()
                    if result:
                        list_coins = sorted([i["coin_name"] for i in result])
                        self.bot.cexswap_coins = list_coins
                        list_pairs.extend(
                            f"{pair[0]}/{pair[1]}"
                            for pair in itertools.combinations(list_coins, 2)
                        )
                        if list_pairs:
                            self.bot.cexswap_pairs = list_pairs
                            return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    @commands.command(hidden=True, usage="config", description="Reload coin setting")
    async def config(self, ctx, cmd: str = None):
        if self.bot.config["discord"]["owner_id"] != ctx.author.id:
            await ctx.reply(f"{ctx.author.mention}, permission denied...")
            await logchanbot(
                f"{ctx.author.name}#{ctx.author.discriminator} tried to use `{ctx.command}`."
            )
            return

        try:
            if cmd is None:
                await ctx.reply(
                    f"{ctx.author.mention}, available for reload `coinlist, advertlist`"
                )
            elif cmd.lower() == "coinlist":
                coin_list = await self.get_coin_setting()
                if coin_list:
                    self.bot.coin_list = AttrDict(coin_list)
                    self.bot.other_data["coin_list"] = coin_list
                coin_list_name = await self.get_coin_list_name()
                if coin_list_name:
                    self.bot.coin_name_list = coin_list_name

                faucet_coins = await self.get_faucet_coin_list()
                if faucet_coins:
                    self.bot.faucet_coins = faucet_coins

                await self.cexswap_get_list_enable_pairs()
                await self.get_token_hints()
                await self.get_coin_alias_name()

                # check daily
                # reset
                self.bot.other_data["daily"] = {}
                for each_coin in self.bot.coin_name_list:
                    is_daily = getattr(
                        getattr(self.bot.coin_list, each_coin), "enable_daily"
                    )
                    amount_daily = getattr(
                        getattr(self.bot.coin_list, each_coin), "daily_amount"
                    )
                    if is_daily == 1 and amount_daily > 0:
                        self.bot.other_data["daily"][each_coin] = amount_daily
                # end of daily

                # check hourly
                # reset
                self.bot.other_data["hourly"] = {}
                for each_coin in self.bot.coin_name_list:
                    is_hourly = getattr(
                        getattr(self.bot.coin_list, each_coin), "enable_hourly"
                    )
                    amount_hourly = getattr(
                        getattr(self.bot.coin_list, each_coin), "hourly_amount"
                    )
                    if is_hourly == 1 and amount_hourly > 0:
                        self.bot.other_data["hourly"][each_coin] = amount_hourly
                # end of hourly

                # re-load ban list
                self.bot.other_data["ban_list"] = await self.get_list_bans()
                # re-load guild list
                await self.utils.bot_reload_guilds()
                # re-load ai tts model
                await self.utils.ai_reload_model_tts()

                await ctx.reply(
                    f"{ctx.author.mention}, cexswap list, coin list, name, coin aliases, daily, hourly reloaded..."
                )
                await logchanbot(
                    f"{ctx.author.name}#{ctx.author.discriminator} reloaded `{cmd}`."
                )
            elif cmd.lower() == "advertlist":
                await self.get_advert_list()
                await ctx.reply(f"{ctx.author.mention}, advert list reloaded...")
                await logchanbot(
                    f"{ctx.author.name}#{ctx.author.discriminator} reloaded `{cmd}`."
                )
            else:
                await ctx.reply(
                    f"{ctx.author.mention}, unknown command. Available for reload `coinlist`"
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(CoinSetting(bot))
