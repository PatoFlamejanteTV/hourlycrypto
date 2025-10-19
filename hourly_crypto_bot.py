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
from dataclasses import dataclass
import requests

from groq import get_groq_summary

from proxy_selector import get_fastest_proxy
import requests

fast_proxy = get_fastest_proxy()

if fast_proxy:
    proxies = {"http": f"http://{fast_proxy}", "https": f"http://{fast_proxy}"}
else:
    proxies = None

# ========== Data Classes ==========
@dataclass
class Coin:
    """Standardized cryptocurrency data model."""
    id: str
    symbol: str
    name: str
    price: Optional[float]
    p1h: Optional[float]
    p24h: Optional[float]
    mcap: Optional[float]

# ========== Utility ==========
def log(msg: str) -> None:
    """Print timestamped debug message."""
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


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
        return "?"
    emoji = "💚" if p > 0 else "❤️" if p < 0 else "🤍"
    sign = "+" if p > 0 else ""
    try:
        return f"{emoji} {sign}{p:.2f}%"
    except Exception:
        return f"{emoji} {p}%"


# ========== Data Fetchers ==========
def _transform_coingecko(raw_coins: List[Dict[str, Any]]) -> List[Coin]:
    return [Coin(
        id=c.get("id"),
        symbol=c.get("symbol"),
        name=c.get("name"),
        price=c.get("current_price"),
        p1h=c.get("price_change_percentage_1h_in_currency"),
        p24h=c.get("price_change_percentage_24h_in_currency"),
        mcap=c.get("market_cap")
    ) for c in raw_coins]

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
    data = r.json()
    log(f"✅ CoinGecko returned {len(data)} coins.")
    return _transform_coingecko(data), "CoinGecko"

def _transform_coinpaprika(raw_coins: List[Dict[str, Any]], vs_currency: str, ids: Optional[List[str]], top_n: int) -> List[Coin]:
    if ids:
        raw_coins = [x for x in raw_coins if x.get("id") in ids]
    else:
        raw_coins = sorted(raw_coins, key=lambda x: x.get("rank", 9999))[:top_n]
    return [Coin(
        id=c.get("id"),
        symbol=c.get("symbol"),
        name=c.get("name"),
        price=c.get("quotes", {}).get(vs_currency.upper(), {}).get("price"),
        p1h=c.get("quotes", {}).get(vs_currency.upper(), {}).get("percent_change_1h"),
        p24h=c.get("quotes", {}).get(vs_currency.upper(), {}).get("percent_change_24h"),
        mcap=c.get("quotes", {}).get(vs_currency.upper(), {}).get("market_cap")
    ) for c in raw_coins]

def get_from_coinpaprika(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinPaprika...")
    url = "https://api.coinpaprika.com/v1/tickers"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    transformed = _transform_coinpaprika(data, vs_currency, ids, top_n)
    log(f"✅ CoinPaprika returned {len(transformed)} coins.")
    return transformed, "CoinPaprika"

def _transform_coincap(raw_coins: List[Dict[str, Any]], ids: Optional[List[str]], top_n: int) -> List[Coin]:
    if ids:
        raw_coins = [x for x in raw_coins if x.get("id") in ids]
    else:
        raw_coins = raw_coins[:top_n]
    return [Coin(
        id=c.get("id"),
        symbol=c.get("symbol"),
        name=c.get("name"),
        price=float(c["priceUsd"]) if c.get("priceUsd") is not None else None,
        p1h=(float(c["changePercent24Hr"]) / 24) if c.get("changePercent24Hr") is not None else None,
        p24h=float(c["changePercent24Hr"]) if c.get("changePercent24Hr") is not None else None,
        mcap=float(c["marketCapUsd"]) if c.get("marketCapUsd") is not None else None
    ) for c in raw_coins]

def get_from_coincap(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinCap...")
    url = "https://api.coincap.io/v2/assets"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json().get("data", [])
    transformed = _transform_coincap(data, ids, top_n)
    log(f"✅ CoinCap returned {len(transformed)} coins.")
    return transformed, "CoinCap"

def _transform_cryptocompare(raw_coins: List[Dict[str, Any]], vs_currency: str) -> List[Coin]:
    coins = []
    for c in raw_coins:
        info = c.get("CoinInfo", {})
        raw = c.get("RAW", {}).get(vs_currency.upper(), {})
        coins.append(Coin(
            id=info.get("Name", "").lower(),
            symbol=info.get("Name"),
            name=info.get("FullName"),
            price=raw.get("PRICE"),
            p1h=raw.get("CHANGEPCTHOUR"),
            p24h=raw.get("CHANGEPCTDAY"),
            mcap=raw.get("MKTCAP")
        ))
    return coins

def get_from_cryptocompare(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/top/mktcapfull"
    params = {"limit": top_n, "tsym": vs_currency.upper()}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json().get("Data", [])
    transformed = _transform_cryptocompare(data, vs_currency)
    log(f"✅ CryptoCompare returned {len(transformed)} coins.")
    return transformed, "CryptoCompare"


def get_crypto_data(vs_currency: str, ids: Optional[List[str]], top_n: int):
    sources = [get_from_coingecko, get_from_coinpaprika, get_from_coincap, get_from_cryptocompare]
    for fetcher in sources:
        try:
            return fetcher(vs_currency, ids, top_n)
        except Exception as e:
            log(f"⚠️ {fetcher.__name__} failed: {e}")
    log("❌ All coin API sources failed!")
    return [], "Unknown"

def get_global_metrics():
    """Fetches global market data from CoinGecko."""
    try:
        log("🔄 Fetching global metrics from CoinGecko...")
        url = "https://api.coingecko.com/api/v3/global"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        metrics = r.json().get("data", {})
        log("✅ Global metrics fetched successfully.")
        return metrics
    except Exception as e:
        log(f"⚠️ Could not fetch global metrics: {e}")
        return {}

def get_fear_greed_index():
    """Fetches Fear & Greed Index from alternative.me."""
    try:
        log("🔄 Fetching Fear & Greed Index...")
        url = "https://api.alternative.me/fng/?limit=1"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        index_data = r.json().get("data", [])[0]
        log("✅ Fear & Greed Index fetched successfully.")
        return index_data
    except Exception as e:
        log(f"⚠️ Could not fetch Fear & Greed Index: {e}")
        return {}


# ========== Telegram ==========
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
def build_message(
    coins: List[Coin],
    global_metrics: Dict[str, Any],
    fear_greed_index: Dict[str, Any],
    vs: str,
    api_name: str,
    include_1h: bool = True,
    include_24h: bool = True,
    include_mcap: bool = False
) -> str:
    now_utc = datetime.now(timezone.utc)

    # Header
    header = f"<b><u>Top {len(coins)} Crypto Coins</u> — {now_utc:%Y-%m-%d %H:%M} UTC</b>\n"

    # Coin list
    coin_lines = []
    for c in coins:
        price_str = f"${format_price(c.price)}"
        line = f"<b>{c.symbol.upper()}</b>: {price_str}"
        changes = []
        if include_1h and c.p1h is not None:
            changes.append(f"1h {fmt_pct(c.p1h)}")
        if include_24h and c.p24h is not None:
            changes.append(f"24h {fmt_pct(c.p24h)}")
        if changes:
            line += f" ({' / '.join(changes)})"
        if include_mcap and c.mcap is not None:
            line += f" — MCAP: ${format_price(c.mcap)}"
        coin_lines.append(line)

    # Global Metrics
    metrics_lines = ["\n<b><u>Market Snapshot</u></b>"]
    if global_metrics:
        total_mcap = global_metrics.get("total_market_cap", {}).get(vs)
        mcap_change = global_metrics.get("market_cap_change_percentage_24h_usd")
        btc_dom = global_metrics.get("market_cap_percentage", {}).get("btc")
        if total_mcap:
            metrics_lines.append(f"<b>Market Cap</b>: ${format_price(total_mcap)} ({fmt_pct(mcap_change)})")
        if btc_dom:
            metrics_lines.append(f"<b>BTC Dominance</b>: {btc_dom:.2f}%")

    # Fear & Greed Index
    if fear_greed_index:
        value = int(fear_greed_index.get("value", 0))
        classification = fear_greed_index.get("value_classification")
        metrics_lines.append(f"<b>Fear/Greed</b>: {value}/100 ({classification})")

    # Groq AI Summary
    summary_lines = []
    try:
        summary = get_groq_summary(coins, global_metrics, fear_greed_index, vs)
        if summary:
            summary_lines = ["\n<b><u>AI Summary</u></b>", summary]
            log("💬 Added Groq AI summary.")
    except Exception as e:
        log(f"⚠️ Groq summary failed: {e}")

    # Footer
    footer = f"\n<i>Stats by t.me/hourlycrypto • {api_name} API</i>"

    return "\n".join([header] + coin_lines + metrics_lines + summary_lines + [footer])


# ========== Posting Logic ==========
def post_once(demo_mode: bool = False) -> None:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.")
        sys.exit(1)
    vs = os.getenv("CURRENCY", "usd")
    ids = [x.strip() for x in os.getenv("COIN_IDS", "").split(",") if x.strip()]
    top_n = get_int_env("TOP_N", 10)
    include_mcap = get_bool_env("INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_env("INCLUDE_24H", True)
    include_1h = get_bool_env("INCLUDE_1H", True)

    log(f"🚀 Fetching all data (vs={vs}, top_n={top_n})...")
    coins, api_name = get_crypto_data(vs, ids or None, top_n)
    global_metrics = get_global_metrics()
    fear_greed = get_fear_greed_index()

    msg = build_message(coins, global_metrics, fear_greed, vs, api_name, include_1h, include_24h, include_mcap)

    if not coins:
        log("⚠️ No coin data fetched, skipping Telegram post.")
        return

    if demo_mode:
        log("💡 --demo mode: Printing message instead of sending.")
        print(msg)
    else:
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
        post_once(demo_mode=True)
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
