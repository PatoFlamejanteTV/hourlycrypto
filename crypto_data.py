# crypto_data.py
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import requests
from config import log


@dataclass
class Coin:
    id: str
    symbol: str
    name: str
    price: Optional[float]
    p1h: Optional[float]
    p24h: Optional[float]
    mcap: Optional[float]

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


def get_from_coingecko(vs_currency: str, ids: Optional[List[str]], top_n: int, proxies: Optional[Dict[str, str]]):
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
    r = requests.get(url, params=params, timeout=20, proxies=proxies)
    r.raise_for_status()
    data = r.json()
    log(f"✅ CoinGecko returned {len(data)} coins.")
    return _transform_coingecko(data), "CoinGecko"


def get_from_coinpaprika(vs_currency: str, ids: Optional[List[str]], top_n: int, proxies: Optional[Dict[str, str]]):
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


def get_from_coincap(vs_currency: str, ids: Optional[List[str]], top_n: int, proxies: Optional[Dict[str, str]]):
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


def get_from_cryptocompare(vs_currency: str, ids: Optional[List[str]], top_n: int, proxies: Optional[Dict[str, str]]):
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


def get_crypto_data(vs_currency: str, ids: Optional[List[str]], top_n: int, proxies: Optional[Dict[str, str]]):
    sources = [
        get_from_coingecko,
        get_from_coinpaprika,
        get_from_coincap,
        get_from_cryptocompare,
    ]
    for fetcher in sources:
        try:
            return fetcher(vs_currency, ids, top_n, proxies)
        except Exception as e:
            log(f"⚠️ {fetcher.__name__} failed: {e}")
    log("❌ All coin API sources failed!")
    return [], "Unknown"


def get_global_metrics(proxies: Optional[Dict[str, str]]):
    try:
        log("🔄 Fetching global metrics from CoinGecko...")
        url = "https://api.coingecko.com/api/v3/global"
        r = requests.get(url, timeout=15, proxies=proxies)
        r.raise_for_status()
        metrics = r.json().get("data", {})
        log("✅ Global metrics fetched successfully.")
        return metrics
    except Exception as e:
        log(f"⚠️ Could not fetch global metrics: {e}")
        return {}


def get_fear_greed_index(proxies: Optional[Dict[str, str]]):
    try:
        log("🔄 Fetching Fear & Greed Index...")
        url = "https://api.alternative.me/fng/?limit=1"
        r = requests.get(url, timeout=15, proxies=proxies)
        r.raise_for_status()
        index_data = r.json().get("data", [])[0]
        log("✅ Fear & Greed Index fetched successfully.")
        return index_data
    except Exception as e:
        log(f"⚠️ Could not fetch Fear & Greed Index: {e}")
        return {}
