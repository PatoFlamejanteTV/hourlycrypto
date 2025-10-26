#!/usr/bin/env python3
"""
Hourly Crypto Telegram Bot
---------------------------------------
• Fetches crypto data from multiple APIs (CoinGecko, CoinPaprika, CoinCap, CryptoCompare)
• Uses automatic HTTPS proxy discovery and latency testing
• Generates market treemap images
• Posts to Telegram
• Supports Groq AI summaries (optional)
---------------------------------------
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
import squarify

# Optional: AI summary from Groq (your custom module)
from groq import get_groq_summary

# ========================= Proxy Scraper / Selector =========================
from proxy_selector import get_fastest_proxy
import crypto_data
import telegram

fast_proxy = get_fastest_proxy()
proxies = {"http": f"http://{fast_proxy}", "https": f"http://{fast_proxy}"} if fast_proxy else None


# ========================= Data Classes =========================
from crypto_data import Coin, get_crypto_data, get_global_metrics, get_fear_greed_index


# ========================= Utility =========================
from config import load_env_from_dotenv, get_bool_env, get_int_env, log


# ========================= Formatting =========================

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


from config import fmt_pct


# ========================= Treemap Generation =========================
from treemap import generate_treemap


# ========================= Telegram =========================
from telegram import send_telegram_message, send_telegram_photo


# ========================= Message Builder =========================

def build_message(
    coins: List[Coin],
    global_metrics: Dict[str, Any],
    fear_greed_index: Dict[str, Any],
    vs: str,
    api_name: str,
    include_1h: bool = True,
    include_24h: bool = True,
    include_mcap: bool = False,
) -> str:
    now_utc = datetime.now(timezone.utc)
    header = f"<b><u>Top {len(coins)} Cryptos</u> — {now_utc:%Y-%m-%d %H:%M} UTC</b>\n"

    lines = []
    for c in coins:
        line = f"<b>{c.symbol.upper()}</b>: ${format_price(c.price)}"
        changes = []
        if include_1h and c.p1h is not None:
            changes.append(f"1h {fmt_pct(c.p1h)}")
        if include_24h and c.p24h is not None:
            changes.append(f"24h {fmt_pct(c.p24h)}")
        if changes:
            line += f" ({' / '.join(changes)})"
        if include_mcap and c.mcap:
            line += f" — MCAP: ${format_price(c.mcap)}"
        lines.append(line)

    metrics = ["\n<b><u>Market Snapshot</u></b>"]
    if global_metrics:
        total_mcap = global_metrics.get("total_market_cap", {}).get(vs)
        mcap_change = global_metrics.get("market_cap_change_percentage_24h_usd")
        btc_dom = global_metrics.get("market_cap_percentage", {}).get("btc")
        if total_mcap:
            metrics.append(f"<b>Market Cap</b>: ${format_price(total_mcap)} ({fmt_pct(mcap_change)})")
        if btc_dom:
            metrics.append(f"<b>BTC Dominance</b>: {btc_dom:.2f}%")

    if fear_greed_index:
        value = int(fear_greed_index.get("value", 0))
        cls = fear_greed_index.get("value_classification")
        metrics.append(f"<b>Fear/Greed</b>: {value}/100 ({cls})")

    # AI Summary
    summary_lines = []
    try:
        summary = get_groq_summary(coins, global_metrics, fear_greed_index, vs)
        if summary:
            summary_lines = ["\n<b><u>AI Summary</u></b>", summary]
            log("💬 Added Groq summary.")
    except Exception as e:
        log(f"⚠️ Groq summary failed: {e}")

    footer = f"\n<i>Stats by t.me/hourlycrypto • {api_name} API</i>"
    return "\n".join([header] + lines + metrics + summary_lines + [footer])


# ========================= Posting Logic =========================

def post_once() -> None:
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        sys.exit(1)
    vs = os.getenv("CURRENCY", "usd")
    ids = [x.strip() for x in os.getenv("COIN_IDS", "").split(",") if x.strip()]
    top_n = get_int_env("TOP_N", 10)
    include_mcap = get_bool_env("INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_env("INCLUDE_24H", True)
    include_1h = get_bool_env("INCLUDE_1H", True)

    log(f"🚀 Fetching crypto data (vs={vs}, top_n={top_n})...")
    coins, api_name = get_crypto_data(vs, ids or None, top_n, proxies)
    global_metrics = get_global_metrics(proxies)
    fear_greed_index = get_fear_greed_index(proxies)

    # Generate Treemap
    treemap_path = generate_treemap(coins, vs)

    # Build Message and Send
    msg = build_message(coins, global_metrics, fear_greed_index, vs, api_name, include_1h, include_24h, include_mcap)

    if treemap_path:
        send_telegram_photo(token, chat_id, treemap_path, msg, proxies)
        os.remove(treemap_path)  # Clean up the generated image
    else:
        send_telegram_message(token, chat_id, msg, proxies)

    log(f"✅ Posted {len(coins)} coins using {api_name}.\n")

# ========================= Main =========================
def main(argv: List[str]) -> None:
    load_env_from_dotenv()
    args = set(a.lower() for a in argv[1:])
    interval = get_int_env("INTERVAL_MINUTES", 60)

    if "--once" in args or "-1" in args:
        post_once()
    elif "--demo" in args:
        post_once()
    else:
        log(f"⏳ Running continuously every {interval} minutes, aligned to UTC.")
        while True:
            try:
                post_once()
            except Exception as e:
                log(f"⚠️ Error during post_once: {e}")

            now_utc = datetime.now(timezone.utc)
            minutes_to_next_interval = interval - (now_utc.minute % interval)
            next_run_time = (now_utc + timedelta(minutes=minutes_to_next_interval)).replace(second=0, microsecond=0)

            sleep_seconds = (next_run_time - now_utc).total_seconds()

            if sleep_seconds <= 0:
                next_run_time += timedelta(minutes=interval)
                sleep_seconds = (next_run_time - now_utc).total_seconds()

            log(f"⏰ Next post at {next_run_time.strftime('%Y-%m-%d %H:%M:%S UTC')}. Sleeping for {sleep_seconds:.2f} seconds.")
            time.sleep(sleep_seconds)

if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        log("🛑 Bot stopped manually.")
