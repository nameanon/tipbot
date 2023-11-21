import sys
import traceback
from datetime import datetime
from decimal import Decimal
import time

import disnake
import store
from Bot import EMOJI_RED_NO, SERVER_BOT
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands
from cogs.utils import Utils, num_format_coin


class BotBalance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.botLogChan = None
        self.enable_logchan = True

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    async def bot_bal(self, ctx, member, token: str):
        if member.bot is False:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention} Only for bot! Use `/balance ticker` or `/balance` to check yours."
            await ctx.response.send_message(msg)
            return

        coin_name = token.upper()
        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.response.send_message(msg)
            return
        # End token name check

        msg = f"{ctx.author.mention}, checking {member.mention}'s balance."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/botbalance", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # Do the job
        try:
            try:
                coin_emoji = ""
                if ctx.guild.get_member(int(self.bot.user.id)).guild_permissions.external_emojis is True:
                    coin_emoji = getattr(getattr(self.bot.coin_list, coin_name), "coin_emoji_discord")
                    coin_emoji = f"{coin_emoji} " if coin_emoji else ""
            except Exception:
                traceback.print_exc(file=sys.stdout)

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(member.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(member.id), coin_name, net_name, type_coin, SERVER_BOT, 0, 0
                )

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

            height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
            description = ""
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            embed = disnake.Embed(
                title=f"Balance for Bot {member.name}#{member.discriminator}",
                description="This is for Bot's! Not yours!",
                timestamp=datetime.now()
            )
            embed.set_author(name=member.name, icon_url=member.display_avatar)
            try:
                # height can be None
                userdata_balance = await store.sql_user_balance_single(
                    str(member.id), coin_name, wallet_address, type_coin, height,
                    deposit_confirm_depth, SERVER_BOT
                )
                total_balance = userdata_balance['adjust']
                equivalent_usd = ""
                if price_with := getattr(
                    getattr(self.bot.coin_list, coin_name), "price_with"
                ):
                    per_unit = await self.utils.get_coin_price(coin_name, price_with)
                    if per_unit and per_unit['price'] and per_unit['price'] > 0:
                        per_unit = per_unit['price']
                        total_in_usd = float(Decimal(total_balance) * Decimal(per_unit))
                        if total_in_usd >= 0.01:
                            equivalent_usd = " ~ {:,.2f}$".format(total_in_usd)
                        elif total_in_usd >= 0.0001:
                            equivalent_usd = " ~ {:,.4f}$".format(total_in_usd)
                embed.add_field(
                    name=f"{coin_emoji}Token/Coin {token_display}{equivalent_usd}",
                    value=f"```Available: {num_format_coin(total_balance)} {token_display}```",
                    inline=False,
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
            embed.set_thumbnail(url=self.bot.user.display_avatar)
            embed.set_footer(
                text=f"Requested by: {ctx.author.name}#{ctx.author.discriminator}"
            )
            await ctx.edit_original_message(content=None, embed=embed)
            # Add update for future call
            try:
                await self.utils.update_user_balance_call(str(member.id), type_coin)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        usage="botbalance <bot> <coin>",
        options=[
            Option("botname", "Enter a bot", OptionType.user, required=True),
            Option("coin", "Enter coin ticker/name", OptionType.string, required=True),
        ],
        description="Get Bot's balance by mention it.")
    async def botbalance(
        self,
        ctx,
        botname: disnake.Member,
        coin: str
    ):
        await self.bot_bal(ctx, botname, coin)

    @botbalance.autocomplete("coin")
    async def coin_name_autocomp(self, inter: disnake.CommandInteraction, string: str):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]

def setup(bot):
    bot.add_cog(BotBalance(bot))
