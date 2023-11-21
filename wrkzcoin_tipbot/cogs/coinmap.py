import datetime
import functools
import os
import os.path
import random
import sys
import time
import traceback
from io import BytesIO

from Bot import EMOJI_RED_NO, SERVER_BOT
from cogs.utils import Utils
from disnake.ext import commands
from PIL import Image
from pyvirtualdisplay import Display

# The selenium module
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def get_coin360(display_id: str, static_coin360_path, selenium_setting, coin360):
    return_to = None
    file_name = (
        f'coin360_image_{datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")}.png'
    )
    file_path = static_coin360_path + file_name
    if os.path.exists(file_path):
        return file_name

    timeout = 20
    try:
        os.environ["DISPLAY"] = display_id
        display = Display(visible=0, size=(1366, 768))
        display.start()

        options = webdriver.ChromeOptions()
        options = Options()
        options.add_argument("--no-sandbox")  # Bypass OS security model
        options.add_argument("--disable-gpu")  # applicable to windows os only
        options.add_argument("start-maximized")  #
        options.add_argument("disable-infobars")
        options.add_argument("--disable-extensions")
        userAgent = selenium_setting["user_agent"]
        options.add_argument(f"user-agent={userAgent}")
        options.add_argument("--user-data-dir=chrome-data")
        options.headless = True

        driver = webdriver.Chrome(options=options)
        driver.set_window_position(0, 0)
        driver.set_window_size(selenium_setting["win_w"], selenium_setting["win_h"])

        driver.get(coin360["url"])
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "SHA256"))
        )
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.ID, "EtHash"))
        )
        time.sleep(3.0)

        # https://stackoverflow.com/questions/8900073/webdriver-screenshot
        # now that we have the preliminary stuff out of the way time to get that image :D
        # Lib updated: https://stackoverflow.com/questions/72773206/selenium-python-attributeerror-webdriver-object-has-no-attribute-find-el
        # find_element(By.ID, ‘id’)
        # find_element(By.NAME, ‘name’)
        # find_element(By.XPATH, ‘xpath’)
        element = driver.find_element(
            By.ID, coin360["id_crop"]
        )  # find part of the page you want image of
        location = element.location
        size = element.size
        png = driver.get_screenshot_as_png()  # saves screenshot of entire page

        im = Image.open(BytesIO(png))  # uses PIL library to open image in memory
        left = location["x"]
        top = location["y"]
        right = location["x"] + size["width"]
        bottom = location["y"] + size["height"]
        im = im.crop((left, top, right, bottom))  # defines crop points

        im.save(file_path)  # saves new cropped image
        driver.close()  # closes the driver
        return_to = file_name
    except Exception:
        traceback.print_exc(file=sys.stdout)
    finally:
        display.stop()
    return return_to


class CoinMap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.utils = Utils(self.bot)
        self.display_list = [f":{str(i)}" for i in range(200, 300)]

    @commands.guild_only()
    @commands.slash_command(usage="coinmap", description="Get view from coin360.")
    async def coinmap(self, ctx):
        try:
            await ctx.response.send_message(f"{ctx.author.mention}, loading...")
            try:
                self.bot.commandings.append(
                    (
                        str(ctx.guild.id)
                        if hasattr(ctx, "guild") and hasattr(ctx.guild, "id")
                        else "DM",
                        str(ctx.author.id),
                        SERVER_BOT,
                        "/coinmap",
                        int(time.time()),
                    )
                )
                await self.utils.add_command_calls()
            except Exception:
                traceback.print_exc(file=sys.stdout)
            display_id = random.choice(self.display_list)
            self.display_list.remove(display_id)
            fetch_coin360 = functools.partial(
                get_coin360,
                display_id,
                self.bot.config["coin360"]["static_coin360_path"],
                self.bot.config["selenium_setting"],
                self.bot.config["coin360"],
            )
            map_image = await self.bot.loop.run_in_executor(None, fetch_coin360)
            self.display_list.append(display_id)
            if map_image:
                await ctx.edit_original_message(
                    content=self.bot.config["coin360"]["static_coin360_link"]
                    + map_image
                )
            else:
                await ctx.edit_original_message(
                    content=f"{EMOJI_RED_NO} {ctx.author.mention}, internal error during fetch image."
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)


def setup(bot):
    bot.add_cog(CoinMap(bot))
