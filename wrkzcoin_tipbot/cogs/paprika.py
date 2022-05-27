import sys
import traceback

import json
import aiohttp, asyncio
import disnake
from disnake.ext import commands, tasks
import time
import datetime
import functools
import random

# The selenium module
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from PIL import Image
from io import BytesIO
import os.path
from pyvirtualdisplay import Display
import os

from disnake.enums import OptionType
from disnake.app_commands import Option, OptionChoice

from Bot import EMOJI_CHART_DOWN, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_FLOPPY, logchanbot, EMOJI_HOURGLASS_NOT_DONE
import redis_utils
import store

from config import config


# https://api.coinpaprika.com/#tag/Tags/paths/~1tags~1{tag_id}/get

def get_trade_view_by_id( display_id: str, web_url: str, id_coin: str, saved_path: str ):
    timeout = 10
    return_to = None
    file_name = "tradeview_{}_image_{}.png".format( id_coin, datetime.datetime.now().strftime("%Y-%m-%d-%H-%M") ) #
    file_path = saved_path + file_name
    if os.path.exists(file_path):
        return file_name
    try:
        os.environ['DISPLAY'] = display_id
        display = Display(visible=0, size=(1366, 768))
        display.start()
        # Wait for 20s

        options = Options()
        options.add_argument('--no-sandbox') # Bypass OS security model
        options.add_argument('--disable-gpu')  # applicable to windows os only
        options.add_argument('start-maximized') # 
        options.add_argument('disable-infobars')
        options.add_argument("--disable-extensions")
        userAgent = config.selenium_setting.user_agent
        options.add_argument(f'user-agent={userAgent}')
        options.add_argument("--user-data-dir=chrome-data")
        options.headless = False

        driver = webdriver.Firefox(options=options)
        driver.set_window_position(0, 0)
        driver.set_window_size(config.selenium_setting.win_w, config.selenium_setting.win_h)

        driver.get( web_url )
        WebDriverWait(driver, timeout).until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR,"iframe[id^='tradingview']")))
        ## WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, "tv_chart_container")))
        WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CLASS_NAME, "chart-markup-table")))
        WebDriverWait(driver, timeout).until(EC.visibility_of_element_located((By.CLASS_NAME, "chart-container-border")))

        time.sleep(3.0)
        # https://stackoverflow.com/questions/8900073/webdriver-screenshot
        # now that we have the preliminary stuff out of the way time to get that image :D
        element = driver.find_element_by_class_name( "chart-page" ) # find part of the page you want image of
        location = element.location
        size = element.size
        png = driver.get_screenshot_as_png() # saves screenshot of entire page

        im = Image.open(BytesIO(png)) # uses PIL library to open image in memory
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']

        im = im.crop((left, top, right, bottom)) # defines crop points        
        im.save(file_path) # saves new cropped image
        driver.close() # closes the driver
        return_to = file_name
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    finally:
        display.stop()
        
    return return_to

class Paprika(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)
        redis_utils.openRedis()
        self.fetch_paprika_pricelist.start()
        
        # enable trade-view
        # Example: https://coinpaprika.com/trading-view/wrkz-wrkzcoin
        self.tradeview = True
        self.tradeview_url = "https://coinpaprika.com/trading-view/"
        self.tradeview_path = "./discordtip_v2_paprika_tradeview/"
        self.tradeview_static_png = "https://tipbot-static.wrkz.work/discordtip_v2_paprika_tradeview/"
        self.display_list = [f":{str(i)}" for i in range(100, 200)]


    async def bot_log(self):
        if self.botLogChan is None:
            self.botLogChan = self.bot.get_channel(self.bot.LOG_CHAN)


    @tasks.loop(seconds=3600)
    async def fetch_paprika_pricelist(self):
        time_lap = 1800 # seconds
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(time_lap)
            url = "https://api.coinpaprika.com/v1/tickers"
            try:
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(url, timeout=30) as r:
                        res_data = await r.read()
                        res_data = res_data.decode('utf-8')
                        decoded_data = json.loads(res_data)
                        update_time = int(time.time())
                        update_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                        if len(decoded_data) > 0:
                            update_list = []
                            insert_list = []
                            for each_coin in decoded_data:
                                try:
                                    quote_usd = each_coin['quotes']['USD']
                                    ath_date = None

                                    if quote_usd['ath_date'] and "." in quote_usd['ath_date']:
                                        ath_date = datetime.datetime.strptime(quote_usd['ath_date'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                    elif quote_usd['ath_date'] and "." not in quote_usd['ath_date']:
                                        ath_date = datetime.datetime.strptime(quote_usd['ath_date'], '%Y-%m-%dT%H:%M:%SZ')

                                    if "." in each_coin['last_updated']:
                                        last_updated = datetime.datetime.strptime(each_coin['last_updated'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                    else:
                                        last_updated = datetime.datetime.strptime(each_coin['last_updated'], '%Y-%m-%dT%H:%M:%SZ')
                                    update_list.append((each_coin['id'], each_coin['symbol'], each_coin['name'], each_coin['rank'], each_coin['circulating_supply'], each_coin['total_supply'], each_coin['max_supply'], quote_usd['price'], update_time, last_updated, quote_usd['price'], quote_usd['volume_24h'], quote_usd['volume_24h_change_24h'], quote_usd['market_cap'], quote_usd['market_cap_change_24h'], quote_usd['percent_change_15m'], quote_usd['percent_change_30m'], quote_usd['percent_change_1h'], quote_usd['percent_change_6h'], quote_usd['percent_change_12h'], quote_usd['percent_change_24h'], quote_usd['percent_change_7d'], quote_usd['percent_change_30d'], quote_usd['percent_change_1y'], quote_usd['ath_price'], ath_date, quote_usd['percent_from_price_ath']))

                                    insert_list.append((each_coin['id'], each_coin['rank'], each_coin['circulating_supply'], each_coin['total_supply'], each_coin['max_supply'], quote_usd['price'], update_time, last_updated, quote_usd['price'], quote_usd['volume_24h'], quote_usd['volume_24h_change_24h'], quote_usd['market_cap'], quote_usd['market_cap_change_24h'], quote_usd['percent_change_15m'], quote_usd['percent_change_30m'], quote_usd['percent_change_1h'], quote_usd['percent_change_6h'], quote_usd['percent_change_12h'], quote_usd['percent_change_24h'], quote_usd['percent_change_7d'], quote_usd['percent_change_30d'], quote_usd['percent_change_1y'], quote_usd['ath_price'], ath_date, quote_usd['percent_from_price_ath'],  update_time))
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            if len(update_list) or len(insert_list) > 0:
                                try:
                                    await store.openConnection()
                                    async with store.pool.acquire() as conn:
                                        async with conn.cursor() as cur:
                                            sql = """ INSERT INTO coin_paprika_list (`id`, `symbol`, `name`, `rank`, `circulating_supply`, `total_supply`, `max_supply`, `price_usd`, `price_time`, `last_updated`, `quotes_USD_price`, `quotes_USD_volume_24h`, `quotes_USD_volume_24h_change_24h`, `quotes_USD_market_cap`, `quotes_USD_market_cap_change_24h`, `quotes_USD_percent_change_15m`, `quotes_USD_percent_change_30m`, `quotes_USD_percent_change_1h`, `quotes_USD_percent_change_6h`, `quotes_USD_percent_change_12h`, `quotes_USD_percent_change_24h`, `quotes_USD_percent_change_7d`, `quotes_USD_percent_change_30d`, `quotes_USD_percent_change_1y`, `quotes_USD_ath_price`, `quotes_USD_ath_date`, `quotes_USD_percent_from_price_ath`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY 
                                                      UPDATE 
                                                      `rank`=VALUES(`rank`), 
                                                      `circulating_supply`=VALUES(`circulating_supply`), 
                                                      `total_supply`=VALUES(`total_supply`), 
                                                      `max_supply`=VALUES(`max_supply`), 
                                                      `price_usd`=VALUES(`price_usd`), 
                                                      `price_time`=VALUES(`price_time`), 
                                                      `last_updated`=VALUES(`last_updated`), 
                                                      `quotes_USD_price`=VALUES(`quotes_USD_price`), 
                                                      `quotes_USD_volume_24h`=VALUES(`quotes_USD_volume_24h`), 
                                                      `quotes_USD_volume_24h_change_24h`=VALUES(`quotes_USD_volume_24h_change_24h`), 
                                                      `quotes_USD_market_cap`=VALUES(`quotes_USD_market_cap`), 
                                                      `quotes_USD_market_cap_change_24h`=VALUES(`quotes_USD_market_cap_change_24h`), 
                                                      `quotes_USD_percent_change_15m`=VALUES(`quotes_USD_percent_change_15m`), 
                                                      `quotes_USD_percent_change_30m`=VALUES(`quotes_USD_percent_change_30m`), 
                                                      `quotes_USD_percent_change_1h`=VALUES(`quotes_USD_percent_change_1h`), 
                                                      `quotes_USD_percent_change_6h`=VALUES(`quotes_USD_percent_change_6h`), 
                                                      `quotes_USD_percent_change_12h`=VALUES(`quotes_USD_percent_change_12h`), 
                                                      `quotes_USD_percent_change_24h`=VALUES(`quotes_USD_percent_change_24h`), 
                                                      `quotes_USD_percent_change_7d`=VALUES(`quotes_USD_percent_change_7d`), 
                                                      `quotes_USD_percent_change_30d`=VALUES(`quotes_USD_percent_change_30d`), 
                                                      `quotes_USD_percent_change_1y`=VALUES(`quotes_USD_percent_change_1y`), 
                                                      `quotes_USD_ath_price`=VALUES(`quotes_USD_ath_price`), 
                                                      `quotes_USD_ath_date`=VALUES(`quotes_USD_ath_date`), 
                                                      `quotes_USD_percent_from_price_ath`=VALUES(`quotes_USD_percent_from_price_ath`)
                                                   """
                                            await cur.executemany(sql, update_list)
                                            await conn.commit()
                                            update_list = []

                                            sql = """ INSERT INTO coin_paprika_list_history (`id`, `rank`, `circulating_supply`, `total_supply`, `max_supply`, `price_usd`, `price_time`, `price_date`, `quotes_USD_price`, `quotes_USD_volume_24h`, `quotes_USD_volume_24h_change_24h`, `quotes_USD_market_cap`, `quotes_USD_market_cap_change_24h`, `quotes_USD_percent_change_15m`, `quotes_USD_percent_change_30m`, `quotes_USD_percent_change_1h`, `quotes_USD_percent_change_6h`, `quotes_USD_percent_change_12h`, `quotes_USD_percent_change_24h`, `quotes_USD_percent_change_7d`, `quotes_USD_percent_change_30d`, `quotes_USD_percent_change_1y`, `quotes_USD_ath_price`, `quotes_USD_ath_date`, `quotes_USD_percent_from_price_ath`, `inserted_date`) 
                                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                                            await cur.executemany(sql, insert_list)
                                            await conn.commit()
                                            insert_list = []
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                    # print(insert_list[-1])
            except asyncio.TimeoutError:
                print('TIMEOUT: Fetching from coingecko price')
            except Exception:
                traceback.print_exc(file=sys.stdout)
            await asyncio.sleep(time_lap)


    async def paprika_coin(
        self, 
        ctx, 
        coin: str
    ):

        try:
            await ctx.response.send_message(f"{EMOJI_HOURGLASS_NOT_DONE} {ctx.author.mention}, checking coinpaprika..")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return

        COIN_NAME = coin.upper()
        key = config.redis.prefix_paprika + coin.upper()
        # Get from redis
        try:
            if redis_utils.redis_conn.exists(key):
                response_text = redis_utils.redis_conn.get(key).decode()
                msg = f"{ctx.author.mention}, {response_text}"
                await ctx.edit_original_message(content=msg)
                # fetch tradeview image
                if self.tradeview == True:
                    try:
                        if COIN_NAME in self.bot.token_hints:
                            id = self.bot.token_hints[COIN_NAME]['ticker_name']
                        elif COIN_NAME in self.bot.token_hint_names:
                            id = self.bot.token_hint_names[COIN_NAME]['ticker_name']
                        else:
                            if redis_utils.redis_conn.exists(config.redis.prefix_paprika + "COINSLIST"):
                                j = json.loads(redis_utils.redis_conn.get(config.redis.prefix_paprika + "COINSLIST").decode())
                            else:
                                link = 'https://api.coinpaprika.com/v1/coins'
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(link) as resp:
                                        if resp.status == 200:
                                            j = await resp.json()
                                            # add to redis coins list
                                            try:
                                                redis_utils.redis_conn.set(config.redis.prefix_paprika + "COINSLIST", json.dumps(j), ex=config.redis.default_time_coinlist)
                                            except Exception as e:
                                                traceback.format_exc()
                                            # end add to redis
                            if COIN_NAME.isdigit():
                                for i in j:
                                    if int(COIN_NAME) == int(i['rank']):
                                        id = i['id']
                            else:
                                for i in j:
                                    if COIN_NAME.lower() == i['name'].lower() or COIN_NAME.lower() == i['symbol'].lower():
                                        id = i['id'] #i['name']
                        if len(self.display_list) > 2:
                            display_id = random.choice(self.display_list)
                            self.display_list.remove(display_id)
                            fetch_tradeview = functools.partial(get_trade_view_by_id, display_id, self.tradeview_url + id, id, self.tradeview_path )
                            self.display_list.append(display_id)
                            tv_image = await self.bot.loop.run_in_executor(None, fetch_tradeview)
                            if tv_image:
                                e = disnake.Embed(timestamp=datetime.datetime.now(), description=response_text)
                                e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                                e.set_image(url=self.tradeview_static_png + tv_image)
                                e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                                await ctx.edit_original_message(content=None, embed=e)
                    except Exception as e:
                        traceback.format_exc()
                return
        except Exception as e:
            traceback.format_exc()
            await logchanbot(traceback.format_exc())
            msg = f"{ctx.author.mention}, internal error from cache."
            await ctx.edit_original_message(content=msg)
            return

        if COIN_NAME in self.bot.token_hints:
            id = self.bot.token_hints[COIN_NAME]['ticker_name']
        elif COIN_NAME in self.bot.token_hint_names:
            id = self.bot.token_hint_names[COIN_NAME]['ticker_name']
        else:
            if redis_utils.redis_conn.exists(config.redis.prefix_paprika + "COINSLIST"):
                j = json.loads(redis_utils.redis_conn.get(config.redis.prefix_paprika + "COINSLIST").decode())
            else:
                link = 'https://api.coinpaprika.com/v1/coins'
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status == 200:
                            j = await resp.json()
                            # add to redis coins list
                            try:
                                redis_utils.redis_conn.set(config.redis.prefix_paprika + "COINSLIST", json.dumps(j), ex=config.redis.default_time_coinlist)
                            except Exception as e:
                                traceback.format_exc()
                            # end add to redis
            if COIN_NAME.isdigit():
                for i in j:
                    if int(COIN_NAME) == int(i['rank']):
                        id = i['id']
            else:
                for i in j:
                    if COIN_NAME.lower() == i['name'].lower() or COIN_NAME.lower() == i['symbol'].lower():
                        id = i['id'] #i['name']
        try:
            async with aiohttp.ClientSession() as session:
                url = 'https://api.coinpaprika.com/v1/tickers/{}'.format(id)
                async with session.get(url) as resp:
                    if resp.status == 200:
                        j = await resp.json()
                        if 'error' in j and j['error'] == 'id not found':
                            msg = f"{ctx.author.mention}, can not get data **{COIN_NAME}** from paprika."
                            await ctx.edit_original_message(content=msg)
                            return
                        if float(j['quotes']['USD']['price']) > 100:
                            trading_at = "${:.2f}".format(float(j['quotes']['USD']['price']))
                        elif float(j['quotes']['USD']['price']) > 1:
                            trading_at = "${:.3f}".format(float(j['quotes']['USD']['price']))
                        elif float(j['quotes']['USD']['price']) > 0.01:
                            trading_at = "${:.4f}".format(float(j['quotes']['USD']['price']))
                        else:
                            trading_at = "${:.8f}".format(float(j['quotes']['USD']['price']))
                        response_text = "{} ({}) is #{} by marketcap (${:,.2f}), trading at {} with a 24h vol of ${:,.2f}. It's changed {}% over 24h, {}% over 7d, {}% over 30d, and {}% over 1y with an ath of ${} on {}.".format(j['name'], j['symbol'], j['rank'], float(j['quotes']['USD']['market_cap']), trading_at, float(j['quotes']['USD']['volume_24h']), j['quotes']['USD']['percent_change_24h'], j['quotes']['USD']['percent_change_7d'], j['quotes']['USD']['percent_change_30d'], j['quotes']['USD']['percent_change_1y'], j['quotes']['USD']['ath_price'], j['quotes']['USD']['ath_date'])
                        try:
                            redis_utils.redis_conn.set(key, response_text, ex=config.redis.default_time_paprika)
                        except Exception as e:
                            traceback.format_exc()
                            await logchanbot(traceback.format_exc())
                        await ctx.edit_original_message(content=f"{ctx.author.mention}, {response_text}")
                        # fetch tradeview image
                        if self.tradeview == True:
                            try:
                                if COIN_NAME in self.bot.token_hints:
                                    id = self.bot.token_hints[COIN_NAME]['ticker_name']
                                elif COIN_NAME in self.bot.token_hint_names:
                                    id = self.bot.token_hint_names[COIN_NAME]['ticker_name']
                                else:
                                    if redis_utils.redis_conn.exists(config.redis.prefix_paprika + "COINSLIST"):
                                        j = json.loads(redis_utils.redis_conn.get(config.redis.prefix_paprika + "COINSLIST").decode())
                                    else:
                                        link = 'https://api.coinpaprika.com/v1/coins'
                                        async with aiohttp.ClientSession() as session:
                                            async with session.get(link) as resp:
                                                if resp.status == 200:
                                                    j = await resp.json()
                                                    # add to redis coins list
                                                    try:
                                                        redis_utils.redis_conn.set(config.redis.prefix_paprika + "COINSLIST", json.dumps(j), ex=config.redis.default_time_coinlist)
                                                    except Exception as e:
                                                        traceback.format_exc()
                                                    # end add to redis
                                    if COIN_NAME.isdigit():
                                        for i in j:
                                            if int(COIN_NAME) == int(i['rank']):
                                                id = i['id']
                                    else:
                                        for i in j:
                                            if COIN_NAME.lower() == i['name'].lower() or COIN_NAME.lower() == i['symbol'].lower():
                                                id = i['id'] #i['name']
                                if len(self.display_list) > 2:
                                    display_id = random.choice(self.display_list)
                                    self.display_list.remove(display_id)
                                    fetch_tradeview = functools.partial(get_trade_view_by_id, display_id, self.tradeview_url + id, id, self.tradeview_path )
                                    self.display_list.append(display_id)
                                    tv_image = await self.bot.loop.run_in_executor(None, fetch_tradeview)
                                    if tv_image:
                                        e = disnake.Embed(timestamp=datetime.datetime.now(), description=response_text)
                                        e.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar)
                                        e.set_image(url=self.tradeview_static_png + tv_image)
                                        e.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}")
                                        await ctx.edit_original_message(content=None, embed=e)
                            except Exception as e:
                                traceback.format_exc()
                    else:
                        await ctx.edit_original_message(content=f"{ctx.author.mention}, can not get data **{COIN_NAME}** from paprika.")
                    return
        except Exception as e:
            traceback.format_exc()
        await ctx.edit_original_message(content=f"{ctx.author.mention}, no paprika only salt.")

    @commands.slash_command(usage="paprika [coin]",
                            options=[
                                Option("coin", "Enter coin ticker/name", OptionType.string, required=True)
                            ],
                            description="Check coin at Paprika.")
    async def paprika(
        self, 
        ctx, 
        coin: str
    ):
        get_pap = await self.paprika_coin( ctx, coin )


def setup(bot):
    bot.add_cog(Paprika(bot))
