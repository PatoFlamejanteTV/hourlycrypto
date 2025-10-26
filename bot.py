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
import warnings
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
import squarify

# Optional: AI summary from Groq (your custom module)
from groq import get_groq_summary

# ========================= Proxy Scraper / Selector =========================

PROXY_SOURCES = [
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://www.proxyscan.io/download?type=https",
]
TEST_URL = "https://1.1.1.1"
TIMEOUT = 5
MAX_WORKERS = 20


def log(msg: str) -> None:
    """Print timestamped debug message."""
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


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
            log(f"⚠️ Falha ao buscar proxies de {url}: {e}")
    return list(proxies)


def test_proxy(proxy: str) -> (str, float):
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    start = time.time()
    try:
        r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        if r.status_code == 200:
            return proxy, time.time() - start
    except Exception:
        pass
    return proxy, float("inf")


def get_fastest_proxy() -> Optional[str]:
    proxy_list = fetch_proxy_list()
    if not proxy_list:
        log("❌ Nenhum proxy encontrado!")
        return None

    fastest_proxy = None
    fastest_time = float("inf")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_proxy, p): p for p in proxy_list}
        for future in as_completed(futures):
            proxy, latency = future.result()
            if latency < fastest_time:
                fastest_time = latency
                fastest_proxy = proxy
            log(f"Tested {proxy}: {latency:.2f}s")

    if fastest_proxy:
        log(f"✅ Proxy mais rápido: {fastest_proxy} ({fastest_time:.2f}s)")
    return fastest_proxy


fast_proxy = get_fastest_proxy()
proxies = {"http": f"http://{fast_proxy}", "https": f"http://{fast_proxy}"} if fast_proxy else None


# ========================= Data Classes =========================

@dataclass
class Coin:
    id: str
    symbol: str
    name: str
    price: Optional[float]
    p1h: Optional[float]
    p24h: Optional[float]
    mcap: Optional[float]


# ========================= Utility =========================

def load_env_from_dotenv(path: str = ".env") -> None:
    """Load .env variables manually."""
    try:
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
        log("✅️ .env loaded successfully.")
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


def fmt_pct(p: Optional[float], emojis: bool = True) -> str:
    if p is None:
        return "?"
    emoji = "💚" if p > 0 else "❤️" if p < 0 else "🤍"
    sign = "+" if p > 0 else ""
    try:
        val = f"{sign}{p:.2f}%"
        return f"{emoji} {val}" if emojis else val
    except Exception:
        val = f"{sign}{p}%"
        return f"{emoji} {val}" if emojis else val


# ========================= Data Fetchers =========================

def _transform_coingecko(raw_coins: List[Dict[str, Any]]) -> List[Coin]:
    return [
        Coin(
            id=c.get("id"),
            symbol=c.get("symbol"),
            name=c.get("name"),
            price=c.get("current_price"),
            p1h=c.get("price_change_percentage_1h_in_currency"),
            p24h=c.get("price_change_percentage_24h_in_currency"),
            mcap=c.get("market_cap"),
        )
        for c in raw_coins
    ]


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
    }
    if ids:
        params["ids"] = ",".join(ids)
    headers = {"User-Agent": "hourly-crypto-bot/1.0"}
    r = requests.get(url, params=params, timeout=20, proxies=proxies, headers=headers)
    r.raise_for_status()
    data = r.json()
    log(f"✅ CoinGecko returned {len(data)} coins.")
    return _transform_coingecko(data), "CoinGecko"


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

    converted = [
        Coin(
            id=c["id"],
            symbol=c["symbol"],
            name=c["name"],
            price=c["quotes"].get(vs_currency.upper(), {}).get("price"),
            p1h=c["quotes"].get(vs_currency.upper(), {}).get("percent_change_1h"),
            p24h=c["quotes"].get(vs_currency.upper(), {}).get("percent_change_24h"),
            mcap=c["quotes"].get(vs_currency.upper(), {}).get("market_cap"),
        )
        for c in data
    ]
    log(f"✅ CoinPaprika returned {len(converted)} coins.")
    return converted, "CoinPaprika"


def get_from_coincap(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CoinCap...")
    url = "https://api.coincap.io/v2/assets"
    r = requests.get(url, timeout=20, proxies=proxies)
    r.raise_for_status()
    data = r.json().get("data", [])
    if ids:
        data = [x for x in data if x["id"] in ids]
    else:
        data = data[:top_n]
    converted = [
        Coin(
            id=c["id"],
            symbol=c["symbol"],
            name=c["name"],
            price=float(c["priceUsd"]) if c.get("priceUsd") else None,
            p1h=(float(c["changePercent24Hr"]) / 24) if c.get("changePercent24Hr") else None,
            p24h=float(c["changePercent24Hr"]) if c.get("changePercent24Hr") else None,
            mcap=float(c["marketCapUsd"]) if c.get("marketCapUsd") else None,
        )
        for c in data
    ]
    log(f"✅ CoinCap returned {len(converted)} coins.")
    return converted, "CoinCap"


def get_from_cryptocompare(vs_currency: str, ids: Optional[List[str]], top_n: int):
    log("🔄 Fetching from CryptoCompare...")
    url = "https://min-api.cryptocompare.com/data/top/mktcapfull"
    params = {"limit": top_n, "tsym": vs_currency.upper()}
    r = requests.get(url, params=params, timeout=20, proxies=proxies)
    r.raise_for_status()
    data = r.json().get("Data", [])
    converted = [
        Coin(
            id=c["CoinInfo"]["Name"].lower(),
            symbol=c["CoinInfo"]["Name"],
            name=c["CoinInfo"]["FullName"],
            price=c.get("RAW", {}).get(vs_currency.upper(), {}).get("PRICE"),
            p1h=c.get("RAW", {}).get(vs_currency.upper(), {}).get("CHANGEPCTHOUR"),
            p24h=c.get("RAW", {}).get(vs_currency.upper(), {}).get("CHANGEPCTDAY"),
            mcap=c.get("RAW", {}).get(vs_currency.upper(), {}).get("MKTCAP"),
        )
        for c in data
    ]
    log(f"✅ CryptoCompare returned {len(converted)} coins.")
    return converted, "CryptoCompare"


def get_crypto_data(vs_currency: str, ids: Optional[List[str]], top_n: int):
    sources = [
        get_from_coingecko,
        get_from_coinpaprika,
        get_from_coincap,
        get_from_cryptocompare,
    ]
    for fetcher in sources:
        try:
            return fetcher(vs_currency, ids, top_n)
        except Exception as e:
            log(f"⚠️ {fetcher.__name__} failed: {e}")
    log("❌ All coin API sources failed!")
    return [], "Unknown"


def get_global_metrics():
    try:
        log("🔄 Fetching global metrics from CoinGecko...")
        url = "https://api.coingecko.com/api/v3/global"
        headers = {"User-Agent": "hourly-crypto-bot/1.0"}
        r = requests.get(url, timeout=15, headers=headers)
        r.raise_for_status()
        metrics = r.json().get("data", {})
        log("✅ Global metrics fetched successfully.")
        return metrics
    except Exception as e:
        log(f"⚠️ Could not fetch global metrics: {e}")
        return {}


def get_fear_greed_index():
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


# ========================= Treemap Generation =========================

def generate_treemap(coins: List[Coin], vs_currency: str, path: str = "treemap.png") -> Optional[str]:
    log("🎨 Generating treemap...")
    try:
        valid = [c for c in coins if c.mcap and c.p24h is not None]
        if not valid:
            log("⚠️ No valid coin data for treemap.")
            return None

        sizes = [c.mcap for c in valid]
        price_changes = [c.p24h for c in valid]
        colors = ['#2ECC71' if change >= 0 else '#E74C3C' for change in price_changes]
        labels = [f"{c.symbol.upper()}\n{fmt_pct(c.p24h)}" for c in valid]

        plt.figure(figsize=(20, 12), dpi=150)
        # Define a font that supports emojis
        try:
            plt.rcParams['font.sans-serif'] = ["Noto Color Emoji", "Segoe UI Emoji", "sans-serif"]
        except Exception as e:
            log(f"⚠️ Could not set emoji font: {e}")

        squarify.plot(
            sizes=sizes,
            label=labels,
            color=colors,
            alpha=0.8,
            text_kwargs={'fontsize': 10, 'color': 'white', 'fontweight': 'bold'}
        )
        plt.title(
            f"[t.me/hourlycrypto] Market Treemap (24h vs {vs_currency.upper()})",
            fontsize=24,
            fontweight='bold',
            color='white'
        )
        plt.axis('off')
        plt.gca().set_facecolor('#1A1A1A')
        plt.gcf().set_facecolor('#1A1A1A')

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            plt.savefig(path, bbox_inches='tight', pad_inches=0.1)

            # Check if a font warning was raised
            if any("Glyph" in str(warn.message) for warn in w):
                log("⚠️ Emoji font not found, re-rendering treemap without emojis.")
                plt.clf()  # Clear the plot
                labels_no_emoji = [f"{c.symbol.upper()}\n{fmt_pct(c.p24h, emojis=False)}" for c in valid]
                squarify.plot(
                    sizes=sizes,
                    label=labels_no_emoji,
                    color=colors,
                    alpha=0.8,
                    text_kwargs={'fontsize': 10, 'color': 'white', 'fontweight': 'bold'}
                )
                plt.title(
                    f"[t.me/hourlycrypto] Market Treemap (24h vs {vs_currency.upper()})",
                    fontsize=24,
                    fontweight='bold',
                    color='white'
                )
                plt.axis('off')
                plt.gca().set_facecolor('#1A1A1A')
                plt.gcf().set_facecolor('#1A1A1A')
                plt.savefig(path, bbox_inches='tight', pad_inches=0.1)

        plt.close()
        log(f"✅ Treemap saved to {path}")
        return path
    except Exception as e:
        log(f"⚠️ Failed to generate treemap: {e}")
        return None


# ========================= Telegram =========================

def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    log("📤 Sending message to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20, proxies=proxies)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    log("✅ Telegram message sent successfully.")


def send_telegram_photo(token: str, chat_id: str, photo_path: str, caption: str) -> None:
    log("📤 Sending photo to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {"photo": open(photo_path, "rb")}
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    r = requests.post(url, files=files, data=payload, timeout=30, proxies=proxies)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    log("✅ Telegram photo sent successfully.")


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
        summary = get_groq_summary(coins, vs)
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
    coins, api_name = get_crypto_data(vs, ids or None, top_n)
    global_metrics = get_global_metrics()
    fear_greed_index = get_fear_greed_index()

    # Generate Treemap
    treemap_path = generate_treemap(coins, vs)

    # Build Message and Send
    msg = build_message(
        coins, global_metrics, fear_greed_index, vs, api_name, include_1h, include_24h, include_mcap
    )

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
