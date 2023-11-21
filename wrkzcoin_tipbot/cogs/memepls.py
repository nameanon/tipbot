# For hash file in case already have
import hashlib
import sys
import time
import traceback
import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import aiohttp
import disnake
import magic
import store
from Bot import EMOJI_ERROR, EMOJI_RED_NO, SERVER_BOT, logchanbot, text_to_num
from cogs.utils import MenuPage, Utils, num_format_coin
from cogs.wallet import WalletAPI
from disnake import ButtonStyle, TextInputStyle
from disnake.app_commands import Option, OptionChoice
from disnake.enums import OptionType
from disnake.ext import commands


# Tip
async def add_memetip(
    meme_id: str,
    owner_userid: str,
    from_userid: str,
    guild_id: str,
    channel_id: str,
    real_amount: float,
    coin: str,
    token_decimal: int,
    contract: str,
    real_amount_usd: float,
):
    try:
        token_name = coin.upper()
        currentTs = int(time.time())
        to_userid = owner_userid
        tiptype = "MEMETIP"
        user_server = SERVER_BOT
        tipped_comment = None
        await store.openConnection()
        async with store.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ INSERT INTO `meme_tipped` (`meme_id`, `owner_userid`, `tipped_by`, `tipped_amount`, `real_amount_usd`, `tipped_coin`, `tipped_guild`, 
                          `tipped_channel`, `tipped_date`, `tipped_comment`)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);

                          UPDATE `meme_uploaded` SET `number_tipped`=`number_tipped`+1 WHERE `key`=%s LIMIT 1;

                          INSERT INTO user_balance_mv 
                          (`token_name`, `contract`, `from_userid`, `to_userid`, `guild_id`, `channel_id`, `real_amount`, `real_amount_usd`, `token_decimal`, `type`, `date`, `user_server`) 
                          VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS DECIMAL(32,8)), CAST(%s AS DECIMAL(32,8)), %s, %s, %s, %s);

                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);

                          INSERT INTO user_balance_mv_data (`user_id`, `token_name`, `user_server`, `balance`, `update_date`) 
                          VALUES (%s, %s, %s, CAST(%s AS DECIMAL(32,8)), %s) ON DUPLICATE KEY 
                          UPDATE 
                          `balance`=`balance`+VALUES(`balance`), 
                          `update_date`=VALUES(`update_date`);

                          """
                await cur.execute(
                    sql,
                    (
                        meme_id,
                        owner_userid,
                        from_userid,
                        real_amount,
                        real_amount_usd,
                        token_name,
                        guild_id,
                        channel_id,
                        currentTs,
                        tipped_comment,
                        meme_id,
                        token_name,
                        contract,
                        from_userid,
                        to_userid,
                        guild_id,
                        channel_id,
                        real_amount,
                        real_amount_usd,
                        token_decimal,
                        tiptype,
                        currentTs,
                        user_server,
                        from_userid,
                        token_name,
                        user_server,
                        -real_amount,
                        currentTs,
                        to_userid,
                        token_name,
                        user_server,
                        real_amount,
                        currentTs,
                    ),
                )
                await conn.commit()
                return cur.rowcount
    except Exception:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())
    return 0


class MemeTipReport(disnake.ui.Modal):
    def __init__(self, ctx, bot, meme_id: str, owner_userid: str, get_meme) -> None:
        self.meme_web_path = self.bot.config["discord"]["meme_web_path"]
        self.ctx = ctx
        self.bot = bot
        self.utils = Utils(self.bot)
        self.meme_id = meme_id
        self.owner_userid = owner_userid
        self.get_meme = get_meme
        self.meme_channel_upload = self.bot.config["discord"]["meme_upload_channel_log"]
        components = [
            disnake.ui.TextInput(
                label="Your contact",
                placeholder="How we contact you",
                custom_id="contact_id",
                style=TextInputStyle.short,
                max_length=64,
            ),
            disnake.ui.TextInput(
                label="Description",
                placeholder="Describe about it.",
                custom_id="desc_id",
                style=TextInputStyle.paragraph,
            ),
        ]
        super().__init__(
            title="Report about meme",
            custom_id="modal_meme_report",
            components=components,
        )

    # meme_report
    async def meme_report(
        self,
        report_id: str,
        meme_id: str,
        owner_userid: str,
        reported_by_uid: str,
        reported_by_name: str,
        contact_id: str,
        desc_id: str,
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `meme_reported` 
                    (`report_id`, `meme_id`, `owner_userid`, `reported_by_uid`, `reported_by_name`, 
                    `contact_id`, `desc_id`, `submitted_date`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(
                        sql,
                        (
                            report_id,
                            meme_id,
                            owner_userid,
                            reported_by_uid,
                            reported_by_name,
                            contact_id,
                            desc_id,
                            int(time.time()),
                        ),
                    )
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            await logchanbot(traceback.format_exc())
        return 0

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        try:
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, checking meme reporting..."
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, failed to execute meme reporting. Try again later!",
                ephemeral=True,
            )
            return
        contact_id = interaction.text_values["contact_id"].strip()
        if contact_id == "" or len(contact_id) < 4:
            await interaction.edit_original_message(
                content=f"{interaction.author.mention}, contact is too short!"
            )
            return

        desc_id = interaction.text_values["desc_id"].strip()
        if desc_id == "" or len(desc_id) < 8:
            await interaction.edit_original_message(
                content=f"{interaction.author.mention}, description is too short!"
            )
            return
        report_id = str(uuid.uuid4())
        report = await self.meme_report(
            report_id,
            self.meme_id,
            self.owner_userid,
            interaction.author.id,
            "{}#{}".format(interaction.author.name, interaction.author.discriminator),
            contact_id,
            desc_id,
        )
        if report > 0:
            await interaction.edit_original_message(
                content=f"{interaction.author.mention}, thank you for your report! ID: `{report_id}`."
            )
            try:
                msg = (
                    f"[MEME REPORT] A user {interaction.author.mention} / "
                    f"{interaction.author.name}#{interaction.author.discriminator} has submitted a report "
                    f"`{report_id}` about meme `{self.meme_id}` uploaded by <@{self.owner_userid}>."
                )
                embed = disnake.Embed(
                    title="MEME REPORT!",
                    description="Caption: {}".format(self.get_meme["caption"]),
                    timestamp=datetime.now(),
                )
                embed.add_field(
                    name="Uploader",
                    value="<@{}>".format(self.owner_userid),
                    inline=False,
                )
                embed.add_field(
                    name="Uploaded Guild/Chan",
                    value="`{}/{}`".format(
                        self.get_meme["guild_id"], self.get_meme["channel_id"]
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="ID", value="`{}`".format(self.get_meme["key"]), inline=False
                )
                embed.add_field(
                    name="Hash",
                    value="`{}`".format(self.get_meme["sha256"]),
                    inline=False,
                )
                embed.set_author(
                    name=self.bot.user.name, icon_url=self.bot.user.display_avatar
                )
                embed.set_image(url=self.meme_web_path + self.get_meme["saved_name"])
                channel = self.bot.get_channel(self.meme_channel_upload)
                await channel.send(content=msg, embed=embed)
            except Exception:
                traceback.print_exc(file=sys.stdout)
        else:
            await interaction.edit_original_message(
                content=f"{interaction.author.mention}, internal error, please report!"
            )


class TipOtherCoin(disnake.ui.Modal):
    def __init__(self, ctx, bot, meme_id: str, owner_userid: str, get_meme) -> None:
        self.meme_web_path = self.bot.config["discord"]["meme_web_path"]
        self.ctx = ctx
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.meme_id = meme_id
        self.owner_userid = owner_userid
        self.get_meme = get_meme
        self.meme_tip_channel = self.bot.config["discord"][
            "meme_tip_channel"
        ]  # memetip
        components = [
            disnake.ui.TextInput(
                label="Amount",
                placeholder="10000",
                custom_id="amount_id",
                style=TextInputStyle.short,
                max_length=16,
            ),
            disnake.ui.TextInput(
                label="Coin/Token Name",
                placeholder="WRKZ",
                custom_id="coin_id",
                style=TextInputStyle.short,
                max_length=16,
            ),
        ]
        super().__init__(
            title="Tip Your Own Amount",
            custom_id="modal_memetip",
            components=components,
        )

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        # Check if type of question is bool or multipe
        try:
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, checking meme tipping..."
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, failed to execute meme tipping. Try again later!",
                ephemeral=True,
            )
            return
        amount = interaction.text_values["amount_id"].strip()
        if amount == "":
            await interaction.edit_original_message(
                f"{interaction.author.mention}, amount is empty!"
            )
            return
        coin_id = interaction.text_values["coin_id"].strip()
        if coin_id == "":
            await interaction.edit_original_message(
                f"{interaction.author.mention}, COIN is empty!"
            )
            return

        amount = amount.replace(",", "")
        amount = text_to_num(amount)
        if amount is None:
            msg = f"{EMOJI_RED_NO} {interaction.author.mention}, invalid given amount."
            await interaction.edit_original_message(content=msg)
            return

        amount = float(amount)
        coin_name = coin_id.upper()
        if (
            len(self.bot.coin_alias_names) > 0
            and coin_name in self.bot.coin_alias_names
        ):
            coin_name = self.bot.coin_alias_names[coin_name]
        if not hasattr(self.bot.coin_list, coin_name):
            msg = (
                f"{interaction.author.mention}, **{coin_name}** does not exist with us."
            )
            await interaction.edit_original_message(content=msg)
            return
        net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
        type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
        deposit_confirm_depth = getattr(
            getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth"
        )
        coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
        contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
        token_display = getattr(getattr(self.bot.coin_list, coin_name), "display_name")

        min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
        max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
        price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
        get_deposit = await self.wallet_api.sql_get_userwallet(
            str(interaction.author.id), coin_name, net_name, type_coin, SERVER_BOT, 0
        )
        if get_deposit is None:
            get_deposit = await self.wallet_api.sql_register_user(
                str(interaction.author.id),
                coin_name,
                net_name,
                type_coin,
                SERVER_BOT,
                0,
                0,
            )

        wallet_address = get_deposit["balance_wallet_address"]
        if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
            wallet_address = get_deposit["paymentid"]
        elif type_coin in ["XRP"]:
            wallet_address = get_deposit["destination_tag"]

        # Check if tx in progress
        if (
            str(interaction.author.id) in self.bot.tipping_in_progress
            and int(time.time())
            - self.bot.tipping_in_progress[str(interaction.author.id)]
            < 150
        ):
            msg = f"{EMOJI_ERROR} {interaction.author.mention}, you have another transaction in progress."
            await interaction.edit_original_message(content=msg)
            return

        height = await self.wallet_api.get_block_height(type_coin, coin_name, net_name)
        userdata_balance = await store.sql_user_balance_single(
            str(interaction.author.id),
            coin_name,
            wallet_address,
            type_coin,
            height,
            deposit_confirm_depth,
            SERVER_BOT,
        )
        actual_balance = float(userdata_balance["adjust"])
        if amount <= 0:
            msg = f"{EMOJI_RED_NO} {interaction.author.mention}, please get more {token_display}."
            await interaction.edit_original_message(content=msg)
            return
        elif amount > actual_balance:
            msg = (
                f"{EMOJI_RED_NO} {self.ctx.author.mention}, insufficient balance to give meme tip of "
                f"**{num_format_coin(amount)} {token_display}**."
            )
            await interaction.edit_original_message(content=msg)
            return
        elif amount > max_tip or amount < min_tip:
            msg = (
                f"{EMOJI_RED_NO} {self.ctx.author.mention}, tipping cannot be bigger than "
                f"**{num_format_coin(max_tip)} {token_display}** or smaller than "
                f"**{num_format_coin(min_tip)} {token_display}**."
            )
            await interaction.edit_original_message(content=msg)
            return
        equivalent_usd = ""
        amount_in_usd = 0.0
        if price_with:
            per_unit = await self.utils.get_coin_price(coin_name, price_with)
            if per_unit and per_unit["price"] and per_unit["price"] > 0:
                per_unit = per_unit["price"]
                amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                if amount_in_usd > 0.0001:
                    equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)

        if str(interaction.author.id) not in self.bot.tipping_in_progress:
            self.bot.tipping_in_progress[str(interaction.author.id)] = int(time.time())
        user_to = await self.wallet_api.sql_get_userwallet(
            self.owner_userid, coin_name, net_name, type_coin, SERVER_BOT, 0
        )
        if user_to is None:
            user_to = await self.wallet_api.sql_register_user(
                self.owner_userid, coin_name, net_name, type_coin, SERVER_BOT, 0
            )
        try:
            guild_id = "DM"
            channel_id = "DM"
            guild_name = " in DM"
            if hasattr(interaction, "guild") and hasattr(interaction.guild, "id"):
                guild_id = interaction.guild.id
                channel_id = interaction.channel.id
                guild_name = " in Guild {}".format(interaction.guild.name)
            tip = await add_memetip(
                self.meme_id,
                self.owner_userid,
                str(interaction.author.id),
                guild_id,
                channel_id,
                amount,
                coin_name,
                coin_decimal,
                contract,
                amount_in_usd,
            )
            if tip > 0:
                url_image = self.meme_web_path + self.get_meme["saved_name"]
                try:
                    msg = "A user ({}) has tipped to your meme `{}` with amount `{} {}`{}. Cheers!\n{}".format(
                        interaction.author.mention,
                        self.meme_id,
                        amount,
                        coin_name,
                        guild_name,
                        url_image,
                    )
                    get_meme_owner = self.bot.get_user(int(self.owner_userid))
                    await get_meme_owner.send(content=msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                msg = (
                    f"{interaction.author.mention}, you tipped **{num_format_coin(amount)} "
                    f"{token_display}** to meme `{self.meme_id}` by <@{self.owner_userid}>."
                )
                await interaction.edit_original_message(content=msg)
                try:
                    embed = disnake.Embed(
                        title="A meme got tipped{}!".format(guild_name),
                        description=f"Share your meme and get tipped!",
                        timestamp=datetime.now(),
                    )
                    embed.add_field(
                        name="Tipped with",
                        value="{} {}".format(amount, coin_name),
                        inline=True,
                    )
                    embed.add_field(
                        name="Uploader",
                        value="<@{}>".format(self.owner_userid),
                        inline=True,
                    )
                    embed.add_field(
                        name="ID",
                        value="`{}`".format(self.get_meme["key"]),
                        inline=False,
                    )
                    embed.set_author(
                        name=self.bot.user.name, icon_url=self.bot.user.display_avatar
                    )
                    embed.set_image(url=url_image)
                    embed.set_footer(
                        text="Tipped by: {}#{}".format(
                            interaction.author.name, interaction.author.discriminator
                        )
                    )
                    channel = self.bot.get_channel(self.meme_tip_channel)
                    await channel.send(embed=embed)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        try:
            del self.bot.tipping_in_progress[str(interaction.author.id)]
        except Exception:
            pass


class MemeTip_Button(disnake.ui.View):
    message: disnake.Message

    def __init__(
        self, ctx, bot, timeout: float, meme_id: str, owner_userid: int, get_meme
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.ctx = ctx
        self.meme_id = meme_id
        self.owner_userid = owner_userid
        self.meme_tip_channel = self.bot.config["discord"][
            "meme_tip_channel"
        ]  # memetip
        self.meme_web_path = self.bot.config["discord"]["meme_web_path"]
        self.get_meme = get_meme

    async def on_timeout(self):
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)

    async def process_tipping(self, amount, coin_name, interaction):
        if int(self.owner_userid) == interaction.author.id:
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, you cannot tip your own meme!"
            )
        else:
            try:
                await interaction.response.send_message(
                    content=f"{interaction.author.mention}, checking meme tipping..."
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await interaction.response.send_message(
                    content=f"{interaction.author.mention}, failed to execute meme tipping. Try again later!",
                    ephemeral=True,
                )
                return
            # Check enough balance
            net_name = getattr(getattr(self.bot.coin_list, coin_name), "net_name")
            type_coin = getattr(getattr(self.bot.coin_list, coin_name), "type")
            deposit_confirm_depth = getattr(
                getattr(self.bot.coin_list, coin_name), "deposit_confirm_depth"
            )
            coin_decimal = getattr(getattr(self.bot.coin_list, coin_name), "decimal")
            contract = getattr(getattr(self.bot.coin_list, coin_name), "contract")
            token_display = getattr(
                getattr(self.bot.coin_list, coin_name), "display_name"
            )

            min_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_min_tip")
            max_tip = getattr(getattr(self.bot.coin_list, coin_name), "real_max_tip")
            price_with = getattr(getattr(self.bot.coin_list, coin_name), "price_with")
            get_deposit = await self.wallet_api.sql_get_userwallet(
                str(interaction.author.id),
                coin_name,
                net_name,
                type_coin,
                SERVER_BOT,
                0,
            )
            if get_deposit is None:
                get_deposit = await self.wallet_api.sql_register_user(
                    str(interaction.author.id),
                    coin_name,
                    net_name,
                    type_coin,
                    SERVER_BOT,
                    0,
                    0,
                )

            wallet_address = get_deposit["balance_wallet_address"]
            if type_coin in ["TRTL-API", "TRTL-SERVICE", "BCN", "XMR"]:
                wallet_address = get_deposit["paymentid"]
            elif type_coin in ["XRP"]:
                wallet_address = get_deposit["destination_tag"]

            # Check if tx in progress
            if (
                str(interaction.author.id) in self.bot.tipping_in_progress
                and int(time.time())
                - self.bot.tipping_in_progress[str(interaction.author.id)]
                < 150
            ):
                msg = f"{EMOJI_ERROR} {interaction.author.mention}, you have another transaction in progress."
                await interaction.edit_original_message(content=msg)
                return

            height = await self.wallet_api.get_block_height(
                type_coin, coin_name, net_name
            )
            userdata_balance = await store.sql_user_balance_single(
                str(interaction.author.id),
                coin_name,
                wallet_address,
                type_coin,
                height,
                deposit_confirm_depth,
                SERVER_BOT,
            )
            actual_balance = float(userdata_balance["adjust"])
            if amount <= 0:
                msg = f"{EMOJI_RED_NO} {interaction.author.mention}, please get more {token_display}."
                await interaction.edit_original_message(content=msg)
                return
            elif amount > actual_balance:
                msg = (
                    f"{EMOJI_RED_NO} {self.ctx.author.mention}, insufficient balance to give meme tip of "
                    f"**{num_format_coin(amount)} {token_display}**."
                )
                await interaction.edit_original_message(content=msg)
                return
            elif amount > max_tip or amount < min_tip:
                msg = (
                    f"{EMOJI_RED_NO} {self.ctx.author.mention}, tipping cannot be bigger than "
                    f"**{num_format_coin(max_tip)} {token_display}** or smaller than "
                    f"**{num_format_coin(min_tip)} {token_display}**."
                )
                await interaction.edit_original_message(content=msg)
                return
            equivalent_usd = ""
            amount_in_usd = 0.0
            if price_with:
                per_unit = await self.utils.get_coin_price(coin_name, price_with)
                if per_unit and per_unit["price"] and per_unit["price"] > 0:
                    per_unit = per_unit["price"]
                    amount_in_usd = float(Decimal(per_unit) * Decimal(amount))
                    if amount_in_usd > 0.0001:
                        equivalent_usd = " ~ {:,.4f} USD".format(amount_in_usd)

            if str(interaction.author.id) not in self.bot.tipping_in_progress:
                self.bot.tipping_in_progress[str(interaction.author.id)] = int(
                    time.time()
                )

            user_to = await self.wallet_api.sql_get_userwallet(
                self.owner_userid, coin_name, net_name, type_coin, SERVER_BOT, 0
            )
            if user_to is None:
                user_to = await self.wallet_api.sql_register_user(
                    self.owner_userid, coin_name, net_name, type_coin, SERVER_BOT, 0
                )
            try:
                guild_id = "DM"
                channel_id = "DM"
                guild_name = " in DM"
                if hasattr(interaction, "guild") and hasattr(interaction.guild, "id"):
                    guild_id = interaction.guild.id
                    channel_id = interaction.channel.id
                    guild_name = " in Guild {}".format(interaction.guild.name)
                tip = await add_memetip(
                    self.meme_id,
                    self.owner_userid,
                    str(interaction.author.id),
                    guild_id,
                    channel_id,
                    amount,
                    coin_name,
                    coin_decimal,
                    contract,
                    amount_in_usd,
                )
                if tip > 0:
                    url_image = self.meme_web_path + self.get_meme["saved_name"]
                    try:
                        msg = "A user ({}) has tipped to your meme `{}` with amount `{} {}`{}. Cheers!\n{}".format(
                            interaction.author.mention,
                            self.meme_id,
                            amount,
                            coin_name,
                            guild_name,
                            url_image,
                        )
                        get_meme_owner = self.bot.get_user(int(self.owner_userid))
                        await get_meme_owner.send(content=msg)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
                    msg = (
                        f"{interaction.author.mention}, you tipped **{num_format_coin(amount)} "
                        f"{token_display}** to meme `{self.meme_id}` by <@{self.owner_userid}>."
                    )
                    await interaction.edit_original_message(content=msg)
                    try:
                        embed = disnake.Embed(
                            title="A meme got tipped{}!".format(guild_name),
                            description=f"Share your meme and get tipped!",
                            timestamp=datetime.now(),
                        )
                        embed.add_field(
                            name="Tipped with",
                            value="{} {}".format(amount, coin_name),
                            inline=True,
                        )
                        embed.add_field(
                            name="Uploader",
                            value="<@{}>".format(self.owner_userid),
                            inline=True,
                        )
                        embed.add_field(
                            name="ID",
                            value="`{}`".format(self.get_meme["key"]),
                            inline=False,
                        )
                        embed.set_author(
                            name=self.bot.user.name,
                            icon_url=self.bot.user.display_avatar,
                        )
                        embed.set_image(url=url_image)
                        embed.set_footer(
                            text="Tipped by: {}#{}".format(
                                interaction.author.name,
                                interaction.author.discriminator,
                            )
                        )
                        channel = self.bot.get_channel(self.meme_tip_channel)
                        await channel.send(embed=embed)
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            try:
                del self.bot.tipping_in_progress[str(interaction.author.id)]
            except Exception:
                pass

    @disnake.ui.button(
        emoji="<a:TB_WRKZ:1095201990486786068>",
        label="100 WRKZ",
        style=ButtonStyle.green,
        custom_id="memetip_100_WRKZ",
        row=1,
    )
    async def tip_wrkz(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            await self.process_tipping(100, "WRKZ", interaction)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @disnake.ui.button(
        emoji="<a:TB_WOW:1095212324626898954>",
        label="0.1 WOW",
        style=ButtonStyle.green,
        custom_id="memetip_0_1_WOW",
        row=1,
    )
    async def tip_wow(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            await self.process_tipping(0.1, "WOW", interaction)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @disnake.ui.button(
        emoji="<a:TB_DOGE:1095212316397670430>",
        label="0.1 DOGE",
        style=ButtonStyle.green,
        custom_id="memetip_0_1_DOGE",
        row=2,
    )
    async def tip_doge(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            await self.process_tipping(0.1, "DOGE", interaction)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @disnake.ui.button(
        emoji="<a:TB_DEGO:1095201546146414682>",
        label="10K DEGO",
        style=ButtonStyle.green,
        custom_id="memetip_10000_DEGO",
        row=2,
    )
    async def tip_dego(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            await self.process_tipping(10000, "DEGO", interaction)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @disnake.ui.button(
        emoji="<a:TB_BAN:1095213025067290694>",
        label="0.5 BAN",
        style=ButtonStyle.green,
        custom_id="memetip_0_5_BAN",
        row=3,
    )
    async def tip_ban(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            await self.process_tipping(0.5, "BAN", interaction)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @disnake.ui.button(
        emoji="<a:TB_MOON:1095222174954041396>",
        label="0.02 MOON",
        style=ButtonStyle.green,
        custom_id="memetip_0_0_2_MOON",
        row=3,
    )
    async def tip_moon(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            await self.process_tipping(0.02, "MOON", interaction)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @disnake.ui.button(
        emoji="<a:TB_XDG:1095236056468684810>",
        label="4.20 XDG",
        style=ButtonStyle.green,
        custom_id="memetip_4_2_XDG",
        row=4,
    )
    async def tip_dogenano(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        try:
            await self.process_tipping(4.2, "XDG", interaction)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @disnake.ui.button(
        label="Tip other coin",
        style=ButtonStyle.blurple,
        custom_id="memetip_other",
        row=4,
    )
    async def tip_other_coin(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if int(self.owner_userid) == interaction.author.id:
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, you cannot tip your own meme!"
            )
        else:
            await interaction.response.send_modal(
                modal=TipOtherCoin(
                    interaction,
                    self.bot,
                    self.meme_id,
                    self.owner_userid,
                    self.get_meme,
                )
            )

    @disnake.ui.button(
        label="⚠️ Report", style=ButtonStyle.red, custom_id="memetip_report", row=4
    )
    async def memetip_report(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        await interaction.response.send_modal(
            modal=MemeTipReport(
                interaction, self.bot, self.meme_id, self.owner_userid, self.get_meme
            )
        )


# Defines a simple view of row buttons.
class MemeReview_Button(disnake.ui.View):
    message: disnake.Message

    def __init__(
        self, ctx, bot, timeout: float, meme_id: str, owner_userid: int, url: str
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.utils = Utils(self.bot)
        self.ctx = ctx
        self.meme_id = meme_id
        self.owner_userid = owner_userid
        self.url = url
        self.meme_channel_upload = self.bot.config["discord"]["meme_upload_channel_log"]

    async def on_timeout(self):
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)

    @disnake.ui.button(
        label="APPROVE", style=ButtonStyle.green, custom_id="memepls_approve"
    )
    async def click_memepls_approve(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.ctx.author.id:
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, that's not your reviewed item."
            )
            return
        try:
            meme_db = MemePls(self.bot)
            toggle = await meme_db.meme_toggle_status(
                self.meme_id, 1, interaction.author.id, int(time.time())
            )
            if toggle > 0:
                await interaction.response.send_message(
                    content=f"{interaction.author.mention}, successfully approved `{self.meme_id}`.\n{self.url}"
                )
                # tell owner that his meme approved.
                guild_name = ""
                if hasattr(interaction, "guild") and hasattr(interaction.guild, "id"):
                    guild_name = f" in Guild {interaction.guild.name}"
                try:
                    get_meme_owner = self.bot.get_user(int(self.owner_userid))
                    if get_meme_owner is not None:
                        await get_meme_owner.send(
                            f"Your meme ID: `{self.meme_id}`{guild_name} is approved. Cheers!\n{self.url}"
                        )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                # Post in meme_channel_upload
                channel = self.bot.get_channel(self.meme_channel_upload)
                await channel.send(
                    content=f"`{self.meme_id}` by <@{str(self.owner_userid)}> is approved by "
                    f"{interaction.author.name}#{interaction.author.discriminator} / {interaction.author.id}{guild_name}."
                )
            else:
                await interaction.response.send_message(
                    content=f"{interaction.author.mention}, failed to approve `{self.meme_id}` or it is already approved."
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)

    @disnake.ui.button(
        label="REJECT", style=ButtonStyle.red, custom_id="memepls_reject"
    )
    async def click_memepls_reject(
        self, button: disnake.ui.Button, interaction: disnake.MessageInteraction
    ):
        if interaction.author.id != self.ctx.author.id:
            await interaction.response.send_message(
                content=f"{interaction.author.mention}, that's not your reviewed item."
            )
            return
        try:
            meme_db = MemePls(self.bot)
            # 0: disable
            # 1: enable
            # 2: reject
            toggle = await meme_db.meme_toggle_status(
                self.meme_id, 2, interaction.author.id, int(time.time())
            )
            if toggle > 0:
                await interaction.response.send_message(
                    content=f"{interaction.author.mention}, successfully rejected `{self.meme_id}`.\n{self.url}"
                )
            else:
                await interaction.response.send_message(
                    content=f"{interaction.author.mention}, failed to reject `{self.meme_id}` or it is already not approved."
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        original_message = await self.ctx.original_message()
        await original_message.edit(view=None)


class MemePls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wallet_api = WalletAPI(self.bot)
        self.utils = Utils(self.bot)
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        self.enable_logchan = True
        self.meme_accept = ["image/jpeg", "image/gif", "image/png"]
        self.meme_storage = "./discordtip_v2_meme/"
        self.meme_web_path = self.bot.config["discord"]["meme_web_path"]
        self.meme_channel_upload = self.bot.config["discord"]["meme_upload_channel_log"]
        self.meme_reviewer = self.bot.config["discord"]["meme_reviewer"]

    async def save_uploaded(
        self,
        key: str,
        owner_userid: str,
        owner_name: str,
        guild_id: str,
        channel_id: str,
        caption: str,
        original_name: str,
        saved_name: str,
        file_type: str,
        sha256: str,
        uploaded_date: int,
        guild_name: str = None,
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    INSERT INTO `meme_uploaded` 
                    (`key`, `owner_userid`, `owner_name`, `guild_id`, `guild_name`, 
                    `channel_id`, `caption`, `original_name`, `saved_name`, `file_type`, `sha256`, `uploaded_date`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(
                        sql,
                        (
                            key,
                            owner_userid,
                            owner_name,
                            guild_id,
                            guild_name,
                            channel_id,
                            caption,
                            original_name,
                            saved_name,
                            file_type,
                            sha256,
                            uploaded_date,
                        ),
                    )
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def get_random_meme(self, checker_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `meme_uploaded` 
                    WHERE `owner_userid`<>%s AND `enable`=%s 
                    ORDER BY RAND() LIMIT 1
                    """
                    await cur.execute(sql, (checker_id, 1))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_id_meme(self, meme_id: str, guild_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `meme_uploaded` 
                    WHERE `key`=%s AND `guild_id`=%s 
                    LIMIT 1 """
                    await cur.execute(sql, (meme_id, guild_id))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_random_pending_meme(self, guild: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `meme_uploaded` 
                    WHERE `enable`=%s AND `guild_id`=%s 
                    ORDER BY `uploaded_date` ASC LIMIT 1
                    """
                    await cur.execute(sql, (0, guild))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_random_approved_meme(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `meme_uploaded` 
                    WHERE `enable`=%s 
                    ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, 1)
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_random_approved_meme_user(self, user_id, guild_id):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `meme_uploaded` 
                    WHERE `enable`=%s AND `owner_userid`=%s 
                    AND `guild_id`=%s 
                    ORDER BY RAND() LIMIT 1 """
                    await cur.execute(sql, (1, user_id, guild_id))
                    result = await cur.fetchone()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_random_approved_meme_guild(self, guild_id, filter_user: str = None):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `meme_uploaded` 
                    WHERE `enable`=%s AND `guild_id`=%s 
                    ORDER BY RAND() LIMIT 1
                    """
                    if filter_user is not None:
                        sql = """
                        SELECT * FROM `meme_uploaded` 
                        WHERE `enable`=%s AND `guild_id`=%s AND `owner_userid`<>%s
                        ORDER BY RAND() LIMIT 1
                        """
                        await cur.execute(sql, (1, guild_id, filter_user))
                    else:
                        await cur.execute(sql, (1, guild_id))
                    result = await cur.fetchone()
                    if result:
                        sql = """
                        SELECT SUM(`tipped_amount`) AS `tipped_amount`, `tipped_coin` AS `coin_name`
                        FROM `meme_tipped`
                        WHERE `meme_id`=%s
                        GROUP BY `tipped_coin`
                        """
                        await cur.execute(sql, result["key"])
                        tip_result = await cur.fetchall()
                        if tip_result:
                            return {"meme": result, "tipped": tip_result}
                        else:
                            return {"meme": result, "tipped": []}
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_user_meme_list(self, user_id: str):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `meme_uploaded` 
                    WHERE `owner_userid`=%s  
                    ORDER BY `uploaded_date` DESC """
                    await cur.execute(sql, user_id)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def meme_toggle_status(
        self, meme_id: str, status: int, reviewed_by: str, reviewed_date: int
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `meme_uploaded` 
                    SET `enable`=%s, `reviewed_by`=%s, `reviewed_date`=%s 
                    WHERE `key`=%s LIMIT 1 """
                    await cur.execute(
                        sql, (status, reviewed_by, reviewed_date, meme_id)
                    )
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def meme_update_view(
        self,
        meme_id: str,
        owner_userid: str,
        called_by: str,
        guild_id: str,
        channel_id: str,
        inc: int = 1,
    ):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `meme_uploaded` SET `number_view`=number_view+%s WHERE `key`=%s LIMIT 1;
                              INSERT INTO meme_viewed (`meme_id`, `owner_userid`, `called_by`, 
                              `guild_id`, `channel_id`, `date`) 
                              VALUES (%s, %s, %s, %s, %s, %s) """
                    await cur.execute(
                        sql,
                        (
                            inc,
                            meme_id,
                            meme_id,
                            owner_userid,
                            called_by,
                            guild_id,
                            channel_id,
                            int(time.time()),
                        ),
                    )
                    await conn.commit()
                    return cur.rowcount
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return 0

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    async def meme_view_here(self, ctx, including_mine):
        await self.bot_log()
        await ctx.response.send_message(
            f"{ctx.author.mention}, checking random meme..."
        )
        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/memepls view here",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
            try:
                serverinfo = self.bot.other_data["guild_list"].get(str(ctx.guild.id))
                if serverinfo and serverinfo["enable_memepls"] == "NO":
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} tried /memepls in {ctx.guild.name} / {ctx.guild.id} which is disable."
                        )
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, /memepls in this guild is disable. You can enable by `/setting memepls`."
                    await ctx.edit_original_message(content=msg)
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)

        guild_id = "DM"
        channel_id = "DM"
        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
            guild_id = ctx.guild.id
            channel_id = ctx.channel.id

        filter_user = None
        if including_mine == "NO":
            filter_user = str(ctx.author.id)
        get_meme_data = await self.get_random_approved_meme_guild(guild_id, filter_user)
        if get_meme_data is None:
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, could not get one random meme here yet. "
                "No one uploaded? Try again later!"
            )
            return
        else:
            get_meme = get_meme_data["meme"]
            get_tipped = get_meme_data["tipped"]
            embed = disnake.Embed(
                title="MEME uploaded by {}".format(get_meme["owner_name"]),
                description=f"You can tip from your balance.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="View Count", value=get_meme["number_view"] + 1, inline=True
            )
            embed.add_field(
                name="Tip Count", value=get_meme["number_tipped"], inline=True
            )
            if len(get_tipped) > 0:
                got_tipped = []
                for i in get_tipped:
                    got_tipped.append(
                        "{} {}".format(
                            num_format_coin(i["tipped_amount"]), i["coin_name"]
                        )
                    )
                embed.add_field(
                    name="Received Tips",
                    value="```{}```".format("\n".join(got_tipped)),
                    inline=False,
                )
            embed.set_author(
                name=self.bot.user.name, icon_url=self.bot.user.display_avatar
            )
            embed.set_image(url=self.meme_web_path + get_meme["saved_name"])
            embed.set_footer(
                text="Random by: {}#{}".format(
                    ctx.author.name, ctx.author.discriminator
                )
            )
            try:
                view = MemeTip_Button(
                    ctx,
                    self.bot,
                    120,
                    get_meme["key"],
                    get_meme["owner_userid"],
                    get_meme,
                )
                view.message = await ctx.original_message()
                await ctx.edit_original_message(content=None, embed=embed, view=view)
                await self.meme_update_view(
                    get_meme["key"],
                    get_meme["owner_userid"],
                    str(ctx.author.id),
                    guild_id,
                    channel_id,
                    1,
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)

    async def meme_user(self, ctx, member):
        await self.bot_log()
        await ctx.response.send_message(
            f"{ctx.author.mention}, checking user's random meme..."
        )

        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/memepls user",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
            try:
                serverinfo = self.bot.other_data["guild_list"].get(str(ctx.guild.id))
                if serverinfo and serverinfo["enable_memepls"] == "NO":
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} tried /memepls in {ctx.guild.name} / {ctx.guild.id} which is disable."
                        )
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, /memepls in this guild is disable. You can enable by `/setting memepls`."
                    await ctx.edit_original_message(content=msg)
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)

        guild_id = "DM"
        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
            guild_id = str(ctx.guild.id)
        get_meme = await self.get_random_approved_meme_user(str(member.id), guild_id)
        if get_meme is None:
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, could not get `{member.name}#{member.discriminator}` random meme yet. "
                "Try again later or ask them to upload more?!"
            )
            return
        else:
            embed = disnake.Embed(
                title="MEME uploaded by {}".format(get_meme["owner_name"]),
                description=f"You can tip from your balance.",
                timestamp=datetime.now(),
            )
            embed.add_field(
                name="View Count", value=get_meme["number_view"] + 1, inline=True
            )
            embed.add_field(
                name="Tip Count", value=get_meme["number_tipped"], inline=True
            )
            embed.set_author(
                name=self.bot.user.name, icon_url=self.bot.user.display_avatar
            )
            embed.set_image(url=self.meme_web_path + get_meme["saved_name"])
            embed.set_footer(
                text="Random requested by: {}#{}".format(
                    ctx.author.name, ctx.author.discriminator
                )
            )
            try:
                view = MemeTip_Button(
                    ctx,
                    self.bot,
                    120,
                    get_meme["key"],
                    get_meme["owner_userid"],
                    get_meme,
                )
                view.message = await ctx.original_message()
                await ctx.edit_original_message(content=None, embed=embed, view=view)
                guild_id = "DM"
                channel_id = "DM"
                if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                    guild_id = ctx.guild.id
                    channel_id = ctx.channel.id
                await self.meme_update_view(
                    get_meme["key"],
                    get_meme["owner_userid"],
                    str(ctx.author.id),
                    guild_id,
                    channel_id,
                    1,
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)

    async def meme_review(self, ctx, meme_id):
        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/memepls review",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if (
            ctx.author.id not in self.meme_reviewer
            and hasattr(ctx, "guild")
            and hasattr(ctx.guild, "id")
            and ctx.channel.permissions_for(
                ctx.guild.get_member(ctx.author.id)
            ).manage_channels
            is False
        ):
            await ctx.response.send_message(
                f"{ctx.author.mention}, permission denied..."
            )
            return
        elif (
            hasattr(ctx, "guild")
            and hasattr(ctx.guild, "id")
            and ctx.channel.permissions_for(
                ctx.guild.get_member(ctx.author.id)
            ).manage_channels
            is True
        ):
            # has permission and public
            await ctx.response.send_message(
                f"{ctx.author.mention}, checking meme in guild `{ctx.guild.name}`..."
            )
            if meme_id is None:
                get_meme = await self.get_random_pending_meme(str(ctx.guild.id))
                if get_meme is None:
                    msg = f"{ctx.author.mention}, no pending left this guild."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    status = "PENDING"
                    if get_meme["enable"] == 1:
                        status = "APPROVED"
                    embed = disnake.Embed(
                        title="MEME uploaded by {} / {} in {}".format(
                            get_meme["owner_name"],
                            get_meme["owner_userid"],
                            get_meme["guild_id"],
                        ),
                        description=f"Status `{status}`",
                        timestamp=datetime.now(),
                    )
                    embed.add_field(
                        name="Original File",
                        value=get_meme["original_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="Stored File", value=get_meme["saved_name"], inline=False
                    )
                    embed.add_field(
                        name="New URL link",
                        value=self.meme_web_path + get_meme["saved_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="View Count", value=get_meme["number_view"], inline=True
                    )
                    embed.add_field(
                        name="Tip Count", value=get_meme["number_tipped"], inline=True
                    )
                    embed.set_thumbnail(url=self.meme_web_path + get_meme["saved_name"])
                    embed.set_footer(
                        text="Reviewing {} by: {}#{}".format(
                            get_meme["key"], ctx.author.name, ctx.author.discriminator
                        )
                    )
                    try:
                        view = MemeReview_Button(
                            ctx,
                            self.bot,
                            30,
                            get_meme["key"],
                            get_meme["owner_userid"],
                            self.meme_web_path + get_meme["saved_name"],
                        )
                        view.message = await ctx.original_message()
                        await ctx.edit_original_message(
                            content=None, embed=embed, view=view
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            else:
                get_meme = await self.get_id_meme(meme_id, str(ctx.guild.id))
                if get_meme is None:
                    msg = f"{ctx.author.mention}, `meme_id` not found in this guild."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    status = "PENDING"
                    if get_meme["enable"] == 1:
                        status = "APPROVED"
                    embed = disnake.Embed(
                        title="MEME uploaded by {} / {} in {}".format(
                            get_meme["owner_name"],
                            get_meme["owner_userid"],
                            get_meme["guild_id"],
                        ),
                        description=f"Status `{status}`",
                        timestamp=datetime.now(),
                    )
                    embed.add_field(
                        name="Original File",
                        value=get_meme["original_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="Stored File", value=get_meme["saved_name"], inline=False
                    )
                    embed.add_field(
                        name="New URL link",
                        value=self.meme_web_path + get_meme["saved_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="View Count", value=get_meme["number_view"], inline=True
                    )
                    embed.add_field(
                        name="Tip Count", value=get_meme["number_tipped"], inline=True
                    )
                    embed.set_thumbnail(url=self.meme_web_path + get_meme["saved_name"])
                    embed.set_footer(
                        text="Reviewing {} by: {}#{}".format(
                            get_meme["key"], ctx.author.name, ctx.author.discriminator
                        )
                    )
                    try:
                        view = MemeReview_Button(
                            ctx,
                            self.bot,
                            30,
                            get_meme["key"],
                            get_meme["owner_userid"],
                            self.meme_web_path + get_meme["saved_name"],
                        )
                        view.message = await ctx.original_message()
                        await ctx.edit_original_message(
                            content=None, embed=embed, view=view
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        elif ctx.author.id in self.meme_reviewer and not hasattr(ctx.guild, "id"):
            # Check meme uploaded in DM
            await ctx.response.send_message(
                f"{ctx.author.mention}, checking meme ID..."
            )
            if meme_id is None:
                # Check random meme which pending
                get_meme = await self.get_random_pending_meme("DM")
                if get_meme is None:
                    msg = f"{ctx.author.mention}, no pending left from DM."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    status = "PENDING"
                    if get_meme["enable"] == 1:
                        status = "APPROVED"
                    embed = disnake.Embed(
                        title="MEME uploaded by {} / {} in {}".format(
                            get_meme["owner_name"],
                            get_meme["owner_userid"],
                            get_meme["guild_id"],
                        ),
                        description=f"Status `{status}`",
                        timestamp=datetime.now(),
                    )
                    embed.add_field(
                        name="Original File",
                        value=get_meme["original_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="Stored File", value=get_meme["saved_name"], inline=False
                    )
                    embed.add_field(
                        name="New URL link",
                        value=self.meme_web_path + get_meme["saved_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="View Count", value=get_meme["number_view"], inline=True
                    )
                    embed.add_field(
                        name="Tip Count", value=get_meme["number_tipped"], inline=True
                    )
                    embed.set_thumbnail(url=self.meme_web_path + get_meme["saved_name"])
                    embed.set_footer(
                        text="Reviewing {} by: {}#{}".format(
                            get_meme["key"], ctx.author.name, ctx.author.discriminator
                        )
                    )
                    try:
                        view = MemeReview_Button(
                            ctx,
                            self.bot,
                            30,
                            get_meme["key"],
                            get_meme["owner_userid"],
                            self.meme_web_path + get_meme["saved_name"],
                        )
                        view.message = await ctx.original_message()
                        await ctx.edit_original_message(
                            content=None, embed=embed, view=view
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
            else:
                get_meme = await self.get_id_meme(meme_id, "DM")
                if get_meme is None:
                    msg = f"{ctx.author.mention}, `meme_id` not found from DM."
                    await ctx.edit_original_message(content=msg)
                    return
                else:
                    status = "PENDING"
                    if get_meme["enable"] == 1:
                        status = "APPROVED"
                    embed = disnake.Embed(
                        title="MEME uploaded by {} / {} in {}".format(
                            get_meme["owner_name"],
                            get_meme["owner_userid"],
                            get_meme["guild_id"],
                        ),
                        description=f"Status `{status}`",
                        timestamp=datetime.now(),
                    )
                    embed.add_field(
                        name="Original File",
                        value=get_meme["original_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="Stored File", value=get_meme["saved_name"], inline=False
                    )
                    embed.add_field(
                        name="New URL link",
                        value=self.meme_web_path + get_meme["saved_name"],
                        inline=False,
                    )
                    embed.add_field(
                        name="View Count", value=get_meme["number_view"], inline=True
                    )
                    embed.add_field(
                        name="Tip Count", value=get_meme["number_tipped"], inline=True
                    )
                    embed.set_thumbnail(url=self.meme_web_path + get_meme["saved_name"])
                    embed.set_footer(
                        text="Reviewing {} by: {}#{}".format(
                            get_meme["key"], ctx.author.name, ctx.author.discriminator
                        )
                    )
                    try:
                        view = MemeReview_Button(
                            ctx,
                            self.bot,
                            30,
                            get_meme["key"],
                            get_meme["owner_userid"],
                            self.meme_web_path + get_meme["saved_name"],
                        )
                        view.message = await ctx.original_message()
                        await ctx.edit_original_message(
                            content=None, embed=embed, view=view
                        )
                    except Exception:
                        traceback.print_exc(file=sys.stdout)
        elif ctx.author.id not in self.meme_reviewer:
            await ctx.response.send_message(
                f"{ctx.author.mention}, permission denied..."
            )
            return
        else:
            await ctx.response.send_message(f"{ctx.author.mention}, error.")
            return

    async def meme_list(self, ctx):
        await self.bot_log()
        await ctx.response.send_message(
            f"{ctx.author.mention}, in progress...", ephemeral=True
        )

        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/memepls list",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        try:
            get_user_memes = await self.get_user_meme_list(str(ctx.author.id))
            if len(get_user_memes) == 0:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, you don't have any uploaded MEME."
                )
            else:
                all_pages = []
                for each in get_user_memes:
                    ts = datetime.fromtimestamp(each["uploaded_date"])
                    embed = disnake.Embed(
                        title="{}#{} Your MEME `{}`".format(
                            ctx.author.name, ctx.author.discriminator, each["key"]
                        ),
                        description=f"Caption: {each['caption']}\nViewed: {each['number_view']}x\n"
                        f"Tipped: {each['number_tipped']}x",
                        timestamp=ts,
                    )
                    embed.add_field(
                        name="Guild ID", value=each["guild_id"], inline=True
                    )
                    embed.add_field(
                        name="Status",
                        value="APPROVED" if each["enable"] == 1 else "PENDING",
                        inline=True,
                    )
                    embed.add_field(
                        name="Original File", value=each["original_name"], inline=False
                    )
                    embed.set_image(url=self.meme_web_path + each["saved_name"])
                    embed.set_footer(text="Your navigation button!")
                    all_pages.append(embed)
                view = MenuPage(ctx, all_pages, timeout=60, disable_remove=True)
                view.message = await ctx.edit_original_message(
                    content=None, embed=all_pages[0], view=view
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def meme_upload(self, ctx, caption, attachment):
        await self.bot_log()
        await ctx.response.send_message(f"{ctx.author.mention}, loading meme upload...")

        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/memepls upload",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
            try:
                serverinfo = self.bot.other_data["guild_list"].get(str(ctx.guild.id))
                if serverinfo and serverinfo["enable_memepls"] == "NO":
                    if self.enable_logchan:
                        await self.botLogChan.send(
                            f"{ctx.author.name} / {ctx.author.id} tried /memepls in {ctx.guild.name} / {ctx.guild.id} which is disable."
                        )
                    msg = f"{EMOJI_RED_NO} {ctx.author.mention}, /memepls in this guild is disable. You can enable by `/setting memepls`."
                    await ctx.edit_original_message(content=msg)
                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)
        try:
            # download attachment first
            res_data = None
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(str(attachment), timeout=32) as response:
                        if response.status == 200:
                            res_data = await response.read()
                            hash_object = hashlib.sha256(res_data)
                            hex_dig = str(hash_object.hexdigest())
                            mime_type = magic.from_buffer(res_data, mime=True)
                            if mime_type not in self.meme_accept:
                                msg = f"{ctx.author.mention}, the uploaded image is not a supported file."
                                await ctx.edit_original_message(content=msg)
                                return
                            else:
                                original_name = str(attachment).split("/")[-1]
                                random_string = str(uuid.uuid4())
                                guild_id = "DM"
                                guild_name = "DM"
                                channel_id = "DM"
                                guild_name = "DM"
                                if hasattr(ctx, "guild") and hasattr(ctx.guild, "id"):
                                    guild_name = ctx.guild.name
                                    guild_id = ctx.guild.id
                                    channel_id = ctx.channel.id
                                    guild_name = ctx.guild.name
                                # Write the stuff
                                saved_name = hex_dig + "." + mime_type.split("/")[1]
                                with open(self.meme_storage + saved_name, "wb") as f:
                                    f.write(BytesIO(res_data).getbuffer())
                                saving = await self.save_uploaded(
                                    random_string,
                                    str(ctx.author.id),
                                    "{}#{}".format(
                                        ctx.author.name, ctx.author.discriminator
                                    ),
                                    guild_id,
                                    channel_id,
                                    caption,
                                    original_name,
                                    saved_name,
                                    mime_type,
                                    hex_dig,
                                    int(time.time()),
                                    guild_name,
                                )
                                if saving > 0:
                                    embed = disnake.Embed(
                                        title="MEME uploaded by {}#{} / {} in {}".format(
                                            ctx.author.name,
                                            ctx.author.discriminator,
                                            ctx.author.id,
                                            guild_name,
                                        ),
                                        description=f"Please help to check and review `{random_string}`!",
                                        timestamp=datetime.now(),
                                    )
                                    embed.add_field(
                                        name="Original File",
                                        value=original_name,
                                        inline=False,
                                    )
                                    embed.add_field(
                                        name="Stored File",
                                        value=saved_name,
                                        inline=False,
                                    )
                                    embed.add_field(
                                        name="New URL link",
                                        value=self.meme_web_path + saved_name,
                                        inline=False,
                                    )
                                    embed.set_thumbnail(url=str(attachment))
                                    embed.set_footer(
                                        text="Posted by: {}#{}".format(
                                            ctx.author.name, ctx.author.discriminator
                                        )
                                    )
                                    msg = (
                                        f"{ctx.author.mention}, successfully uploaded. Image ID: `{random_string}`. "
                                        "It will be reviewed and approved shortly."
                                    )
                                    await ctx.edit_original_message(content=msg)
                                    # send to meme channel
                                    channel = self.bot.get_channel(
                                        self.meme_channel_upload
                                    )
                                    await channel.send(embed=embed)
                                    return
                                else:
                                    msg = f"{ctx.author.mention}, failed to saved."
                                    await ctx.edit_original_message(content=msg)
                                    return
            except Exception:
                traceback.print_exc(file=sys.stdout)

        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def meme_disclaimer(self, ctx):
        disclaimer = """
1] You have permission to use the uploaded file
2] We reserved right to reject it
3] Follow each Discord Guild's rule
4] Comply to https://discord.com/terms
5] No NSFW
"""
        await ctx.response.send_message(f"{ctx.author.mention}, ```{disclaimer}```")
        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/memepls disclaimer",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.slash_command(description="Meme commands (upload, view, list yours)")
    async def memepls(self, ctx):
        await self.bot_log()

    @memepls.sub_command(
        usage="memepls view",
        description="View MEME randomly.",
        options=[
            Option(
                "including_mine",
                "including_mine",
                OptionType.string,
                required=False,
                choices=[OptionChoice("YES", "YES"), OptionChoice("NO", "NO")],
            )
        ],
    )
    async def view(self, ctx, including_mine: str = "YES"):
        await self.meme_view_here(ctx, including_mine)

    @memepls.sub_command(
        usage="memepls user <@member>",
        options=[Option("user", "user", OptionType.user, required=False)],
        description="View other user's MEME randomly.",
    )
    async def user(self, ctx, user: disnake.Member = None):
        if user is None:
            user = ctx.author
        await self.meme_user(ctx, user)

    @memepls.sub_command(usage="memepls list", description="View your uploaded MEME")
    async def list(self, ctx):
        await self.meme_list(ctx)

    @memepls.sub_command(
        usage="memepls upload <caption> <attachment>",
        options=[
            Option("caption", "caption", OptionType.string, required=True),
            Option("image", "image", OptionType.attachment, required=True),
        ],
        description="Upload your MEME.",
    )
    async def upload(self, ctx, caption: str, image: disnake.Attachment):
        await self.meme_upload(ctx, caption, image)

    @memepls.sub_command(
        usage="memepls review <meme_id>",
        options=[Option("meme_id", "meme_id", OptionType.string, required=False)],
        description="Review MEME ID (reviewer).",
    )
    async def review(
        self,
        ctx,
        meme_id: str = None,
    ):
        await self.meme_review(ctx, meme_id)

    @memepls.sub_command(
        usage="memepls disclaimer",
        description="View term & condition of your upload MEME.",
    )
    async def disclaimer(self, ctx):
        await self.meme_disclaimer(ctx)


def setup(bot):
    bot.add_cog(MemePls(bot))
