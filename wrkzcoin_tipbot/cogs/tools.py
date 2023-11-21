import functools
import io
import os
import random
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime

import disnake
import store
from Bot import EMOJI_CHECKMARK, EMOJI_ERROR, EMOJI_INFORMATION, SERVER_BOT, logchanbot
from cogs.utils import Utils

# pip3 install -U deep-translator
from deep_translator import GoogleTranslator
from disnake.app_commands import Option
from disnake.enums import OptionType
from disnake.ext import commands

# gTTs
from gtts import gTTS


class Tool(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        self.utils = Utils(self.bot)

        # TTS path
        self.tts_path = "./tts/"

    async def sql_add_tts(
        self,
        user_id: str,
        user_name: str,
        msg_content: str,
        lang: str,
        tts_mp3: str,
        user_server: str = "DISCORD",
    ):
        user_server = user_server.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `discord_tts` 
                    (`user_id`, `user_name`, `msg_content`, `lang`, `time`, `tts_mp3`, `user_server`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(
                        sql,
                        (
                            user_id,
                            user_name,
                            msg_content,
                            lang,
                            int(time.time()),
                            tts_mp3,
                            user_server,
                        ),
                    )
                    await conn.commit()
                    return True
        except Exception:
            await logchanbot("tools " + str(traceback.format_exc()))
        return False

    async def sql_add_trans_tts(
        self,
        user_id: str,
        user_name: str,
        original: str,
        translated: str,
        to_lang: str,
        media_file: str,
        user_server: str = "DISCORD",
    ):
        user_server = user_server.upper()
        try:
            await store.openConnection()
            async with store.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `discord_trans_tts` (`user_id`, `user_name`, `original`, `translated`, 
                    `to_lang`, `time`, `media_file`, `user_server`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(
                        sql,
                        (
                            user_id,
                            user_name,
                            original,
                            translated,
                            to_lang,
                            int(time.time()),
                            media_file,
                            user_server,
                        ),
                    )
                    await conn.commit()
                    return True
        except Exception:
            await logchanbot("tools " + str(traceback.format_exc()))
        return False

    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)

    @commands.slash_command(description="Various tool's commands.")
    async def tool(self, ctx):
        # This is just a parent for subcommands
        # It's not necessary to do anything here,
        # but if you do, it runs for any subcommand nested below
        pass

    @tool.sub_command(
        usage="tool tts <text to translate>",
        options=[Option("input_text", "input_text", OptionType.string, required=True)],
        description="Tex to speak",
    )
    async def tts(self, ctx, input_text: str):
        # -*- coding: utf-8 -*-
        def isEnglish(s):
            try:
                s.encode(encoding="utf-8").decode("ascii")
            except UnicodeDecodeError:
                return False
            else:
                return True

        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, checking TTS..."
        await ctx.response.send_message(msg)

        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/tool tts",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

        if not isEnglish(input_text):
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, TTS supports English only."
            )
            return
        else:

            def user_speech(text):
                try:
                    speech_txt = text
                    tts = gTTS(text=speech_txt, lang="en")
                    random_mp3_name = (
                        time.strftime("%Y%m%d-%H%M_") + str(uuid.uuid4()) + ".mp3"
                    )
                    tts.save(self.tts_path + random_mp3_name)
                    return random_mp3_name
                except Exception:
                    traceback.print_exc(file=sys.stdout)

            try:
                make_voice = functools.partial(user_speech, input_text)
                voice_file = await self.bot.loop.run_in_executor(None, make_voice)
                file = disnake.File(self.tts_path + voice_file, filename=voice_file)
                await ctx.edit_original_message(
                    content="{}".format(ctx.author.mention), file=file
                )
                await self.sql_add_tts(
                    str(ctx.author.id),
                    "{}#{}".format(ctx.author.name, ctx.author.discriminator),
                    input_text,
                    "en",
                    voice_file,
                    SERVER_BOT,
                )
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await logchanbot("tools " + str(traceback.format_exc()))
        return

    @tool.sub_command(
        usage="tool translate <to_language> <text to translate>",
        options=[
            Option("to_language", "to_language", OptionType.string, required=True),
            Option("input_text", "input_text", OptionType.string, required=True),
        ],
        description="use Google Translator",
    )
    async def translate(self, ctx, to_language: str, input_text: str):
        to_lang = to_language.lower()
        LANGUAGES = {
            "af": "afrikaans",
            "sq": "albanian",
            "am": "amharic",
            "ar": "arabic",
            "hy": "armenian",
            "az": "azerbaijani",
            "eu": "basque",
            "be": "belarusian",
            "bn": "bengali",
            "bs": "bosnian",
            "bg": "bulgarian",
            "ca": "catalan",
            "ceb": "cebuano",
            "ny": "chichewa",
            "zh-cn": "chinese (simplified)",
            "zh-tw": "chinese (traditional)",
            "co": "corsican",
            "hr": "croatian",
            "cs": "czech",
            "da": "danish",
            "nl": "dutch",
            "en": "english",
            "eo": "esperanto",
            "et": "estonian",
            "tl": "filipino",
            "fi": "finnish",
            "fr": "french",
            "fy": "frisian",
            "gl": "galician",
            "ka": "georgian",
            "de": "german",
            "el": "greek",
            "gu": "gujarati",
            "ht": "haitian creole",
            "ha": "hausa",
            "haw": "hawaiian",
            "iw": "hebrew",
            "he": "hebrew",
            "hi": "hindi",
            "hmn": "hmong",
            "hu": "hungarian",
            "is": "icelandic",
            "ig": "igbo",
            "id": "indonesian",
            "ga": "irish",
            "it": "italian",
            "ja": "japanese",
            "jw": "javanese",
            "kn": "kannada",
            "kk": "kazakh",
            "km": "khmer",
            "ko": "korean",
            "ku": "kurdish (kurmanji)",
            "ky": "kyrgyz",
            "lo": "lao",
            "la": "latin",
            "lv": "latvian",
            "lt": "lithuanian",
            "lb": "luxembourgish",
            "mk": "macedonian",
            "mg": "malagasy",
            "ms": "malay",
            "ml": "malayalam",
            "mt": "maltese",
            "mi": "maori",
            "mr": "marathi",
            "mn": "mongolian",
            "my": "myanmar (burmese)",
            "ne": "nepali",
            "no": "norwegian",
            "or": "odia",
            "ps": "pashto",
            "fa": "persian",
            "pl": "polish",
            "pt": "portuguese",
            "pa": "punjabi",
            "ro": "romanian",
            "ru": "russian",
            "sm": "samoan",
            "gd": "scots gaelic",
            "sr": "serbian",
            "st": "sesotho",
            "sn": "shona",
            "sd": "sindhi",
            "si": "sinhala",
            "sk": "slovak",
            "sl": "slovenian",
            "so": "somali",
            "es": "spanish",
            "su": "sundanese",
            "sw": "swahili",
            "sv": "swedish",
            "tg": "tajik",
            "ta": "tamil",
            "te": "telugu",
            "th": "thai",
            "tr": "turkish",
            "uk": "ukrainian",
            "ur": "urdu",
            "ug": "uyghur",
            "uz": "uzbek",
            "vi": "vietnamese",
            "cy": "welsh",
            "xh": "xhosa",
            "yi": "yiddish",
            "yo": "yoruba",
            "zu": "zulu",
        }
        msg = f"{EMOJI_INFORMATION} {ctx.author.mention}, checking translation..."
        await ctx.response.send_message(msg)

        if to_lang not in LANGUAGES or to_lang.upper() == "HELP":
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, supported language code: {self.bot.config['others']['g_language_code_url']}"
            )
            return
        else:

            def user_translated(input_text, to_lang: str):
                try:
                    GoogleTranslator()
                    translated = GoogleTranslator(
                        source="auto", target=to_lang
                    ).translate(input_text)
                    speech_txt = translated

                    tts = gTTS(text=speech_txt, lang=to_lang)
                    rand_str = time.strftime("%Y%m%d-%H%M_") + str(uuid.uuid4())
                    random_mp3_name = rand_str + ".mp3"
                    random_mp4_name = rand_str + ".mp4"
                    tts.save(self.tts_path + random_mp3_name)
                    command = f'ffmpeg -i {self.tts_path + random_mp3_name} -filter_complex "[0:a]showwaves=s=640x360:mode=cline:r=30,colorkey=0x000000:0.01:0.1,format=yuv420p[vid]" -map "[vid]" -map 0:a -codec:v libx264 -crf 18 -c:a copy {self.tts_path + random_mp4_name}'
                    process_video = subprocess.Popen(command, shell=True)
                    process_video.wait(timeout=20000)  # 20s waiting
                    os.remove(self.tts_path + random_mp3_name)
                    return {
                        "file": random_mp4_name,
                        "original": input_text,
                        "translated": translated,
                        "to_lang": to_lang,
                    }
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                return None

            try:
                make_voice = functools.partial(user_translated, input_text, to_lang)
                voice_file = await self.bot.loop.run_in_executor(None, make_voice)
                if voice_file:
                    file = disnake.File(
                        self.tts_path + voice_file["file"], filename=voice_file["file"]
                    )
                    await ctx.edit_original_message(
                        content="{}: {}".format(
                            ctx.author.mention, voice_file["translated"]
                        ),
                        file=file,
                    )
                    await self.sql_add_trans_tts(
                        str(ctx.author.id),
                        "{}#{}".format(ctx.author.name, ctx.author.discriminator),
                        input_text,
                        voice_file["translated"],
                        to_lang,
                        voice_file["file"],
                        SERVER_BOT,
                    )
                else:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, internal error."
                    )
            except Exception:
                traceback.print_exc(file=sys.stdout)
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, internal error. The media file could be "
                    f"too big or text too long. Please reduce your text length."
                )
                await logchanbot(
                    f"[TRANSLATE] {ctx.author.name}#{ctx.author.discriminator} failed to get translation with {to_lang} ```{input_text}```"
                )

        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/tool translate",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    # For each subcommand you can specify individual options and other parameters,
    # see the "Objects and methods" reference to learn more.
    @tool.sub_command(
        usage="tool avatar <member>",
        options=[Option("member", "member", OptionType.user, required=True)],
        description="Get avatar of a user.",
    )
    async def avatar(self, ctx, member: disnake.Member):
        if member is None:
            member = ctx.author
        try:
            msg = await ctx.response.send_message(
                f"Avatar image for {member.mention}:\n{str(member.display_avatar)}"
            )
        except Exception:
            await logchanbot("tools " + str(traceback.format_exc()))
        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/tool avatar",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @tool.sub_command(
        usage="tool prime <number>",
        options=[Option("number", "number", OptionType.string, required=True)],
        description="Check a given number if it is a prime number.",
    )
    async def prime(self, ctx, number: str):
        # https://en.wikipedia.org/wiki/Primality_test
        def is_prime(n: int) -> bool:
            """Primality test using 6k+-1 optimization."""
            if n <= 3:
                return n > 1
            if n % 2 == 0 or n % 3 == 0:
                return False
            i = 5
            while i**2 <= n:
                if n % i == 0 or n % (i + 2) == 0:
                    return False
                i += 6
            return True

        number = number.replace(",", "")
        if len(number) >= 1900:
            await ctx.response.send_message(
                f"{ctx.author.mention} {EMOJI_ERROR} given number is too long."
            )
            return
        try:
            value = is_prime(int(number))
            if value:
                await ctx.response.send_message(
                    f"{ctx.author.mention} {EMOJI_CHECKMARK} Given number is a prime number: ```{str(number)}```"
                )
            else:
                await ctx.response.send_message(
                    f"{ctx.author.mention} {EMOJI_ERROR} Given number is not a prime number: ```{str(number)}```"
                )
        except ValueError:
            await ctx.response.send_message(
                f"{ctx.author.mention} {EMOJI_ERROR} Number error."
            )
        try:
            self.bot.commandings.append(
                (
                    str(ctx.guild.id)
                    if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                    else "DM",
                    str(ctx.author.id),
                    SERVER_BOT,
                    "/tool prime",
                    int(time.time()),
                )
            )
            await self.utils.add_command_calls()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        name="whoreact",
        description="Get list of user who reacts on a message.",
    )
    async def command_whoreact(
        self, ctx, msg_id: str, channel: disnake.TextChannel = None
    ) -> None:
        """/whoreact <message ID>"""
        await ctx.response.send_message(
            f"{ctx.author.mention} finding message & re-action..."
        )
        try:
            msg_id = int(msg_id)
            try:
                if channel is not None:
                    _msg: disnake.Message = await channel.fetch_message(msg_id)
                    msg_link = (
                        "<https://discord.com/channels/"
                        + str(ctx.guild.id)
                        + "/"
                        + str(channel.id)
                        + "/"
                        + str(msg_id)
                        + ">"
                    )
                else:
                    _msg: disnake.Message = await ctx.channel.fetch_message(msg_id)
                    msg_link = (
                        "<https://discord.com/channels/"
                        + str(ctx.guild.id)
                        + "/"
                        + str(ctx.channel.id)
                        + "/"
                        + str(msg_id)
                        + ">"
                    )
            except disnake.errors.NotFound:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, message not found or wrong channel."
                )
                return

            if _msg is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, I can't find that message `{str(msg_id)}` ({msg_link}). "
                    "Try again later or double check the ID."
                )
            else:
                attend_list = []
                if len(_msg.reactions) > 0:
                    for each_r in _msg.reactions:
                        attend_list += [
                            user
                            async for user in each_r.users()
                            if not user.bot and user != ctx.author
                        ]

                    attend_list = list(set(attend_list))
                    if len(attend_list) > 0:
                        list_user_ids = " ".join(
                            ["<@{}>".format(u.id) for u in attend_list]
                        )
                        list_user_names = " ".join(
                            [
                                "{}#{}".format(u.name, u.discriminator)
                                for u in attend_list
                            ]
                        )
                        concat_str = (
                            f"Total list of user ID ({str(len(attend_list))}):\n"
                            + list_user_ids
                            + "\n\nList of user name(s):\n"
                            + list_user_names
                        )
                        if len(concat_str) < 1000:
                            await ctx.edit_original_message(
                                content="```{}```".format(concat_str)
                            )
                        else:
                            data_file = disnake.File(
                                io.BytesIO(concat_str.encode()),
                                filename=f"Re-act on message_{msg_id}_{str(int(time.time()))}.txt",
                            )
                            await ctx.edit_original_message(
                                content=None, file=data_file
                            )
                    else:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, there is no one re-act on that message {msg_link}."
                        )
                else:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, I can't find anyone re-act to that message {msg_link}."
                    )
        except ValueError:
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, invalid message ID."
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.guild_only()
    @commands.slash_command(
        dm_permission=False,
        name="pickuser",
        description="Pick a user from who re-act on a message.",
    )
    async def command_pickuser(
        self, ctx, msg_id: str, emoji_str: str, channel: disnake.TextChannel = None
    ) -> None:
        """/pickuser <message ID> <emoji>"""
        await ctx.response.send_message(
            f"{ctx.author.mention} finding message & re-action..."
        )
        try:
            msg_id = int(msg_id)
            try:
                if channel is not None:
                    _msg: disnake.Message = await channel.fetch_message(msg_id)
                else:
                    _msg: disnake.Message = await ctx.channel.fetch_message(msg_id)
            except disnake.errors.NotFound:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, message not found or wrong channel."
                )
                return

            if _msg is None:
                await ctx.edit_original_message(
                    content=f"{ctx.author.mention}, I can't find that message `{str(msg_id)}`. Try again later or double check the ID."
                )
            else:
                # check if that's his message
                if _msg.author != ctx.author:
                    await ctx.edit_original_message(
                        content=f"{ctx.author.mention}, you can only do with your message. Try again!"
                    )
                    return
                else:
                    my_emoji = disnake.PartialEmoji.from_str(emoji_str)
                    if my_emoji is None:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, I can't get emoji from string `{emoji_str}`!"
                        )
                        return

                    attend_list = []
                    if len(_msg.reactions) > 0:
                        for each_r in _msg.reactions:
                            if str(each_r) == str(emoji_str):
                                attend_list = [
                                    user
                                    async for user in each_r.users()
                                    if not user.bot and user != ctx.author
                                ]
                            else:
                                continue
                        if len(attend_list) > 1:
                            random.seed(datetime.now())
                            picked_u = random.choice(attend_list)
                            await ctx.edit_original_message(
                                content=f"{ctx.author.mention}, there are total {str(len(attend_list))} users. A random selected {picked_u.mention} by {self.bot.user.mention}."
                            )
                        else:
                            await ctx.edit_original_message(
                                content=f"{ctx.author.mention}, need more user to re-act on that mesage with {emoji_str}."
                            )
                    else:
                        await ctx.edit_original_message(
                            content=f"{ctx.author.mention}, I can't find anyone re-act with {emoji_str}."
                        )
        except ValueError:
            await ctx.edit_original_message(
                content=f"{ctx.author.mention}, invalid message ID."
            )
        except Exception:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(Tool(bot))
