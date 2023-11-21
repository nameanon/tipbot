import argparse
import asyncio
import datetime
import json
import sys
import time
import traceback
from typing import Any, List

import aiohttp
import uvicorn
from cachetools import TTLCache
from fastapi import FastAPI
from mnemonic import Mnemonic
from pydantic import BaseModel
from pytezos import pytezos
from pytezos.crypto.encoding import is_address
from pytezos.crypto.key import Key

from config import load_config

config = load_config()
parser = argparse.ArgumentParser()
bind_port = config["api_helper"]["port_tezos"]

try:
    parser.add_argument("--port", dest="port", type=int, help="Set port (Ex. 7001)")
    args = parser.parse_args()
    if args and args.port and type(args.port) == int and 1024 < args.port < 60000:
        bind_port = int(args.port)
except Exception:
    traceback.print_exc(file=sys.stdout)

app = FastAPI(title="TipBotv2 FastAPI Tezos", version="0.1", docs_url="/dokument")
app.config = config
app.pending_cache_balance = TTLCache(maxsize=20000, ttl=5.0)


class Address(BaseModel):
    addr: str


class BalanceTzData(BaseModel):
    endpoint: str
    key: str


class BalanceTzToken(BaseModel):
    endpoint: str
    token_contract: str
    token_id: int
    address: List
    timeout: int = 60


class BalanceTzTokenData(BaseModel):
    endpoint: str
    address: str
    timeout: int = 60


class VerifyAsset(BaseModel):
    endpoint: str
    asset_name: str
    issuer: str
    address: str


class RevealAddress(BaseModel):
    endpoint: str
    key: str


class CheckRevealAddress(BaseModel):
    endpoint: str
    address: str


class EndpointData(BaseModel):
    endpoint: str
    timeout: int = 30


class TxData(BaseModel):
    endpoint: str
    txhash: str
    timeout: int = 30


class SendTxData(BaseModel):
    endpoint: str
    key: str
    to_address: str
    atomic_amount: int


class SendTxDataToken(BaseModel):
    endpoint: str
    key: str
    to_address: str
    atomic_amount: int
    contract: Any
    token_id: Any


@app.post("/validate_address")
async def validate_address(item: Address):
    try:
        valid = is_address(item.addr)
        return {
            "address": item.addr,
            "success": True,
            "valid": valid,
            "timestamp": int(time.time()),
        }
    except AttributeError:
        pass
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "address": item.addr,
        "success": True,
        "valid": False,
        "timestamp": int(time.time()),
    }


@app.post("/check_reveal_address")
async def check_reveal_address(item: CheckRevealAddress):
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{item.endpoint}accounts/{item.address}", headers=headers, timeout=30
            ) as response:
                json_resp = await response.json()
                if (
                    json_resp["type"] == "user"
                    and "revealed" in json_resp
                    and json_resp["revealed"] is True
                ):
                    if response.status in [200, 201]:
                        return {"result": True, "timestamp": int(time.time())}
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {"result": False, "timestamp": int(time.time())}


@app.post("/reveal_address")
async def reveal_address(item: RevealAddress):
    try:
        user_address = pytezos.using(shell=item.endpoint, key=item.key)
        tx = user_address.reveal().autofill().sign().inject()
        print(f"XTZ revealed new tx {tx}")
        return {"success": True, "hash": tx, "timestamp": int(time.time())}
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {"error": "Reveal address failed!", "timestamp": int(time.time())}


@app.post("/get_head")
async def get_head(item: EndpointData):
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{item.endpoint}head/", headers=headers, timeout=item.timeout
            ) as response:
                json_resp = await response.json()
                if "synced" in json_resp and json_resp["synced"] is True:
                    if response.status in [200, 201]:
                        return {
                            "success": True,
                            "result": json_resp,
                            "timestamp": int(time.time()),
                        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {"error": "Get head failed!", "timestamp": int(time.time())}


@app.post("/get_tx")
async def get_tx(item: TxData):
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{item.endpoint}operations/transactions/{item.txhash}",
                headers=headers,
                timeout=item.timeout,
            ) as response:
                json_resp = await response.json()
                if (
                    len(json_resp) == 1
                    and "status" in json_resp[0]
                    and "level" in json_resp[0]
                ):
                    if response.status in [200, 201]:
                        return {
                            "success": True,
                            "result": json_resp[0],
                            "timestamp": int(time.time()),
                        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": f"Get tx {item.txhash} failed!",
        "timestamp": int(time.time()),
    }


@app.post("/send_tezos")
async def send_tezos(item: SendTxData):
    try:
        user_address = pytezos.using(shell=item.endpoint, key=item.key)
        tx = user_address.transaction(
            source=user_address.key.public_key_hash(),
            destination=item.to_address,
            amount=item.atomic_amount,
        ).send()
        return {
            "success": True,
            "hash": tx.hash(),
            "contents": json.dumps(tx.contents),
            "timestamp": int(time.time()),
        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {"error": "Send tezos failed!", "timestamp": int(time.time())}


@app.post("/send_tezos_token_fa2")
async def send_tezos_token(item: SendTxDataToken):
    try:
        token = pytezos.using(shell=item.endpoint, key=item.key).contract(item.contract)
        acc = pytezos.using(shell=item.endpoint, key=item.key)
        tx_token = token.transfer(
            [
                dict(
                    from_=acc.key.public_key_hash(),
                    txs=[
                        dict(
                            to_=item.to_address,
                            amount=item.atomic_amount,
                            token_id=int(item.token_id),
                        )
                    ],
                )
            ]
        ).send()
        return {
            "success": True,
            "hash": tx_token.hash(),
            "contents": json.dumps(tx_token.contents),
            "timestamp": int(time.time()),
        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
        print(
            f"[XTZ 2.0] failed to transfer url: {item.endpoint}, contract {item.contract} moving {acc.key.public_key_hash()} to {item.to_address}"
        )
    return {"error": "Send tezos failed!", "timestamp": int(time.time())}


@app.post("/send_tezos_token_fa12")
async def send_tezos_token_fa12(item: SendTxDataToken):
    try:
        token = pytezos.using(shell=item.endpoint, key=item.key).contract(item.contract)
        acc = pytezos.using(shell=item.endpoint, key=item.key)
        tx_token = token.transfer(
            **{
                "from": acc.key.public_key_hash(),
                "to": item.to_address,
                "value": item.atomic_amount,
            }
        ).inject()
        return {
            "success": True,
            "hash": tx_token["hash"],
            "contents": json.dumps(tx_token["contents"]),
            "timestamp": int(time.time()),
        }
    except Exception:
        traceback.print_exc(file=sys.stdout)
        print(
            f"[XTZ 1.2] failed to transfer url: {item.endpoint}, contract {item.contract} moving {acc.key.public_key_hash()} to {item.to_address}"
        )
    return {"error": "Send tezos failed!", "timestamp": int(time.time())}


@app.post("/get_address_token_balances")
async def get_address_token_balances(item: BalanceTzToken):
    try:
        token = pytezos.using(shell=item.endpoint).contract(item.token_contract)
        addresses = [
            {"owner": each_address, "token_id": item.token_id}
            for each_address in item.address
        ]
        if token_balance := token.balance_of(requests=addresses, callback=None).view():
            result_balance = {
                each["request"]["owner"]: int(each["balance"]) for each in token_balance
            }
            return {
                "success": True,
                "result": result_balance,  # dict of address => balance in float
                "timestamp": int(time.time()),
            }
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {}


@app.post("/get_balances_token_tezos")
async def get_balance_token_tezos(item: BalanceTzTokenData):
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{item.endpoint}tokens/balances?account={item.address}",
                headers=headers,
                timeout=item.timeout,
            ) as response:
                json_resp = await response.json()
                if response.status in [200, 201]:
                    return {
                        "success": True,
                        "result": json_resp,
                        "timestamp": int(time.time()),
                    }
                else:
                    print(f"tezos_check_token_balances: return {response.status}")
    except asyncio.exceptions.TimeoutError:
        print(
            f"Tezos check balances timeout for url: {item.endpoint} / addr: {item.address}. Time: {item.timeout}"
        )
    except Exception:
        traceback.print_exc(file=sys.stdout)
    return {
        "error": f"Error trying to get balance from endpoint for token address {item.address}.",
        "timestamp": int(time.time()),
    }


@app.post("/get_balance_tezos")
async def get_balance_tezos(item: BalanceTzData):
    if app.pending_cache_balance.get(item.key):
        return app.pending_cache_balance[item.key]
    try:
        client = pytezos.using(shell=item.endpoint, key=item.key)
        if client is None:
            return {
                "error": "Error trying to get balance from endpoint.",
                "timestamp": int(time.time()),
            }
        result = {
            "success": True,
            "result": {"balance": float(client.balance())},
            "timestamp": int(time.time()),
        }
        app.pending_cache_balance[item.key] = result
        return result
    except Exception:
        traceback.print_exc(file=sys.stdout)


@app.get("/create_address")
async def create_address():
    mnemo = Mnemonic("english")
    words = str(mnemo.generate(strength=128))
    key = Key.from_mnemonic(mnemonic=words, passphrase="", email="")
    print(
        f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} create a new address: {key.public_key_hash()}'
    )
    return {
        "success": True,
        "address": key.public_key_hash(),
        "seed": words,
        "secret_key_hex": key.secret_key(),
        "dump": {
            "address": key.public_key_hash(),
            "seed": words,
            "key": key.secret_key(),
        },
        "timestamp": int(time.time()),
    }


if __name__ == "__main__":
    print(
        f"""{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} running with IP: {config['api_helper']['bind_ip']} and port {bind_port}"""
    )
    uvicorn.run(
        app,
        host=config["api_helper"]["bind_ip"],
        headers=[("server", "TipBot v2")],
        port=bind_port,
        access_log=False,
    )
