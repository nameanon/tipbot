import random
import re
import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Dict
import asyncio
from cachetools import TTLCache

import disnake
import store
from Bot import num_format_coin, logchanbot, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_INFORMATION, SERVER_BOT, text_to_num, \
    truncate, seconds_str_days
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import ButtonStyle
from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from disnake.ext import commands, tasks
from config import config

from cogs.utils import Utils

class QuickDropButton(disnake.ui.View):
    message: disnake.Message
    channel_interact: disnake.TextChannel
    coin_list: Dict

    def __init__(self, ctx, timeout: float, coin_list, bot, channel_interact):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.coin_list = coin_list
        self.ctx = ctx
        self.channel_interact = channel_interact

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True

        ## Update content
        try:
            channel = self.bot.get_channel(self.channel_interact)
            _msg: disnake.Message = await channel.fetch_message(self.message.id)
            await _msg.edit(content=None, view=None)
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @disnake.ui.button(label="🎉 Collect", style=ButtonStyle.green, custom_id="quickdrop_tipbot")
    async def quick_collect(
        self, button: disnake.ui.Button,
        interaction: disnake.MessageInteraction
    ):
        pass


class QuickDrop(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.max_ongoing_by_user = 3
        self.max_ongoing_by_guild = 5
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.quickdrop_check.start()


    @tasks.loop(seconds=10.0)
    async def quickdrop_check(self):
        await self.bot.wait_until_ready()
        # Check if task recently run @bot_task_logs
        task_name = "quickdrop_check"
        check_last_running = await self.utils.bot_task_logs_check(task_name)
        if check_last_running and int(time.time()) - check_last_running['run_at'] < 5: # not running if less than 15s
            return
        try:
            get_list_quickdrops = await store.get_all_quickdrop("ONGOING")
            if len(get_list_quickdrops) > 0:
                for each_drop in get_list_quickdrops:
                    # print("Checkping quickdrop: {}".format(each_drop['message_id']))
                    try:
                        # Update view
                        owner_displayname = each_drop['from_ownername']
                        amount = each_drop['real_amount']
                        equivalent_usd = each_drop['real_amount_usd_text']

                        coin_name = each_drop['token_name']
                        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
                        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
                        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
                        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

                        # If party ends
                        if each_drop['expiring_time'] < int(time.time()):
                            embed = disnake.Embed(
                                title=f"📦📦📦 Quick Drop Ended! 📦📦📦",
                                description="First come, first serve!",
                                timestamp=datetime.fromtimestamp(each_drop['expiring_time']))
                            embed.set_footer(text=f"Dropped by {owner_displayname} | Used with /quickdrop | Ended")
                            embed.add_field(name='Owner',
                                            value=owner_displayname,
                                            inline=False)
                            if each_drop['collected_by_userid'] is None:
                                embed.add_field(name='Collected by',
                                                value="None",
                                                inline=False)
                            embed.add_field(name='Amount',
                                            value="🎉🎉 {} {} 🎉🎉".format(num_format_coin(amount, coin_name, coin_decimal, False), coin_name),
                                            inline=False)
                            try:
                                channel = self.bot.get_channel(int(each_drop['channel_id']))
                                _msg: disnake.Message = await channel.fetch_message(int(each_drop['message_id']))
                                await _msg.edit(content=None, embed=embed, view=None)
                                # Update balance
                                if each_drop['collected_by_userid'] is None:
                                    update_drop = await store.update_quickdrop_id_status(each_drop['message_id'], "NOCOLLECT")
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot("quickdrop_check " +str(traceback.format_exc()))
        # Update @bot_task_logs
        await self.utils.bot_task_logs_add(task_name, int(time.time()))

    async def async_quickdrop(self, ctx, amount: str, token: str):
        coin_name = token.upper()
        await ctx.response.send_message(f"{ctx.author.mention}, /quickdrop preparation... ")

        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM",
                                         str(ctx.author.id), SERVER_BOT, "/quickdrop", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # Token name check
        if len(self.bot.coin_alias_names) > 0 and coin_name in self.bot.coin_alias_names:
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f'{ctx.author.mention}, **{coin_name}** does not exist with us.'
            await ctx.edit_original_message(content=msg)
            return
        # End token name check

        serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
        if serverinfo and serverinfo['tiponly'] and serverinfo['tiponly'] != "ALLCOIN" and coin_name not in serverinfo[
            'tiponly'].split(","):
            allowed_coins = serverinfo['tiponly']
            msg = f'{ctx.author.mention}, **{coin_name}** is not allowed here. Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. `/SETTING TIPONLY coin1,coin2,...`'
            await ctx.edit_original_message(content=msg)
            return

        # if coin is allowed for partydrop
        if getattr(getattr(self.bot.coin_list, coin_name), "enable_quickdrop") != 1:
            msg = f'{ctx.author.mention}, **{coin_name}** not enable with `/quickdrop`'
            await ctx.edit_original_message(content=msg)
            return

        # Check if there is many airdrop/mathtip/triviatip/partydrop/quickdrop
        try:
            count_ongoing = await store.discord_freetip_ongoing(str(ctx.author.id), "ONGOING")
            if count_ongoing >= self.max_ongoing_by_user and ctx.author.id != config.discord.ownerID:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, you still have some ongoing tips. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                return
            count_ongoing = await store.discord_freetip_ongoing_guild(str(ctx.guild.id), "ONGOING")
            # Check max if set in guild
            if serverinfo and count_ongoing >= serverinfo['max_ongoing_drop'] and ctx.author.id != config.discord.ownerID:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or tips in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                return
            elif serverinfo is None and count_ongoing >= self.max_ongoing_by_guild and ctx.author.id != config.discord.ownerID:
                msg = f'{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or tips in this guild. Please wait for them to complete first!'
                await ctx.edit_original_message(content=msg)
                await logchanbot(f"[QUICKDROP] server {str(ctx.guild.id)} has no data in discord_server.")
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # End of ongoing check

        try:
            token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")

            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth")
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")

            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            usd_equivalent_enable = getattr(getattr(self.bot.coin_list, coin_name), "usd_equivalent_enable")
            get_deposit = await self.wallet_api.sql_get_userwallet(str(ctx.author.id), coin_name, net_name, type_coin,
                                                                   SERVER_BOT, 0)
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(str(ctx.author.id), coin_name, net_name,
                                                                      type_coin, SERVER_BOT, 0)

            wallet_address = get_deposit['balance_wallet_address']
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit['paymentid']
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit['destination_tag']

        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, some internal error. Please try again."
            await ctx.edit_original_message(content=msg)
            return

        height = self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        try:
            # Check amount
            if not amount.isdigit() and amount.upper() == "ALL":
                userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), coin_name, wallet_address,
                                                                       type_coin, height, deposit_confirm_depth, SERVER_BOT)
                amount = float(userdata_balance['adjust'])
            # If $ is in amount, let's convert to coin/token
            elif "$" in amount[-1] or "$" in amount[0]:  # last is $
                # Check if conversion is allowed for this coin.
                amount = amount.replace(",", "").replace("$", "")
                if usd_equivalent_enable == 0:
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                    coin_name_for_price = coin_name
                    if native_token_name:
                        coin_name_for_price = native_token_name
                    per_unit = None
                    if coin_name_for_price in self.bot.token_hints:
                        id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                        per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                    else:
                        per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                    if per_unit and per_unit > 0:
                        amount = float(Decimal(amount) / Decimal(per_unit))
                    else:
                        msg = f'{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. Try with different method.'
                        await ctx.edit_original_message(content=msg)
                        return
            else:
                amount = amount.replace(",", "")
                amount = text_to_num(amount)
                if amount is None:
                    msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid given minimum amount.'
                    await ctx.edit_original_message(content=msg)
                    return
            # end of check if amount is all

            # Check if tx in progress
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                msg = f'{EMOJI_ERROR} {ctx.author.mention}, you have another tx in progress.'
                await ctx.edit_original_message(content=msg)
                return

            try:
                amount = float(amount)
            except ValueError:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, invalid minimum amount.'
                await ctx.edit_original_message(content=msg)
                return

            default_duration = 60

            if amount <= 0:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}.'
                await ctx.edit_original_message(content=msg)
                return

            userdata_balance = await store.sql_user_balance_single(str(ctx.author.id), coin_name, wallet_address, type_coin,
                                                                   height, deposit_confirm_depth, SERVER_BOT)
            actual_balance = float(userdata_balance['adjust'])

            if amount > max_tip or amount < min_tip:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, amount cannot be bigger than **{num_format_coin(max_tip, coin_name, coin_decimal, False)} {token_display}** or smaller than **{num_format_coin(min_tip, coin_name, coin_decimal, False)} {token_display}**.'
                await ctx.edit_original_message(content=msg)
                return
            elif amount > actual_balance:
                msg = f'{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to drop **{num_format_coin(amount, coin_name, coin_decimal, False)} {token_display}**.'
                await ctx.edit_original_message(content=msg)
                return

            if ctx.author.id not in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.append(ctx.author.id)

            equivalent_usd = ""
            total_in_usd = 0.0
            per_unit = None
            if usd_equivalent_enable == 1:
                native_token_name = getattr(getattr(self.bot.coin_list, coin_name), "native_token_name")
                coin_name_for_price = coin_name
                if native_token_name:
                    coin_name_for_price = native_token_name
                if coin_name_for_price in self.bot.token_hints:
                    id = self.bot.token_hints[coin_name_for_price]['ticker_name']
                    per_unit = self.bot.coin_paprika_id_list[id]['price_usd']
                else:
                    per_unit = self.bot.coin_paprika_symbol_list[coin_name_for_price]['price_usd']
                if per_unit and per_unit > 0:
                    total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                    if total_in_usd >= 0.0001:
                        equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

            drop_end = int(time.time()) + 60
            owner_displayname = "{}#{}".format(ctx.author.name, ctx.author.discriminator)
            embed = disnake.Embed(
                title=f"📦📦📦 Quick Drop 📦📦📦",
                description="First come, first serve!",
                timestamp=datetime.now())
            embed.add_field(name='Owner',
                            value="{}#{}".format(ctx.author.name, ctx.author.discriminator),
                            inline=False)
            embed.add_field(name='Amount',
                            value="❔❔❔❔❔",
                            inline=False)
            embed.set_footer(text=f"Dropped by {owner_displayname} | Used with /quickdrop")
            try:
                view = QuickDropButton(ctx, default_duration, self.bot.coin_list, self.bot, ctx.channel.id) 
                msg = await ctx.channel.send(content=None, embed=embed, view=view)
                view.message = msg
                view.channel_interact = ctx.channel.id
                quick = await store.insert_quickdrop_create(coin_name, contract, str(ctx.author.id),
                                                            owner_displayname, str(view.message.id),
                                                            str(ctx.guild.id), str(ctx.channel.id), 
                                                            amount, total_in_usd,
                                                            equivalent_usd, per_unit, coin_decimal, 
                                                            drop_end, "ONGOING")
                await ctx.delete_original_message()
            except Exception:
                traceback.print_exc(file=sys.stdout)
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.remove(ctx.author.id)
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        usage='quickdrop <amount> <token>',
        options=[
            Option('amount', 'amount', OptionType.string, required=True),
            Option('token', 'token', OptionType.string, required=True)
        ],
        description="Quick drop and first people to collect when tap."
    )
    async def quickdrop(
        self,
        ctx,
        amount: str,
        token: str
    ):
        await self.async_quickdrop(ctx, amount, token)


def setup(bot):
    bot.add_cog(QuickDrop(bot))