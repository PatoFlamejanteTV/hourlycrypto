"""
Vercel Serverless Function for Hourly Crypto Bot
This function is triggered by Vercel Cron Jobs to post crypto prices to Telegram.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import requests


def get_bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except Exception:
        return default


def format_price(v: Optional[float]) -> str:
    if v is None:
        return "?"
    try:
        if v >= 1000:
            return f"{v:,.0f}"
        if v >= 1:
            return f"{v:,.2f}"
        if v >= 0.01:
            return f"{v:,.4f}"
        return f"{v:,.6f}"
    except Exception:
        return str(v)


def fmt_pct(p: Optional[float]) -> str:
    if p is None:
        return "?%"
    arrow = "" if p == 0 else ("▲" if p > 0 else "▼")
    sign = "+" if p and p > 0 else ""
    try:
        return f"{arrow}{sign}{p:.2f}%"
    except Exception:
        return f"{arrow}{p}%"


def get_top_coins(vs_currency: str = "usd", per_page: int = 10) -> List[Dict[str, Any]]:
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": max(1, min(per_page, 250)),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h",
        "locale": "en",
    }
    headers = {"Accept": "application/json"}
    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response from CoinGecko")
    return data


def get_coins_by_ids(ids: List[str], vs_currency: str = "usd") -> List[Dict[str, Any]]:
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "ids": ",".join(ids),
        "order": "market_cap_desc",
        "per_page": max(1, min(len(ids), 250)),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h",
        "locale": "en",
    }
    headers = {"Accept": "application/json"}
    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response from CoinGecko")
    by_id = {c.get("id"): c for c in data if isinstance(c, dict)}
    ordered = [by_id[i] for i in ids if i in by_id]
    return ordered


def build_message(
    coins: List[Dict[str, Any]],
    vs: str,
    include_1h: bool = True,
    include_24h: bool = True,
    include_mcap: bool = False,
) -> str:
    now_utc = datetime.now(timezone.utc)
    header = f"Crypto Prices ({vs.upper()}) — {now_utc:%Y-%m-%d %H:%M} UTC\n"
    lines = [header]

    for c in coins:
        try:
            symbol = (c.get("symbol") or "").upper()
            name = c.get("name") or symbol
            price = c.get("current_price")
            p1h = c.get("price_change_percentage_1h_in_currency")
            p24h = c.get("price_change_percentage_24h_in_currency")
            mcap = c.get("market_cap")

            parts = [f"{symbol} ${format_price(price)}"]
            changes = []
            if include_1h:
                changes.append(f"1h: {fmt_pct(p1h)}")
            if include_24h:
                changes.append(f"24h: {fmt_pct(p24h)}")
            if changes:
                parts.append(" | ".join(changes))
            if include_mcap and mcap is not None:
                parts.append(f"MC: ${format_price(mcap)}")

            lines.append(" ".join(parts))
        except Exception:
            lines.append(f"{c.get('symbol','?').upper()} ${format_price(c.get('current_price'))}")

    return "\n".join(lines)


def send_telegram_message(token: str, chat_id: str, text: str) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=20)
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        data = {"ok": True}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data


def handler(request, context=None):
    """
    Vercel serverless function handler.
    This is triggered by Vercel Cron Jobs.
    """
    try:
        # Get configuration from environment variables
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not token or not chat_id:
            return {
                "statusCode": 500,
                "body": "Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in Vercel environment variables"
            }

        vs = os.getenv("CURRENCY", "usd")
        coin_ids_env = os.getenv("COIN_IDS")
        top_n = get_int_env("TOP_N", 10)
        include_mcap = get_bool_env("INCLUDE_MARKET_CAP", False)
        include_24h = get_bool_env("INCLUDE_24H", True)
        include_1h = get_bool_env("INCLUDE_1H", True)

        # Fetch coin data
        if coin_ids_env:
            ids = [x.strip() for x in coin_ids_env.split(",") if x.strip()]
            coins = get_coins_by_ids(ids, vs_currency=vs)
        else:
            coins = get_top_coins(vs_currency=vs, per_page=top_n)

        # Build and send message
        message = build_message(
            coins, 
            vs=vs, 
            include_1h=include_1h, 
            include_24h=include_24h, 
            include_mcap=include_mcap
        )
        send_telegram_message(token, chat_id, message)

        return {
            "statusCode": 200,
            "body": f"Successfully posted {len(coins)} coins to Telegram chat {chat_id}"
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }