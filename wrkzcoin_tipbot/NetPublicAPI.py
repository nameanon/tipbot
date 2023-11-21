#!/usr/bin/python3.8
from fastapi import FastAPI, Response, Header, Query
from fastapi.concurrency import run_in_threadpool
import traceback, sys
import uvicorn
import os
from typing import Union

import asyncio
import json
import math
import sys
import time
import traceback
from decimal import Decimal

import aiomysql
from aiohttp import web
from aiomysql.cursors import DictCursor
from sqlitedict import SqliteDict

from config import load_config

app = FastAPI()
config = load_config()


class DBStore():
    def __init__(self):
        # DB
        self.pool = None
        self.enable_trade_coin = []
        self.cache_kv_db_test = SqliteDict(config['cache']['temp_leveldb_gen'], tablename="test", flag='r')
        self.cache_kv_db_general = SqliteDict(config['cache']['temp_leveldb_gen'], tablename="general", flag='r')
        self.cache_kv_db_block = SqliteDict(config['cache']['temp_leveldb_gen'], tablename="block", flag='r')

    def get_cache_kv(self, table: str, key: str):
        try:
            if table.lower() == "test":
                return self.cache_kv_db_test[key.upper()]
            elif table.lower() == "general":
                return self.cache_kv_db_general[key.upper()]
            elif table.lower() == "block":
                return self.cache_kv_db_block[key.upper()]
        except KeyError:
            pass
        return None

    async def openConnection(self):
        try:
            if self.pool is None:
                self.pool = await aiomysql.create_pool(
                    host=config['mysql']['host'], port=3306, minsize=1, maxsize=2,
                    user=config['mysql']['user'], password=config['mysql']['password'],
                    db=config['mysql']['db'], cursorclass=DictCursor, autocommit=True
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def get_all_coin(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `coin_settings` WHERE `enable`=1
                    """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result: return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_trading_coinlist(self):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM coin_settings 
                    WHERE `enable_trade`=%s AND `enable`=%s """
                    await cur.execute(sql, (1, 1))
                    return await cur.fetchall()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    def truncate(self, number, digits) -> float:
        stepper = Decimal(pow(10.0, digits))
        return math.trunc(stepper * Decimal(number)) / stepper

    def num_format_coin(self, amount):
        if amount == 0:
            return "0.0"

        amount = self.truncate(amount, 8)
        amount_test = '{:,f}'.format(float(('%f' % (amount)).rstrip('0').rstrip('.')))
        if '.' in amount_test and len(amount_test.split('.')[1]) > 8:
            amount_str = '{:,.8f}'.format(amount)
        else:
            amount_str = amount_test
        return amount_str.rstrip('0').rstrip('.') if '.' in amount_str else amount_str

    async def sql_get_open_order_by_alluser_by_coins(
        self, coin1: str, coin2: str, status: str, option_order: str, limit: int = 50
    ):
        option_order = option_order.upper()
        if option_order not in ["DESC", "ASC"]:
            return False
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if coin2.upper() == "ALL":
                        sql = """ SELECT * FROM open_order 
                        WHERE `status`=%s AND `coin_sell`=%s 
                        ORDER BY sell_div_get """ + option_order + """ LIMIT """ + str(limit)
                        await cur.execute(sql, (status, coin1.upper()))
                    else:
                        sql = """ SELECT * FROM open_order 
                        WHERE `status`=%s AND `coin_sell`=%s AND `coin_get`=%s 
                        ORDER BY sell_div_get """ + option_order + """ LIMIT """ + str(limit)
                        await cur.execute(sql, (status, coin1.upper(), coin2.upper()))
                    return await cur.fetchall()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def sql_get_markets_by_coin(self, coin: str, status: str):
        global pool
        coin_name = coin.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT DISTINCT `coin_sell`, `coin_get` 
                    FROM `open_order` 
                    WHERE `status`=%s AND (`coin_sell`=%s OR `coin_get`=%s)
                    """
                    await cur.execute(sql, (status, coin_name, coin_name))
                    return await cur.fetchall()
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def sql_get_order_numb(self, order_num: str, status: str = None):
        if status is None: status = 'OPEN'
        if status: status = status.upper()
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    result = None
                    if status == "ANY":
                        sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s LIMIT 1 """
                        await cur.execute(sql, order_num)
                    else:
                        sql = """ SELECT * FROM `open_order` WHERE `order_id` = %s 
                                  AND `status`=%s LIMIT 1 """
                        await cur.execute(sql, (order_num, status))
                    return await cur.fetchone()
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def sql_get_coin_trade_stat(self, coin: str):
        try:
            await self.openConnection()
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT (SELECT SUM(amount_sell) FROM open_order 
                              WHERE coin_sell=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24) AS sell_24h, 
                              (SELECT SUM(amount_get) FROM open_order 
                              WHERE coin_get=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24) AS get_24h,
                              (SELECT SUM(amount_sell) FROM open_order 
                              WHERE coin_sell=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*7) AS sell_7d, 
                              (SELECT SUM(amount_get) FROM open_order 
                              WHERE coin_get=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*7) AS get_7d,
                              (SELECT SUM(amount_sell) FROM open_order 
                              WHERE coin_sell=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*30) AS sell_30d, 
                              (SELECT SUM(amount_get) FROM open_order 
                              WHERE coin_get=%s AND status='COMPLETE' AND order_completed_date > UNIX_TIMESTAMP()-3600*24*30) AS get_30d
                              """
                    await cur.execute(sql, (
                    coin.upper(), coin.upper(), coin.upper(), coin.upper(), coin.upper(), coin.upper()))
                    result = await cur.fetchone()
                    if result:
                        result['sell_24h'] = result['sell_24h'] if result['sell_24h'] else 0
                        result['get_24h'] = result['get_24h'] if result['get_24h'] else 0
                        result['sell_7d'] = result['sell_7d'] if result['sell_7d'] else 0
                        result['get_7d'] = result['get_7d'] if result['get_7d'] else 0
                        result['sell_30d'] = result['sell_30d'] if result['sell_30d'] else 0
                        result['get_30d'] = result['get_30d'] if result['get_30d'] else 0
                        return {'trade_24h': result['sell_24h'] + result['get_24h'],
                                'trade_7d': result['sell_7d'] + result['get_7d'],
                                'trade_30d': result['sell_30d'] + result['get_30d']}
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return None


app.db = DBStore()

@app.get("/orders/{market_pair}")
async def show_all_ordered_books(market_pair: str):
    # catch order book market.
    market_pair = market_pair.upper().split("-") if market_pair else None
    if len(market_pair) != 2 or market_pair is None:
        return {
            "error": "Invalid market pair!",
            "time": int(time.time())
        }
    sell_coin = market_pair[0]
    buy_coin = market_pair[1]
    get_market_buy_list = await app.db.sql_get_open_order_by_alluser_by_coins(
        sell_coin, buy_coin, "OPEN", "ASC", 1000
    )
    get_market_sell_list = await app.db.sql_get_open_order_by_alluser_by_coins(
        buy_coin, sell_coin, "OPEN", "DESC", 1000
    )
    buy_refs = []
    sell_refs = []
    if get_market_buy_list and len(get_market_buy_list) > 0:
        for each_buy in get_market_buy_list:
            rate = "{:.8f}".format(each_buy['amount_sell'] / each_buy['amount_get'])
            amount = "{:.8f}".format(each_buy['amount_sell'])
            buy_refs.append(
                {
                    str(each_buy["order_id"]): {
                        "sell": {
                            "coin_sell": each_buy['coin_sell'],
                            "amount_sell": app.db.num_format_coin(each_buy['amount_sell_after_fee']),
                            "fee_sell": app.db.num_format_coin(each_buy['amount_sell'] - each_buy['amount_sell_after_fee']),
                            "total": app.db.num_format_coin(each_buy['amount_sell'])
                        },
                        "for": {
                            "coin_get": each_buy['coin_get'],
                            "amount_get": app.db.num_format_coin(each_buy['amount_get_after_fee']),
                            "fee_get": app.db.num_format_coin(each_buy['amount_get'] - each_buy['amount_get_after_fee']),
                            "total": app.db.num_format_coin(each_buy['amount_get'])
                        }
                    }
            })
    if get_market_sell_list and len(get_market_sell_list) > 0:
        for each_sell in get_market_sell_list:
            rate = "{:.8f}".format(each_sell['amount_sell'] / each_sell['amount_get'])
            amount = "{:.8f}".format(each_sell['amount_get'])
            sell_refs.append(
                {
                    str(each_sell["order_id"]): {
                        "sell": {
                            "coin_sell": each_sell['coin_sell'],
                            "amount_sell": app.db.num_format_coin(each_sell['amount_sell_after_fee']),
                            "fee_sell": app.db.num_format_coin(each_sell['amount_sell'] - each_sell['amount_sell_after_fee']),
                            "total": app.db.num_format_coin(each_sell['amount_sell'])
                        },
                        "for": {
                            "coin_get": each_sell['coin_get'],
                            "amount_get": app.db.num_format_coin(each_sell['amount_get_after_fee']),
                            "fee_get": app.db.num_format_coin(each_sell['amount_get'] - each_sell['amount_get_after_fee']),
                            "total": app.db.num_format_coin(each_sell['amount_get'])
                        }
                    }
                }
            )
    result = {
        "success": False,
        "order_book": f"{sell_coin}-{buy_coin}",
        "time": int(time.time()),
    }
    if buy_refs or sell_refs:
        result = {
            "success": True,
            "order_book": f"{sell_coin}-{buy_coin}",
            "buys": buy_refs,
            "sells": sell_refs,
            "time": int(time.time()),
        }
    return result

@app.get("/order/{ref_number}")
async def show_order_by_referenced_number(ref_number: str):
    if not ref_number.isnumeric():
        return {
            "error": "referenced number should be numeric only!",
            "time": int(time.time())
        }
    get_order_num = await app.db.sql_get_order_numb(ref_number, 'ANY')
    if get_order_num:
        return {
            "success": True,
            "ref_number": f"#{get_order_num['order_id']}",
            "sell": {
                "coin_sell": get_order_num['coin_sell'],
                "amount_sell": app.db.num_format_coin(
                    get_order_num['amount_sell_after_fee']
                ),
                "fee_sell": app.db.num_format_coin(
                    get_order_num['amount_sell']
                    - get_order_num['amount_sell_after_fee']
                ),
                "total": app.db.num_format_coin(get_order_num['amount_sell']),
            },
            "for": {
                "coin_get": get_order_num['coin_get'],
                "amount_get": app.db.num_format_coin(
                    get_order_num['amount_get_after_fee']
                ),
                "fee_get": app.db.num_format_coin(
                    get_order_num['amount_get']
                    - get_order_num['amount_get_after_fee']
                ),
                "total": app.db.num_format_coin(get_order_num['amount_get']),
            },
            "status": get_order_num['status'],
            "time": int(time.time()),
        }
    else:
        return {
            "success": False,
            "error": "ref_number not found.",
            "time": int(time.time())
        }

@app.get("/markets/list")
async def list_all_available_markets():
    market_list = {}
    pairs = []
    list_trading_coins = await app.db.get_trading_coinlist()
    enabled_coin = [each['coin_name'] for each in list_trading_coins]
    for each_coin in enabled_coin:
        each_market_coin = await app.db.sql_get_markets_by_coin(each_coin, 'OPEN')
        if each_market_coin and len(each_market_coin) > 0:
            for each_item in each_market_coin:
                sell_coin = each_item['coin_sell']
                buy_coin = each_item['coin_get']
                pair_items = f"{sell_coin}-{buy_coin}"
                if pair_items not in pairs:
                    pairs.append(pair_items)
                    get_market_buy_list = await app.db.sql_get_open_order_by_alluser_by_coins(
                        sell_coin, buy_coin, "OPEN", "ASC", 1000
                    )
                    get_market_sell_list = await app.db.sql_get_open_order_by_alluser_by_coins(
                        buy_coin, sell_coin, "OPEN", "DESC", 1000
                    )
                    buy_list = []
                    sell_list = []
                    if get_market_buy_list and len(get_market_buy_list) > 0:
                        for each_buy in get_market_buy_list:
                            rate = "{:.8f}".format(each_buy['amount_sell'] / (each_buy['amount_get']))
                            amount = "{:.8f}".format(each_buy['amount_sell'])
                            buy_list.append(
                                {
                                    str(each_buy["order_id"]): {
                                        "sell": {
                                            "coin_sell": each_buy['coin_sell'],
                                            "amount_sell": app.db.num_format_coin(each_buy['amount_sell_after_fee']),
                                            "fee_sell": app.db.num_format_coin(each_buy['amount_sell'] - each_buy['amount_sell_after_fee']),
                                            "total": app.db.num_format_coin(each_buy['amount_sell'])
                                        },
                                        "for": {
                                            "coin_get": each_buy['coin_get'],
                                            "amount_get": app.db.num_format_coin(each_buy['amount_get_after_fee']),
                                            "fee_get": app.db.num_format_coin(each_buy['amount_get'] - each_buy['amount_get_after_fee']),
                                            "total": app.db.num_format_coin(each_buy['amount_get'])
                                        }
                                    }
                                }
                            )
                    if get_market_sell_list and len(get_market_sell_list) > 0:
                        for each_sell in get_market_sell_list:
                            rate = "{:.8f}".format(each_sell['amount_sell'] / each_sell['amount_get'])
                            amount = "{:.8f}".format(each_sell['amount_get'])
                            sell_list.append(
                                {
                                    str(each_sell["order_id"]): {
                                        "sell": {
                                            "coin_sell": each_sell['coin_sell'],
                                            "amount_sell": app.db.num_format_coin(each_sell['amount_sell_after_fee']),
                                            "fee_sell": app.db.num_format_coin(each_sell['amount_sell'] - each_sell['amount_sell_after_fee']),
                                            "total": app.db.num_format_coin(each_sell['amount_sell'])},
                                        "for": {
                                            "coin_get": each_sell['coin_get'],
                                            "amount_get": app.db.num_format_coin(each_sell['amount_get_after_fee']),
                                            "fee_get": app.db.num_format_coin(each_sell['amount_get'] - each_sell['amount_get_after_fee']),
                                            "total": app.db.num_format_coin(each_sell['amount_get'])
                                        }
                                    }
                                }
                            )
                    if buy_list or sell_list:
                        market_list[pair_items] = {
                            "buy": buy_list,
                            "sell": sell_list
                        }
    return {
        "success": True,
        "market_list": market_list,
        "time": int(time.time())
    }


@app.get("/markets")
async def show_trading_markets():
    market_list = []
    list_trading_coins = await app.db.get_trading_coinlist()
    enabled_coin = [each['coin_name'] for each in list_trading_coins]
    for each_coin in enabled_coin:
        each_market_coin = await app.db.sql_get_markets_by_coin(each_coin, 'OPEN')
        if each_market_coin and len(each_market_coin) > 0:
            market_list += [
                f"{each_item['coin_sell']}-{each_item['coin_get']}"
                for each_item in each_market_coin
            ]
    return {
        "success": True,
        "market_list": sorted(set(market_list)),
        "time": int(time.time())
    }


@app.get("/ticker/{coin_name}")
async def check_information_by_ticker(coin_name: str):
    list_trading_coins = await app.db.get_trading_coinlist()
    enabled_coin = [each['coin_name'] for each in list_trading_coins]
    coin_name = coin_name.upper()

    if coin_name not in enabled_coin:
        return {
            "error": f"Coin {coin_name.upper()} is not available!",
            "time": int(time.time()),
        }
    get_trade = await app.db.sql_get_coin_trade_stat(coin_name)
    markets = await app.db.sql_get_markets_by_coin(coin_name, 'OPEN')
    market_list = (
        [
            f"{each_item['coin_sell']}-{each_item['coin_get']}"
            for each_item in markets
        ]
        if markets and len(markets) > 0
        else []
    )
    return {
        "success": True,
        "volume_24h": app.db.num_format_coin(get_trade['trade_24h']),
        "volume_7d": app.db.num_format_coin(get_trade['trade_7d']),
        "volume_30d": app.db.num_format_coin(get_trade['trade_30d']),
        "markets": sorted(set(market_list)),
        "time": int(time.time())
    }

@app.get("/coininfo")
async def list_all_coin_information():
    get_all_coins = await app.db.get_all_coin()
    if len(get_all_coins) <= 0:
        return {
            "error": "No data!",
            "time": int(time.time())
        }
    all_coins = []
    for c in get_all_coins:
        type_coin = c['type']
        height = "N/A"
        tip = "✅" if c['enable_tip'] == 1 else "❌"
        deposit = "✅" if c['enable_deposit'] == 1 else "❌"
        withdraw = "✅" if c['enable_withdraw'] == 1 else "❌"
        twitter = "✅" if c['enable_twitter'] == 1 else "❌"
        telegram = "✅" if c['enable_telegram'] == 1 else "❌"
        cexswap = "✅" if c['cexswap_enable'] == 1 else "❌"

        explorer_link = c['explorer_link']
        if explorer_link and explorer_link.startswith("http"):
            explorer_link = f'<a href=\"{explorer_link}\" target=\"_blank\">Link</a>'
        withdraw_info = f"Min. {app.db.num_format_coin(c['real_min_tx'])} / Max. {app.db.num_format_coin(c['real_max_tx'])} {c['coin_name']}"
        tip_info = f"Min. {app.db.num_format_coin(c['real_min_tip'])} / Max. {app.db.num_format_coin(c['real_max_tip'])} {c['coin_name']}"
        net_name = c['net_name']
        coin_name = c['coin_name']
        try:
            if type_coin in ["ERC-20", "TRC-20"]:
                height = app.db.get_cache_kv(
                    "block",
                    f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{net_name}"
                )
            elif type_coin in ["XLM", "NEO", "VITE"]:
                height = app.db.get_cache_kv(
                    "block",
                    f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{type_coin}"
                )
            else:
                height = app.db.get_cache_kv(
                    "block",
                    f"{config['kv_db']['prefix'] + config['kv_db']['daemon_height']}{coin_name}"
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        all_coins.append(
            [c['coin_name'], height, c['deposit_confirm_depth'], tip, deposit, withdraw, twitter, telegram,
                cexswap, tip_info, withdraw_info, explorer_link]
        )
    return {
        "data": all_coins,
        "time": int(time.time())
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=2022)
