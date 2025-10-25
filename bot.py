#!/usr/bin/env python3
"""
Hourly Crypto Telegram Bot (with API fallbacks + Groq summary + Debugging + Fast Proxy)
"""

import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
import squarify

from groq import get_groq_summary

# ========================= Proxy Scraper / Selector =========================
PROXY_SOURCES = [
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://www.proxyscan.io/download?type=https",
]
TEST_URL = "https://1.1.1.1"
TIMEOUT = 5
MAX_WORKERS = 20

def fetch_proxy_list() -> List[str]:
    proxies = set()
    for url in PROXY_SOURCES:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            for line in r.text.splitlines():
                line = line.strip()
                if line:
                    proxies.add(line)
        except Exception as e:
            print(f"⚠️ Falha ao buscar proxies de {url}: {e}")
    return list(proxies)

def test_proxy(proxy: str) -> (str, float):
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    start = time.time()
    try:
        r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        if r.status_code == 200:
            return proxy, time.time() - start
    except:
        pass
    return proxy, float('inf')

def get_fastest_proxy() -> Optional[str]:
    proxy_list = fetch_proxy_list()
    if not proxy_list:
        print("❌ Nenhum proxy encontrado!")
        return None

    fastest_proxy = None
    fastest_time = float('inf')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_proxy, p): p for p in proxy_list}
        for future in as_completed(futures):
            proxy, latency = future.result()
            if latency < fastest_time:
                fastest_time = latency
                fastest_proxy = proxy
            print(f"Tested {proxy}: {latency:.2f}s")

    if fastest_proxy:
        print(f"✅ Proxy mais rápido: {fastest_proxy} ({fastest_time:.2f}s)")
    return fastest_proxy

# ========================= Global Proxy Setup =========================
fast_proxy = get_fastest_proxy()
proxies = {"http": f"http://{fast_proxy}", "https": f"http://{fast_proxy}"} if fast_proxy else None

# ========================= Utility =========================
def log(msg: str) -> None:
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def load_env_from_dotenv(path: str = ".env") -> None:
    try:
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
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

def fmt_pct(p: Optional[float]) -> str:
    if p is None:
        return "?%"
    arrow = "" if p == 0 else ("▲" if p > 0 else "▼")
    sign = "+" if p and p > 0 else ""
    try:
        return f"{arrow}{sign}{p:.2f}%"
    except Exception:
        return f"{arrow}{p}%"

# ========================= Data Fetchers =========================
def get_from_coingecko(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinGecko...")
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": vs_currency, "order": "market_cap_desc", "per_page": max(1, min(top_n, 250)), "page": 1, "sparkline": "false", "price_change_percentage": "1h,24h", "locale": "en"}
    if ids:
        params["ids"] = ",".join(ids)
    r = requests.get(url, params=params, timeout=20, proxies=proxies)
    r.raise_for_status()
    log(f"✅ CoinGecko returned {len(r.json())} coins.")
    return r.json(), "CoinGecko"

def get_from_coinpaprika(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinPaprika...")
    url = "https://api.coinpaprika.com/v1/tickers"
    r = requests.get(url, timeout=20, proxies=proxies)
    r.raise_for_status()
    data = r.json()
    if ids:
        data = [x for x in data if x["id"] in ids]
    else:
        data = sorted(data, key=lambda x: x.get("rank", 9999))[:top_n]
    converted = [{"id": c["id"], "symbol": c["symbol"], "name": c["name"],
                  "current_price": c["quotes"].get(vs_currency.upper(), {}).get("price"),
                  "market_cap": c["quotes"].get(vs_currency.upper(), {}).get("market_cap"),
                  "price_change_percentage_1h_in_currency": c["quotes"].get(vs_currency.upper(), {}).get("percent_change_1h"),
                  "price_change_percentage_24h_in_currency": c["quotes"].get(vs_currency.upper(), {}).get("percent_change_24h")} for c in data]
    log(f"✅ CoinPaprika returned {len(converted)} coins.")
    return converted, "CoinPaprika"

def get_from_coincap(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinCap...")
    url = "https://api.coincap.io/v2/assets"
    r = requests.get(url, timeout=20, proxies=proxies)
    r.raise_for_status()
    data = r.json()["data"]
    if ids:
        data = [x for x in data if x["id"] in ids]
    else:
        data = data[:top_n]
    converted = [{"id": c["id"], "symbol": c["symbol"], "name": c["name"],
                  "current_price": float(c["priceUsd"]), "market_cap": float(c["marketCapUsd"]),
                  "price_change_percentage_1h_in_currency": float(c.get("changePercent24Hr", 0)) / 24,
                  "price_change_percentage_24h_in_currency": float(c.get("changePercent24Hr", 0))} for c in data]
    log(f"✅ CoinCap returned {len(converted)} coins.")
    return converted, "CoinCap"

def get_from_cryptocompare(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/top/mktcapfull"
    params = {"limit": top_n, "tsym": vs_currency.upper()}
    r = requests.get(url, params=params, timeout=20, proxies=proxies)
    r.raise_for_status()
    data = r.json().get("Data", [])
    converted = [{"id": c["CoinInfo"]["Name"].lower(), "symbol": c["CoinInfo"]["Name"], "name": c["CoinInfo"]["FullName"],
                  "current_price": c.get("RAW", {}).get(vs_currency.upper(), {}).get("PRICE"),
                  "market_cap": c.get("RAW", {}).get(vs_currency.upper(), {}).get("MKTCAP"),
                  "price_change_percentage_1h_in_currency": c.get("RAW", {}).get(vs_currency.upper(), {}).get("CHANGEPCTHOUR"),
                  "price_change_percentage_24h_in_currency": c.get("RAW", {}).get(vs_currency.upper(), {}).get("CHANGEPCTDAY")} for c in data]
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

# ========================= Telegram =========================
def send_telegram_message(token: str, chat_id: str, text: str) -> Dict[str, Any]:
    log("📤 Sending message to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20, proxies=proxies)
    try:
        data = r.json()
    except Exception:
        r.raise_for_status()
        data = {"ok": True}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    log("✅ Telegram message sent successfully.")
    return data

def send_telegram_photo(token: str, chat_id: str, photo_path: str, caption: str) -> Dict[str, Any]:
    log("📤 Sending photo to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {'photo': open(photo_path, 'rb')}
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    r = requests.post(url, files=files, data=payload, timeout=30, proxies=proxies)
    try:
        data = r.json()
    except Exception:
        r.raise_for_status()
        data = {"ok": True}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    log("✅ Telegram photo sent successfully.")
    return data

# ========================= Treemap Generation =========================
def generate_treemap(coins: List[Dict[str, Any]], vs_currency: str, path: str = "treemap.png") -> Optional[str]:
    log("🎨 Generating treemap...")
    try:
        # Filter out coins with missing or invalid data
        coins = [c for c in coins if c.get("market_cap") and c.get("price_change_percentage_24h_in_currency") is not None]
        if not coins:
            log("⚠️ No valid coin data for treemap.")
            return None

        sizes = [c["market_cap"] for c in coins]
        price_changes = [c["price_change_percentage_24h_in_currency"] for c in coins]

        # Determine colors based on price change
        colors = ['#2ECC71' if change >= 0 else '#E74C3C' for change in price_changes]

        # Create labels for each coin
        labels = [f"{c['symbol'].upper()}\n{fmt_pct(c['price_change_percentage_24h_in_currency'])}" for c in coins]

        plt.figure(figsize=(20, 12), dpi=150)
        squarify.plot(sizes=sizes, label=labels, color=colors, alpha=0.8, text_kwargs={'fontsize':10, 'color':'white', 'fontweight':'bold'})

        plt.title(f"[t.me/hourlycrypto] Crypto Market Cap Treemap (24h % Change vs {vs_currency.upper()})", fontsize=24, fontweight='bold', color='white')
        plt.axis('off')

        # Dark theme background
        plt.gca().set_facecolor('#1A1A1A')
        plt.gcf().set_facecolor('#1A1A1A')

        plt.savefig(path, bbox_inches='tight', pad_inches=0.1)
        plt.close()

        log(f"✅ Treemap saved to {path}")
        return path
    except Exception as e:
        log(f"⚠️ Failed to generate treemap: {e}")
        return None

# ========================= Message Builder =========================
def build_message(coins: list[dict], vs: str, api_name: str, include_1h=True, include_24h=True, include_mcap=False) -> str:
    now_utc = datetime.now(timezone.utc)
    lines = [f"Crypto Prices ({vs.upper()}) — {now_utc:%Y-%m-%d %H:%M} UTC\n"]
    for c in coins:
        try:
            symbol = c.get("symbol", "?").upper()
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
            if include_mcap:
                parts.append(f"MC: ${format_price(mcap)}")
            lines.append(" ".join(parts))
        except Exception as e:
            log(f"⚠️ Error formatting {c.get('symbol')}: {e}")

    try:
        summary = get_groq_summary(coins, vs)
        if summary:
            lines.append("\n" + summary)
            log("💬 Added Groq AI summary.")
    except Exception as e:
        log(f"⚠️ Groq summary failed: {e}")

    lines.append(f"\n<i>Pricing by <b>t.me/hourlycrypto</b> • Prices computed from {api_name}.</i>")
    return "\n".join(lines)

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
    coins, api_name = get_crypto_data(vs, ids or None, top_n)

    # Generate Treemap
    treemap_path = generate_treemap(coins, vs)

    # Build Message and Send
    msg = build_message(coins, vs, api_name, include_1h, include_24h, include_mcap)

    if treemap_path:
        send_telegram_photo(token, chat_id, treemap_path, msg)
        os.remove(treemap_path)  # Clean up the generated image
    else:
        send_telegram_message(token, chat_id, msg)

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
