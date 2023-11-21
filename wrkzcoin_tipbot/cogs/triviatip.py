import random
import re
import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Dict

import disnake
import store
from Bot import (
    EMOJI_ERROR,
    EMOJI_INFORMATION,
    EMOJI_RED_NO,
    SERVER_BOT,
    logchanbot,
    text_to_num,
    truncate,
)
from cogs.utils import Utils, num_format_coin
from cogs.wallet import WalletAPI
from disnake.app_commands import Option
from disnake.enums import ButtonStyle, OptionType
from disnake.ext import commands


class MyTriviaBtn(disnake.ui.Button):
    def __init__(self, label, _style, _custom_id):
        super().__init__(label=label, style=_style, custom_id=_custom_id)


class TriviaButton(disnake.ui.View):
    message: disnake.Message
    a_index: int
    coin_list: Dict

    def __init__(
        self, bot, ctx, answer_list, answer_index: int, timeout: float, coin_list
    ):
        super().__init__(timeout=timeout)
        i = 0
        self.a_index = answer_index
        self.coin_list = coin_list
        self.bot = bot
        self.ctx = ctx
        for name in answer_list:
            custom_id = "trivia_answers_" + str(i)
            self.add_item(MyTriviaBtn(name, ButtonStyle.green, custom_id))
            i += 1

    async def on_timeout(self):
        i = 0
        for child in self.children:
            if isinstance(child, disnake.ui.Button):
                child.disabled = True
                if i == self.a_index:
                    child.style = ButtonStyle.red
                i += 1
        ## Update content
        get_triviatip = None
        try:
            original_message = await self.ctx.original_message()
            get_triviatip = await store.get_discord_triviatip_by_msgid(
                str(original_message.id)
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            return

        if get_triviatip is None:
            await logchanbot(
                f"[ERROR TRIVIA TIP] Failed timeout in guild {self.ctx.guild.name} / {self.ctx.guild.id}!"
            )
            return

        if get_triviatip["status"] == "ONGOING":
            answered_msg_id = await store.get_responders_by_message_id(
                str(self.message.id)
            )
            amount = get_triviatip["real_amount"]
            coin_name = get_triviatip["token_name"]
            get_triviatip["button_correct_answer"]
            owner_displayname = get_triviatip["from_owner_name"]
            coin_decimal = getattr(getattr(self.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.coin_list, coin_name), "contract")
            token_display = getattr(getattr(self.coin_list, coin_name), "display_name")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
            # get question from db:
            question = await store.get_q_db(get_triviatip["question_id"])
            total_answer = answered_msg_id["total"]

            indiv_amount_str = (
                num_format_coin(
                    truncate(amount / len(answered_msg_id["right_ids"]), 12)
                )
                if len(answered_msg_id["right_ids"]) > 0
                else num_format_coin(truncate(amount, 12))
            )
            indiv_amount = (
                truncate(amount / len(answered_msg_id["right_ids"]), 12)
                if len(answered_msg_id["right_ids"]) > 0
                else truncate(amount, 12)
            )

            answered_msg_id["right_ids"]
            each_amount_in_usd = 0.0
            try:
                coin_emoji = ""
                if (
                    self.ctx.guild.get_member(
                        int(self.bot.user.id)
                    ).guild_permissions.external_emojis
                    is True
                ):
                    coin_emoji = getattr(
                        getattr(self.coin_list, coin_name), "coin_emoji_discord"
                    )
                    coin_emoji = coin_emoji + " " if coin_emoji else ""
            except Exception:
                traceback.print_exc(file=sys.stdout)
            total_equivalent_usd = ""
            per_unit = None
            if price_with:
                per_unit = get_triviatip["unit_price_usd"]
                if per_unit and per_unit > 0 and len(answered_msg_id["right_ids"]) > 0:
                    each_amount_in_usd = per_unit * float(indiv_amount)
                    if each_amount_in_usd > 0.0001:
                        num = (
                            len(answered_msg_id["right_ids"])
                            if len(answered_msg_id["right_ids"]) > 0
                            else 1
                        )
                        total_equivalent_usd = " ~ {:,.4f} USD".format(
                            each_amount_in_usd * num
                        )
                elif (
                    per_unit and per_unit > 0 and len(answered_msg_id["right_ids"]) == 0
                ):
                    each_amount_in_usd = per_unit * float(indiv_amount)
                    total_equivalent_usd = " ~ {:,.4f} USD".format(each_amount_in_usd)

            embed = disnake.Embed(
                title=f"⁉️ TriviaTip {coin_emoji} {num_format_coin(amount)} "
                f"{token_display} - {total_equivalent_usd} Total answer {total_answer}",
                description=get_triviatip["question_content"],
                timestamp=datetime.fromtimestamp(get_triviatip["trivia_endtime"]),
            )
            embed.add_field(
                name="Category (credit: {})".format(question["credit"]),
                value=question["category"],
                inline=False,
            )
            embed.add_field(
                name="Correct answer",
                value=get_triviatip["button_correct_answer"],
                inline=False,
            )
            embed.add_field(
                name="Correct ( {} )".format(len(answered_msg_id["right_ids"])),
                value="{}".format(
                    " | ".join(answered_msg_id["right_names"])
                    if len(answered_msg_id["right_names"]) > 0
                    else "N/A"
                ),
                inline=False,
            )
            embed.add_field(
                name="Incorrect ( {} )".format(len(answered_msg_id["wrong_ids"])),
                value="{}".format(
                    " | ".join(answered_msg_id["wrong_names"])
                    if len(answered_msg_id["wrong_names"]) > 0
                    else "N/A"
                ),
                inline=False,
            )
            if len(answered_msg_id["right_ids"]) > 0:
                embed.add_field(
                    name="Each Winner Receives:",
                    value=f"{coin_emoji}{indiv_amount_str} {token_display}",
                    inline=True,
                )
            embed.set_footer(text=f"TriviaTip by {owner_displayname}")

            if len(answered_msg_id["right_ids"]) > 0:
                await store.sql_user_balance_mv_multiple(
                    get_triviatip["from_userid"],
                    answered_msg_id["right_ids"],
                    get_triviatip["guild_id"],
                    get_triviatip["channel_id"],
                    float(indiv_amount),
                    coin_name,
                    "TRIVIATIP",
                    coin_decimal,
                    SERVER_BOT,
                    contract,
                    float(each_amount_in_usd),
                    None,
                )
            # Change status
            await store.discord_triviatip_update(
                get_triviatip["message_id"], "COMPLETED"
            )
            await original_message.edit(embed=embed, view=self)
        else:
            await original_message.edit(view=self)


class TriviaTips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)

        self.trivia_duration_min = 5
        self.trivia_duration_max = 45

        self.max_ongoing_by_user = self.bot.config["discord"]["max_ongoing_by_user"]
        self.max_ongoing_by_guild = self.bot.config["discord"]["max_ongoing_by_guild"]

    async def async_triviatip(self, ctx, amount: str, token: str, duration: str):
        coin_name = token.upper()
        # Token name check
        if (
            len(self.bot.coin_alias_names) > 0
            and coin_name in self.bot.coin_alias_names
        ):
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = f"{ctx.author.mention}, **{coin_name}** does not exist with us."
            await ctx.response.send_message(msg)
            return
        # End token name check

        await ctx.response.send_message(
            f"{ctx.author.mention}, /triviatip preparation... "
        )
        serverinfo = self.bot.other_data["guild_list"].get(str(ctx.guild.id))
        if (
            serverinfo
            and serverinfo["tiponly"]
            and serverinfo["tiponly"] != "ALLCOIN"
            and coin_name not in serverinfo["tiponly"].split(",")
        ):
            allowed_coins = serverinfo["tiponly"]
            msg = (
                f"{ctx.author.mention}, **{coin_name}** is not allowed here. "
                f"Currently, allowed `{allowed_coins}`. You can ask guild owner to allow. "
                f"`/SETTING TIPONLY coin1,coin2,...`"
            )
            await ctx.edit_original_message(content=msg)
            return

        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/triviatip",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        # check lock
        try:
            is_user_locked = self.utils.is_locked_user(str(ctx.author.id), SERVER_BOT)
            if is_user_locked is True:
                await ctx.edit_original_message(
                    content=f"{EMOJI_RED_NO} {ctx.author.mention}, your account is locked for using the Bot. "
                    "Please contact bot dev by /about link."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # end check lock

        # Check if there is many airdrop/mathtip/triviatip
        try:
            count_ongoing = await store.discord_freetip_ongoing(
                str(ctx.author.id), "ONGOING"
            )
            if (
                count_ongoing >= self.max_ongoing_by_user
                and ctx.author.id != self.bot.config["discord"]["owner_id"]
            ):
                msg = (
                    f"{EMOJI_INFORMATION} {ctx.author.mention}, you still have some ongoing tips. "
                    "Please wait for them to complete first!"
                )
                await ctx.edit_original_message(content=msg)
                return
            count_ongoing = await store.discord_freetip_ongoing_guild(
                str(ctx.guild.id), "ONGOING"
            )
            # Check max if set in guild
            if (
                serverinfo
                and count_ongoing >= serverinfo["max_ongoing_drop"]
                and ctx.author.id != self.bot.config["discord"]["owner_id"]
            ):
                msg = (
                    f"{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or "
                    "tips in this guild. Please wait for them to complete first!"
                )
                await ctx.edit_original_message(content=msg)
                return
            elif (
                serverinfo is None
                and count_ongoing >= self.max_ongoing_by_guild
                and ctx.author.id != self.bot.config["discord"]["owner_id"]
            ):
                msg = (
                    f"{EMOJI_INFORMATION} {ctx.author.mention}, there are still some ongoing drops or "
                    "tips in this guild. Please wait for them to complete first!"
                )
                await ctx.edit_original_message(content=msg)
                await logchanbot(
                    f"[TRIVIATIP] server {str(ctx.guild.id)} has no data in discord_server."
                )
                return
        except Exception:
            traceback.print_exc(file=sys.stdout)
        # End of ongoing check

        try:
            token_display = getattr(
                getattr(self.bot.coin_list, coin_name), "display_name"
            )
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            try:
                coin_emoji = ""
                if (
                    ctx.guild.get_member(
                        int(self.bot.user.id)
                    ).guild_permissions.external_emojis
                    is True
                ):
                    coin_emoji = getattr(
                        getattr(self.bot.coin_list, coin_name), "coin_emoji_discord"
                    )
                    coin_emoji = coin_emoji + " " if coin_emoji else ""
            except Exception:
                traceback.print_exc(file=sys.stdout)
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(
                getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth"
            )
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")

            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(ctx.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
                )

            wallet_address = get_deposit["balance_wallet_address"]
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit["paymentid"]
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit["destination_tag"]

        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, some internal error. Please try again."
            await ctx.edit_original_message(content=msg)
            return

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        # check if amount is all
        if not amount.isdigit() and amount.upper() == "ALL":
            userdata_balance = await store.sql_user_balance_single(
                str(ctx.author.id),
                coin_name,
                wallet_address,
                type_coin,
                height,
                deposit_confirm_depth,
                SERVER_BOT,
            )
            amount = float(userdata_balance["adjust"])
        # If $ is in amount, let's convert to coin/token
        elif "$" in amount[-1] or "$" in amount[0]:  # last is $
            # Check if conversion is allowed for this coin.
            amount = amount.replace(",", "").replace("$", "")
            if price_with is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, dollar conversion is not enabled for this `{coin_name}`."
                await ctx.edit_original_message(content=msg)
                return
            else:
                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                if per_unit and per_unit["price"] and per_unit["price"] > 0:
                    per_unit = per_unit["price"]
                    amount = float(Decimal(amount) / Decimal(per_unit))
                else:
                    msg = (
                        f"{EMOJI_RED_NO} {ctx.author.mention}, I cannot fetch equivalent price. "
                        "Try with different method."
                    )
                    await ctx.edit_original_message(content=msg)
                    return
        else:
            amount = amount.replace(",", "")
            amount = text_to_num(amount)
            if amount is None:
                msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid given amount."
                await ctx.edit_original_message(content=msg)
                return
        # end of check if amount is all

        # Check if tx in progress
        if (
            str(ctx.author.id) in self.bot.tipping_in_progress
            and int(time.time()) - self.bot.tipping_in_progress[str(ctx.author.id)]
            < 150
        ):
            msg = f"{EMOJI_ERROR} {ctx.author.mention}, you have another transaction in progress."
            await ctx.edit_original_message(content=msg)
            return

        def hms_to_seconds(time_string):
            duration_in_second = 0
            if time_string.isdigit():
                return int(time_string)
            try:
                time_string = time_string.replace("hours", "h")
                time_string = time_string.replace("hour", "h")
                time_string = time_string.replace("hrs", "h")
                time_string = time_string.replace("hr", "h")

                time_string = time_string.replace("minutes", "mn")
                time_string = time_string.replace("mns", "mn")
                time_string = time_string.replace("mins", "mn")
                time_string = time_string.replace("min", "mn")
                time_string = time_string.replace("mn", "mn")
                mult = {"h": 60 * 60, "mn": 60, "s": 1}
                duration_in_second = sum(
                    int(num) * mult.get(val, 1)
                    for num, val in re.findall("(\d+)(\w+)", time_string)
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
            return duration_in_second

        default_duration = 60
        duration_s = 0
        try:
            duration_s = hms_to_seconds(duration)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid duration."
            await ctx.edit_original_message(content=msg)
            return

        if duration_s == 0:
            # Skip message
            duration_s = default_duration
            # Just info, continue
        elif (
            duration_s < self.trivia_duration_min
            or duration_s > self.trivia_duration_max
        ):
            msg = (
                f"{EMOJI_RED_NO} {ctx.author.mention} Invalid duration. "
                f"Please use between {str(self.trivia_duration_min)}s "
                f"to {str(self.trivia_duration_max)}s."
            )
            await ctx.edit_original_message(content=msg)
            return

        try:
            amount = float(amount)
        except ValueError:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, invalid amount."
            await ctx.edit_original_message(content=msg)
            return

        # Get random question
        rand_q = await store.get_random_q_db("ANY")
        if rand_q is None:
            msg = f"{EMOJI_RED_NO} {ctx.author.mention}, internal error, please report."
            await ctx.edit_original_message(content=msg)
            return

        userdata_balance = await store.sql_user_balance_single(
            str(ctx.author.id),
            coin_name,
            wallet_address,
            type_coin,
            height,
            deposit_confirm_depth,
            SERVER_BOT,
        )
        actual_balance = float(userdata_balance["adjust"])

        if amount <= 0 or actual_balance <= 0:
            msg = (
                f"{EMOJI_RED_NO} {ctx.author.mention}, please get more {token_display}."
            )
            await ctx.edit_original_message(content=msg)
            return

        if amount > max_tip or amount < min_tip:
            msg = (
                f"{EMOJI_RED_NO} {ctx.author.mention}, transactions cannot be "
                f"bigger than **{num_format_coin(max_tip)} "
                f"{token_display}** or smaller than **{num_format_coin(min_tip)} "
                f"{token_display}**."
            )
            await ctx.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = (
                f"{EMOJI_RED_NO} {ctx.author.mention}, insufficient balance to do a trivia "
                f"tip of **{num_format_coin(amount)} {token_display}**."
            )
            await ctx.edit_original_message(content=msg)
            return

        if str(ctx.author.id) not in self.bot.tipping_in_progress:
            self.bot.tipping_in_progress[str(ctx.author.id)] = int(time.time())

        equivalent_usd = ""
        total_in_usd = 0.0
        per_unit = None
        if price_with:
            per_unit = await self.utils.get_coin_price(coin_name, price_with)
            if per_unit and per_unit["price"] and per_unit["price"] > 0:
                per_unit = per_unit["price"]
                total_in_usd = float(Decimal(amount) * Decimal(per_unit))
                if total_in_usd >= 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(total_in_usd)

        trivia_end = int(time.time()) + duration_s
        owner_displayname = "{}#{}".format(ctx.author.name, ctx.author.discriminator)
        embed = disnake.Embed(
            title=f"⁉️ Trivia Tip {coin_emoji} {num_format_coin(amount)} {token_display} {equivalent_usd}",
            description=rand_q["question"],
            timestamp=datetime.fromtimestamp(trivia_end),
        )
        embed.add_field(
            name="Category (credit: {})".format(rand_q["credit"]),
            value=rand_q["category"],
            inline=False,
        )
        embed.add_field(name="Answering", value="None", inline=False)
        embed.set_footer(text=f"Trivia tip by {owner_displayname}")
        if rand_q and rand_q["type"] == "MULTIPLE":
            answers = [
                rand_q["correct_answer"],
                rand_q["incorrect_answer_1"],
                rand_q["incorrect_answer_2"],
                rand_q["incorrect_answer_3"],
            ]
            random.shuffle(answers)
            index_answer = answers.index(rand_q["correct_answer"])

            try:
                view = TriviaButton(
                    self.bot, ctx, answers, index_answer, duration_s, self.bot.coin_list
                )
                view.message = await ctx.original_message()
                # Insert to trivia ongoing list
                await store.insert_discord_triviatip(
                    coin_name,
                    contract,
                    str(ctx.author.id),
                    owner_displayname,
                    str(view.message.id),
                    rand_q["question"],
                    rand_q["id"],
                    rand_q["correct_answer"],
                    str(ctx.guild.id),
                    str(ctx.channel.id),
                    amount,
                    total_in_usd,
                    equivalent_usd,
                    per_unit,
                    coin_decimal,
                    trivia_end,
                    net_name,
                    "ONGOING",
                )
                await ctx.edit_original_message(content=None, embed=embed, view=view)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        elif rand_q and rand_q["type"] == "BOOLEAN":
            answers = [rand_q["correct_answer"], rand_q["incorrect_answer_1"]]
            random.shuffle(answers)
            index_answer = answers.index(rand_q["correct_answer"])
            try:
                view = TriviaButton(
                    self.bot, ctx, answers, index_answer, duration_s, self.bot.coin_list
                )
                view.message = await ctx.original_message()
                # Insert to trivia ongoing list
                await store.insert_discord_triviatip(
                    coin_name,
                    contract,
                    str(ctx.author.id),
                    owner_displayname,
                    str(view.message.id),
                    rand_q["question"],
                    rand_q["id"],
                    rand_q["correct_answer"],
                    str(ctx.guild.id),
                    str(ctx.channel.id),
                    amount,
                    total_in_usd,
                    equivalent_usd,
                    per_unit,
                    coin_decimal,
                    trivia_end,
                    net_name,
                    "ONGOING",
                )
                await ctx.edit_original_message(content=None, embed=embed, view=view)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        try:
            del self.bot.tipping_in_progress[str(ctx.author.id)]
        except Exception:
            pass

    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    @commands.slash_command(
        dm_permission=False,
        usage="triviatip <amount> <token> <duration>",
        options=[
            Option("amount", "amount", OptionType.string, required=True),
            Option("token", "token", OptionType.string, required=True),
            Option("duration", "duration", OptionType.string, required=True),
        ],
        description="Spread trivia tip",
    )
    async def triviatip(self, ctx, amount: str, token: str, duration: str):
        await self.async_triviatip(ctx, amount, token, duration)

    @triviatip.autocomplete("token")
    async def triviatip_token_name_autocomp(
        self, inter: disnake.CommandInteraction, string: str
    ):
        string = string.lower()
        return [name for name in self.bot.coin_name_list if string in name.lower()][:10]


def setup(bot):
    bot.add_cog(TriviaTips(bot))
