#!/usr/bin/env python3
"""
Hourly Crypto Telegram Bot

- Fetches the top N cryptocurrencies by market cap from CoinGecko
- Posts formatted prices to a Telegram channel/group
- Runs once with --once, continuously aligned to the top of the hour, or as a demo (--demo)

Configuration (environment variables or .env file):
  TELEGRAM_BOT_TOKEN   = Telegram bot token from BotFather
  TELEGRAM_CHAT_ID     = Target chat identifier, e.g. -1001234567890 or @channelusername
  CURRENCY             = Fiat currency code for prices (default: usd)
  TOP_N                = Number of top coins to show (default: 10)
  COIN_IDS             = Comma-separated CoinGecko IDs to show (overrides TOP_N), e.g. bitcoin,tether,toncoin,tether-gold
  INCLUDE_MARKET_CAP   = true/false to include market cap in each line (default: false)
  INCLUDE_24H          = true/false to include 24h change (default: true)
  INCLUDE_1H           = true/false to include 1h change (default: true)
  INTERVAL_MINUTES     = Minutes between posts when running continuously (default: 60)

Usage:
  python hourly_crypto_bot.py --once            # Post once and exit
  python hourly_crypto_bot.py --demo            # Post a single demo message with live data
  python hourly_crypto_bot.py                   # Run forever and post every hour (or INTERVAL_MINUTES)

Requirements:
  pip install requests
"""

import os
import sys
import time
import signal
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

import requests


def load_env_from_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a .env file into os.environ if not already set."""
    try:
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"Warning: failed to read .env file: {e}")


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


# ------------------- CRYPTO FETCH WITH FALLBACK -------------------

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


def fetch_coins_fallback(ids: Optional[List[str]] = None, vs_currency: str = "usd", top_n: int = 10) -> List[Dict[str, Any]]:
    BOT_CONTACT = "@patointeressante"

    # Lista de endpoints alternativos
    endpoints = []

    if ids:
        endpoints.append(lambda: get_coins_by_ids(ids, vs_currency=vs_currency))
    else:
        endpoints.append(lambda: get_top_coins(vs_currency=vs_currency, per_page=top_n))

    # CoinPaprika alternativa
    def coinpaprika_fetch():
        url = "https://api.coinpaprika.com/v1/tickers"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        coins = []
        for c in data[:top_n]:
            coins.append({
                "id": c.get("id"),
                "symbol": c.get("symbol"),
                "name": c.get("name"),
                "current_price": c.get("quotes", {}).get(vs_currency.upper(), {}).get("price"),
                "price_change_percentage_1h_in_currency": None,
                "price_change_percentage_24h_in_currency": c.get("quotes", {}).get(vs_currency.upper(), {}).get("percent_change_24h"),
                "market_cap": c.get("quotes", {}).get(vs_currency.upper(), {}).get("market_cap")
            })
        return coins
    endpoints.append(coinpaprika_fetch)

    # Nomics alternativa
    def nomics_fetch():
        api_key = "demo-1"
        url = f"https://api.nomics.com/v1/currencies/ticker?key={api_key}&per-page={top_n}&convert={vs_currency.upper()}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        coins = []
        for c in data:
            coins.append({
                "id": c.get("id"),
                "symbol": c.get("symbol"),
                "name": c.get("name"),
                "current_price": float(c.get("price", 0)),
                "price_change_percentage_1h_in_currency": None,
                "price_change_percentage_24h_in_currency": float(c.get("1d", {}).get("price_change_pct", 0)) * 100,
                "market_cap": float(c.get("market_cap", 0))
            })
        return coins
    endpoints.append(nomics_fetch)

    last_error = None
    for fetcher in endpoints:
        try:
            coins = fetcher()
            if coins:
                return coins
        except Exception as e:
            last_error = e
            continue

    # Se nenhuma API funcionar, envia mensagem de erro
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            send_telegram_message(token, chat_id, f"🚨 Nenhuma API de criptomoeda está funcionando no momento. Contate {BOT_CONTACT} no Telegram.")
        except Exception:
            pass
    raise RuntimeError(f"All crypto APIs failed: {last_error}")


# ------------------- MESSAGE BUILDING -------------------

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


# ------------------- TELEGRAM -------------------

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


# ------------------- MAIN BOT LOGIC -------------------

def post_once() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set (env or .env).")
        sys.exit(1)

    vs = os.getenv("CURRENCY", "usd")
    coin_ids_env = os.getenv("COIN_IDS")
    top_n = get_int_env("TOP_N", 10)
    include_mcap = get_bool_env("INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_env("INCLUDE_24H", True)
    include_1h = get_bool_env("INCLUDE_1H", True)

    try:
        if coin_ids_env:
            ids = [x.strip() for x in coin_ids_env.split(",") if x.strip()]
            coins = fetch_coins_fallback(ids=ids, vs_currency=vs, top_n=top_n)
        else:
            coins = fetch_coins_fallback(ids=None, vs_currency=vs, top_n=top_n)
        message = build_message(coins, vs=vs, include_1h=include_1h, include_24h=include_24h, include_mcap=include_mcap)
        send_telegram_message(token, chat_id, message)
        print(f"Posted {len(coins)} coins to Telegram chat {chat_id}.")
    except Exception as e:
        print(f"Error fetching or sending coins: {e}")


def demo_message() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set (env or .env).")
        sys.exit(1)

    vs = os.getenv("CURRENCY", "usd")
    coin_ids_env = os.getenv("COIN_IDS")
    top_n = get_int_env("TOP_N", 10)
    include_mcap = get_bool_env("INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_env("INCLUDE_24H", True)
    include_1h = get_bool_env("INCLUDE_1H", True)

    try:
        if coin_ids_env:
            ids = [x.strip() for x in coin_ids_env.split(",") if x.strip()]
            coins = fetch_coins_fallback(ids=ids, vs_currency=vs, top_n=top_n)
        else:
            coins = fetch_coins_fallback(ids=None, vs_currency=vs, top_n=top_n)
        message = build_message(coins, vs=vs, include_1h=include_1h, include_24h=include_24h, include_mcap=include_mcap)
        send_telegram_message(token, chat_id, message)
        print(f"Demo message sent to Telegram chat {chat_id}.")
    except Exception as e:
        print(f"Error fetching or sending coins: {e}")


def seconds_until_next_boundary(now: Optional[datetime], minutes: int) -> float:
    if now is None:
        now = datetime.now(timezone.utc)
    minute = (now.minute // minutes + 1) * minutes
    next_time = now.replace(second=0, microsecond=0)
    if minute >= 60:
        next_time = (next_time + timedelta(hours=1)).replace(minute=0)
    else:
        next_time = next_time.replace(minute=minute)
    delta = (next_time - now).total_seconds()
    return max(1.0, delta)


def run_forever() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set (env or .env).")
        sys.exit(1)

    vs = os.getenv("CURRENCY", "usd")
    coin_ids_env = os.getenv("COIN_IDS")
    top_n = get_int_env("TOP_N", 10)
    include_mcap = get_bool_env("INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_env("INCLUDE_24H", True)
    include_1h = get_bool_env("INCLUDE_1H", True)
    interval = max(1, get_int_env("INTERVAL_MINUTES", 60))

    stop = {"flag": False}

    def handle_sig(signum, frame):
        stop["flag"] = True
        print("Received signal, shutting down...")

    try:
        signal.signal(signal.SIGINT, handle_sig)
        signal.signal(signal.SIGTERM, handle_sig)
    except Exception:
        pass

    wait = seconds_until_next_boundary(datetime.now(timezone.utc), interval)
    print(f"Waiting {int(wait)}s until next {interval}-minute boundary (UTC) ...")
    time.sleep(wait)

    while not stop["flag"]:
        try:
            if coin_ids_env:
                ids = [x.strip() for x in coin_ids_env.split(",") if x.strip()]
                coins = fetch_coins_fallback(ids=ids, vs_currency=vs, top_n=top_n)
            else:
                coins = fetch_coins_fallback(ids=None, vs_currency=vs, top_n=top_n)
            message = build_message(
                coins, vs=vs, include_1h=include_1h, include_24h=include_24h, include_mcap=include_mcap
            )
            send_telegram_message(token, chat_id, message)
            print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] Posted to {chat_id}")
        except Exception as e:
            print(f"Error during post: {e}")
        now = datetime.now(timezone.utc)
        q = ((now.minute // interval) + 1) * interval
        next_time = now.replace(second=0, microsecond=0)
        if q >= 60:
            next_time = (next_time + timedelta(hours=1)).replace(minute=0)
        else:
            next_time = next_time.replace(minute=q)
        delay = (next_time - now).total_seconds()
        if delay < 1:
            delay = interval * 60
        slept = 0.0
        while slept < delay and not stop["flag"]:
            step = min(5.0, delay - slept)
            time.sleep(step)
            slept += step


def main(argv: List[str]) -> None:
    load_env_from_dotenv()
    args = set(a.lower() for a in argv[1:])
    if "--once" in args or "-1" in args:
        post_once()
    elif "--demo" in args:
        demo_message()
    else:
        run_forever()


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass