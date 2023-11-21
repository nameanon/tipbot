import sys
import time
import traceback

from Bot import SERVER_BOT
from cogs.utils import Utils
from disnake.ext import commands


class Invite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)

    @commands.slash_command(description="Get TipBot's invite link.")
    async def invite(self, ctx):
        await ctx.response.send_message(
            f"**[INVITE LINK]**: {self.bot.config['discord']['invite_link']}",
            ephemeral=False,
        )
        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/invite",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Invite(bot))
