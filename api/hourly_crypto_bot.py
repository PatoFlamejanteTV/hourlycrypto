import os
import sys
import json
import requests
from datetime import datetime
from typing import List

# --- Environment ---
def load_env_from_vercel() -> None:
    """Load env vars from Vercel Environment."""
    # On Vercel, os.environ already has all vars
    required = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise Exception(f"Missing environment variables: {', '.join(missing)}")


# --- Fetch Crypto Data ---
def get_top_coins(vs_currency="usd", per_page=10):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": vs_currency, "order": "market_cap_desc", "per_page": per_page, "page": 1}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


# --- Format Telegram Message ---
def build_message(coins, vs="usd", include_1h=True, include_24h=True, include_mcap=False):
    lines = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"💰 **Crypto Market Update** — {now}\n")

    for coin in coins:
        price = coin["current_price"]
        symbol = coin["symbol"].upper()
        line = f"{coin['name']} ({symbol}) ${price:,.2f}"
        if include_1h and "price_change_percentage_1h_in_currency" in coin:
            pct = coin["price_change_percentage_1h_in_currency"]
            arrow = "▲" if pct > 0 else "▼"
            line += f" | 1h: {arrow}{pct:.2f}%"
        if include_24h and "price_change_percentage_24h_in_currency" in coin:
            pct = coin["price_change_percentage_24h_in_currency"]
            arrow = "▲" if pct > 0 else "▼"
            line += f" | 24h: {arrow}{pct:.2f}%"
        if include_mcap:
            line += f" | MC: ${coin['market_cap'] / 1e9:.2f}B"
        lines.append(line)

    return "\n".join(lines)


# --- Telegram Send ---
def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    r.raise_for_status()
    return r.json()


# --- Handler (Vercel entrypoint) ---
def handler(request):
    load_env_from_vercel()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    vs = os.getenv("CURRENCY", "usd")
    top_n = int(os.getenv("TOP_N", 10))
    include_mcap = os.getenv("INCLUDE_MARKET_CAP", "false").lower() == "true"
    include_1h = os.getenv("INCLUDE_1H", "true").lower() == "true"
    include_24h = os.getenv("INCLUDE_24H", "true").lower() == "true"

    coins = get_top_coins(vs_currency=vs, per_page=top_n)
    message = build_message(coins, vs=vs, include_1h=include_1h, include_24h=include_24h, include_mcap=include_mcap)
    send_telegram_message(token, chat_id, message)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"ok": True, "message": "Posted crypto update successfully"}),
    }
