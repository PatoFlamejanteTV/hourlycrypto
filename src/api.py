# src/api.py
import requests
from typing import Dict, Any, List

def get_top_coins(vs_currency: str = "usd", per_page: int = 10) -> List[Dict[str, Any]]:
    """Fetches the top N cryptocurrencies by market cap from CoinGecko."""
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
    """Fetches cryptocurrency data for a specific list of CoinGecko IDs."""
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

def get_historical_data(coin_id: str, vs_currency: str = "usd", days: int = 7) -> Dict[str, Any]:
    """Fetches historical market data for a specific cryptocurrency."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": vs_currency,
        "days": days,
    }
    headers = {"Accept": "application/json"}
    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response from CoinGecko")
    return data
