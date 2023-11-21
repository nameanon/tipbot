import sys
import traceback
import psutil
from datetime import datetime
import time
import random

import disnake
import store
from Bot import RowButtonRowCloseAnyMessage, logchanbot, SERVER_BOT
from cogs.utils import Utils
from disnake.ext import commands


class About(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    async def get_tipping_count(self):
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT (SELECT COUNT(*) FROM user_balance_mv) AS nos_tipping,
                    (SELECT COUNT(*) FROM user_balance_mv_data) AS nos_user
                    """
                    await cur.execute(sql, ())
                    return await cur.fetchone()
        except Exception:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        return None

    async def async_about(self, ctx):
        await ctx.response.defer(ephemeral=False)
        try:
            self.bot.commandings.append((str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM", 
                                         str(ctx.author.id), SERVER_BOT, "/about", int(time.time())))
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            embed = await self.about_embed()
            # if advert enable
            if self.bot.config['discord']['enable_advert'] == 1 and len(self.bot.advert_list) > 0:
                try:
                    random.shuffle(self.bot.advert_list)
                    embed.add_field(
                        name=f"{self.bot.advert_list[0]['title']}",
                        value=f"```{self.bot.advert_list[0]['content']}```👉 <{self.bot.advert_list[0]['link']}>",
                        inline=False,
                    )
                    await self.utils.advert_impress(
                        self.bot.advert_list[0]['id'], str(ctx.author.id),
                        str(ctx.guild.id) if hasattr(ctx, "guild") and hasattr(ctx.guild, "id") else "DM"
                    )
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # end advert

            await ctx.edit_original_message(content=None, embed=embed, view=RowButtonRowCloseAnyMessage())
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def about_embed(self):
        await self.bot.wait_until_ready()
        # some steal from https://github.com/yazilimcilarinmolayeri/bot-rw/blob/3d81111cb0334831de223788d3754e0597e71581/cogs/utility.py
        description = ""
        ts = datetime.now()
        try:
            guilds = '{:,.0f}'.format(len(self.bot.guilds))
            total_members = '{:,.0f}'.format(sum(1 for _ in self.bot.get_all_members()))
            total_unique = '{:,.0f}'.format(len(self.bot.users))
            total_bots = '{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.bot is True))
            total_online = '{:,.0f}'.format(sum(1 for m in self.bot.get_all_members() if m.status != disnake.Status.offline))
            cpu_usage = psutil.cpu_percent() / psutil.cpu_count()
            memory_usage = psutil.Process().memory_full_info().uss / 1024**2
            description = f"Total guild(s): `{guilds}` Total member(s): `{total_members}`\nUnique: `{total_unique}` Bots: `{total_bots}`\nOnline: `{total_online}`\n\n**Usage**: CPU: `{round(cpu_usage, 1)} %` Memory: `{round(memory_usage, 1)} MiB`"
            ts = datetime.fromtimestamp(int(psutil.Process().create_time()))
        except Exception:
            traceback.print_exc(file=sys.stdout)
        botdetails = disnake.Embed(title='About Me', description=description, timestamp=ts)
        botdetails.add_field(name='Creator\'s Discord Name:', value='pluton#8888', inline=True)
        botdetails.add_field(name='My Github:', value="[TipBot Github](https://github.com/wrkzcoin/TipBot)",
                             inline=True)
        botdetails.add_field(name='Invite Me:', value=self.bot.config['discord']['invite_link'], inline=True)
        try:
            get_tipping_count = await self.get_tipping_count()
            if get_tipping_count:
                botdetails.add_field(name="Tips", value='{:,.0f}'.format(get_tipping_count['nos_tipping']), inline=True)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        try:
            bot_settings = await self.utils.get_bot_settings()
            botdetails.add_field(name='Add Coin/Token', value=bot_settings['link_listing_form'], inline=False)
        except Exception:
            traceback.print_exc(file=sys.stdout)
        botdetails.set_footer(
            text='Made in Python',
            icon_url='http://findicons.com/files/icons/2804/plex/512/python.png'
        )
        botdetails.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
        return botdetails

    @commands.slash_command(
        usage="about",
        description="Get information about me."
    )
    async def about(
            self,
            ctx
    ):
        await self.async_about(ctx)

    @commands.user_command(name="About")
    async def about_me(self, ctx):
        await self.async_about(ctx)


def setup(bot):
    bot.add_cog(About(bot))
