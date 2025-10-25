#!/usr/bin/env python3
"""
Hourly Crypto Telegram Bot (with API fallbacks + Groq summary + Debugging)

- Fetches crypto prices from CoinGecko, CoinPaprika, CoinCap, or CryptoCompare.
- Posts formatted prices to a Telegram chat/channel.
- Has modes: --once, --demo, or continuous posting every INTERVAL_MINUTES.
- Adds a fun Groq AI summary under the crypto list.
- Includes detailed debug logging to console.

Credit footer:
  *Pricing by t.me/hourlycrypto • Prices computed from [API_NAME]*

Requirements:
  pip install requests groq
"""

import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import requests

from groq import get_groq_summary


# ========== Utility ==========
def log(msg: str) -> None:
    """Print timestamped debug message."""
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def load_env_from_dotenv(path: str = ".env") -> None:
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
        log("✅ .env loaded successfully.")
    except Exception as e:
        log(f"⚠️ Failed to read .env: {e}")


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


# ========== Formatting ==========
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
    emoji = "💚" if p > 0 else "❤️" if p < 0 else "➡️"
    sign = "+" if p > 0 else ""
    try:
        return f"{sign}{p:.2f}%{emoji}"
    except Exception:
        return f"{p}%{emoji}"


# ========== Data Fetchers ==========
def get_from_coingecko(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": max(1, min(top_n, 250)),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h",
        "locale": "en",
    }
    if ids:
        params["ids"] = ",".join(ids)
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    log(f"✅ CoinGecko returned {len(r.json())} coins.")
    return r.json(), "CoinGecko"


def get_from_coinpaprika(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinPaprika...")
    url = "https://api.coinpaprika.com/v1/tickers"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    if ids:
        data = [x for x in data if x["id"] in ids]
    else:
        data = sorted(data, key=lambda x: x.get("rank", 9999))[:top_n]
    converted = []
    for c in data:
        converted.append({
            "id": c["id"],
            "symbol": c["symbol"],
            "name": c["name"],
            "current_price": c["quotes"].get(vs_currency.upper(), {}).get("price"),
            "market_cap": c["quotes"].get(vs_currency.upper(), {}).get("market_cap"),
            "price_change_percentage_1h_in_currency": c["quotes"].get(vs_currency.upper(), {}).get("percent_change_1h"),
            "price_change_percentage_24h_in_currency": c["quotes"].get(vs_currency.upper(), {}).get("percent_change_24h"),
        })
    log(f"✅ CoinPaprika returned {len(converted)} coins.")
    return converted, "CoinPaprika"


def get_from_coincap(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinCap...")
    url = "https://api.coincap.io/v2/assets"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()["data"]
    if ids:
        data = [x for x in data if x["id"] in ids]
    else:
        data = data[:top_n]
    converted = []
    for c in data:
        converted.append({
            "id": c["id"],
            "symbol": c["symbol"],
            "name": c["name"],
            "current_price": float(c["priceUsd"]),
            "market_cap": float(c["marketCapUsd"]),
            "price_change_percentage_1h_in_currency": float(c.get("changePercent24Hr", 0)) / 24,
            "price_change_percentage_24h_in_currency": float(c.get("changePercent24Hr", 0)),
        })
    log(f"✅ CoinCap returned {len(converted)} coins.")
    return converted, "CoinCap"


def get_from_cryptocompare(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/top/mktcapfull"
    params = {"limit": top_n, "tsym": vs_currency.upper()}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json().get("Data", [])
    converted = []
    for c in data:
        info = c["CoinInfo"]
        raw = c.get("RAW", {}).get(vs_currency.upper(), {})
        converted.append({
            "id": info["Name"].lower(),
            "symbol": info["Name"],
            "name": info["FullName"],
            "current_price": raw.get("PRICE"),
            "market_cap": raw.get("MKTCAP"),
            "price_change_percentage_1h_in_currency": raw.get("CHANGEPCTHOUR"),
            "price_change_percentage_24h_in_currency": raw.get("CHANGEPCTDAY"),
        })
    log(f"✅ CryptoCompare returned {len(converted)} coins.")
    return converted, "CryptoCompare"


def get_crypto_data(vs_currency: str, ids: Optional[List[str]], top_n: int):
    sources = [get_from_coingecko, get_from_coinpaprika, get_from_coincap, get_from_cryptocompare]
    for fetcher in sources:
        try:
            return fetcher(vs_currency, ids, top_n)
        except Exception as e:
            log(f"⚠️ {fetcher.__name__} failed: {e}")
    log("❌ All API sources failed! Contact @patointeressante on Telegram.")
    sys.exit(1)


# ========== Telegram ==========
def get_fear_and_greed_index():
    log("🔄 Fetching Fear & Greed Index from alternative.me...")
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()["data"][0]
        log("✅ Fear & Greed Index fetched successfully.")
        return {
            "value": data["value"],
            "classification": data["value_classification"],
        }
    except Exception as e:
        log(f"⚠️ Could not fetch Fear & Greed Index: {e}")
        return None


def get_global_metrics(vs_currency: str):
    log("🔄 Fetching global metrics from CoinGecko...")
    url = "https://api.coingecko.com/api/v3/global"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()["data"]
        log("✅ Global metrics fetched successfully.")
        return {
            "btc_dominance": data["market_cap_percentage"].get("btc"),
            "eth_dominance": data["market_cap_percentage"].get("eth"),
            "total_market_cap": data["total_market_cap"].get(vs_currency.lower()),
            "market_cap_change_24h": data["market_cap_change_percentage_24h_usd"],
        }
    except Exception as e:
        log(f"⚠️ Could not fetch global metrics: {e}")
        return None


def send_telegram_message(token: str, chat_id: str, text: str) -> Dict[str, Any]:
    log("📤 Sending message to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20)
    try:
        data = r.json()
    except Exception:
        r.raise_for_status()
        data = {"ok": True}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    log("✅ Telegram message sent successfully.")
    return data


# ========== Message Builder ==========
def build_message(coins: list[dict], vs: str, api_name: str) -> str:
    lines = ["💲 <b>CoinMarketCap</b>:", "-------------------------"]

    for c in coins:
        try:
            name = c.get("name", "?")
            symbol = c.get("symbol", "?").upper()
            price = c.get("current_price")
            p24h = c.get("price_change_percentage_24h_in_currency")

            lines.append(f"<b>{name} #{symbol}</b>: ${format_price(price)}")
            lines.append(f"Last 24 hours: {fmt_pct(p24h)}")
            lines.append("-------------------------")
        except Exception as e:
            log(f"⚠️ Error formatting {c.get('symbol')}: {e}")

    # Global Metrics
    global_metrics = get_global_metrics(vs)
    if global_metrics:
        lines.append("<b>Global Metrics:</b>")
        lines.append(f"BTC dominance: {global_metrics.get('btc_dominance'):.2f}%")
        lines.append(f"ETH dominance: {global_metrics.get('eth_dominance'):.2f}%")

        mcap_total = global_metrics.get('total_market_cap')
        mcap_change = global_metrics.get('market_cap_change_24h')

        if mcap_total is not None and mcap_change is not None:
            formatted_mcap = f"${mcap_total / 1_000_000_000_000:.2f}T"
            lines.append(f"Market Cap: {formatted_mcap} {fmt_pct(mcap_change)}")

        fng = get_fear_and_greed_index()
        if fng:
            lines.append(f"Fear & Greed: {fng['value']}/100 {fng['classification']}")
        lines.append("-------------------------")

    # Add Groq AI summary
    try:
        summary = get_groq_summary(coins, vs)
        if summary:
            lines.append(summary)
            log("💬 Added Groq AI summary.")
    except Exception as e:
        log(f"⚠️ Groq summary failed: {e}")

    # Footer
    lines.append(f"\n<i>Pricing by <b>t.me/hourlycrypto</b> • Prices computed from {api_name}.</i>")
    return "\n".join(lines)


# ========== Posting Logic ==========
def post_once() -> None:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        sys.exit(1)
    vs = os.getenv("CURRENCY", "usd")
    ids = [x.strip() for x in os.getenv("COIN_IDS", "").split(",") if x.strip()]
    top_n = get_int_env("TOP_N", 10)

    log(f"🚀 Fetching crypto data (vs={vs}, top_n={top_n})...")
    coins, api_name = get_crypto_data(vs, ids or None, top_n)
    msg = build_message(coins, vs, api_name)
    send_telegram_message(token, chat_id, msg)
    log(f"✅ Posted {len(coins)} coins using {api_name}.\n")


# ========== Main ==========
def main(argv: List[str]) -> None:
    load_env_from_dotenv()
    args = set(a.lower() for a in argv[1:])
    interval = get_int_env("INTERVAL_MINUTES", 60)

    if "--once" in args or "-1" in args:
        post_once()
    elif "--demo" in args:
        post_once()
    else:
        log(f"⏳ Running continuously every {interval} minutes.")
        while True:
            try:
                post_once()
            except Exception as e:
                log(f"⚠️ Error during post_once: {e}")
            time.sleep(interval * 60)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        log("🛑 Bot stopped manually.")
