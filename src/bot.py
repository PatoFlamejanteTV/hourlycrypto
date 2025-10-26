# src/bot.py
import sys
import time
import signal
import logging
import tempfile
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import requests

from .api import get_top_coins, get_coins_by_ids, get_historical_data
from .formatting import build_message
from .config import get_config, get_int_config, get_bool_config
from .alerts import load_alerts, check_price_alerts
from .charts import generate_price_chart

logger = logging.getLogger(__name__)

def send_telegram_message(token: str, chat_id: str, text: str) -> Dict[str, Any]:
    """Sends a message to a Telegram chat."""
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

def send_telegram_photo(token: str, chat_id: str, photo_path: str, caption: str = "") -> Dict[str, Any]:
    """Sends a photo to a Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(photo_path, "rb") as photo:
        files = {"photo": photo}
        data = {"chat_id": chat_id, "caption": caption}
        resp = requests.post(url, files=files, data=data, timeout=20)
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        data = {"ok": True}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data

def post_once() -> None:
    """Fetches and posts cryptocurrency prices once."""
    token = get_config("telegram", "bot_token", "TELEGRAM_BOT_TOKEN")
    chat_id = get_config("telegram", "chat_id", "TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.critical("Error: bot_token and chat_id must be set in config.ini or environment.")
        sys.exit(1)

    vs = get_config("settings", "currency", "CURRENCY", "usd")
    coin_ids_env = get_config("settings", "coin_ids", "COIN_IDS")
    top_n = get_int_config("settings", "top_n", "TOP_N", 10)
    include_mcap = get_bool_config("settings", "include_market_cap", "INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_config("settings", "include_24h", "INCLUDE_24H", True)
    include_1h = get_bool_config("settings", "include_1h", "INCLUDE_1H", True)

    if coin_ids_env:
        ids = [x.strip() for x in coin_ids_env.split(",") if x.strip()]
        coins = get_coins_by_ids(ids, vs_currency=vs)
    else:
        coins = get_top_coins(vs_currency=vs, per_page=top_n)

    alerts = load_alerts()
    if alerts:
        fetched_coin_ids = {c['id'] for c in coins}
        missing_coin_ids = [a['coin_id'] for a in alerts if a['coin_id'] not in fetched_coin_ids]
        if missing_coin_ids:
            coins.extend(get_coins_by_ids(missing_coin_ids, vs_currency=vs))

        notifications = check_price_alerts(coins, alerts)
        for alert_chat_id, message in notifications:
            send_telegram_message(token, alert_chat_id, message)

    message = build_message(coins, vs=vs, include_1h=include_1h, include_24h=include_24h, include_mcap=include_mcap)
    send_telegram_message(token, chat_id, message)
    logger.info(f"Posted {len(coins)} coins to Telegram chat {chat_id}.")

def demo_message() -> None:
    """Fethes live crypto data and sends a single demo message to Telegram."""
    token = get_config("telegram", "bot_token", "TELEGRAM_BOT_TOKEN")
    chat_id = get_config("telegram", "chat_id", "TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.critical("Error: bot_token and chat_id must be set in config.ini or environment.")
        sys.exit(1)

    vs = get_config("settings", "currency", "CURRENCY", "usd")
    coin_ids_env = get_config("settings", "coin_ids", "COIN_IDS")
    top_n = get_int_config("settings", "top_n", "TOP_N", 10)
    include_mcap = get_bool_config("settings", "include_market_cap", "INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_config("settings", "include_24h", "INCLUDE_24H", True)
    include_1h = get_bool_config("settings", "include_1h", "INCLUDE_1H", True)

    try:
        if coin_ids_env:
            ids = [x.strip() for x in coin_ids_env.split(",") if x.strip()]
            coins = get_coins_by_ids(ids, vs_currency=vs)
        else:
            coins = get_top_coins(vs_currency=vs, per_page=top_n)
    except Exception as e:
        logger.error(f"Error fetching coin data: {e}")
        sys.exit(1)

    message = build_message(coins, vs=vs, include_1h=include_1h, include_24h=include_24h, include_mcap=include_mcap)
    try:
        send_telegram_message(token, chat_id, message)
        logger.info(f"Demo message sent to Telegram chat {chat_id}.")
    except Exception as e:
        logger.error(f"Error sending message to Telegram: {e}")
        sys.exit(1)

def post_chart(coin_id: str) -> None:
    """Generates and posts a historical price chart for a given cryptocurrency."""
    token = get_config("telegram", "bot_token", "TELEGRAM_BOT_TOKEN")
    chat_id = get_config("telegram", "chat_id", "TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.critical("Error: bot_token and chat_id must be set in config.ini or environment.")
        sys.exit(1)

    vs = get_config("settings", "currency", "CURRENCY", "usd")
    try:
        coin_data = get_coins_by_ids([coin_id], vs_currency=vs)[0]
        historical_data = get_historical_data(coin_id, vs_currency=vs)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
            chart_path = tmpfile.name

        generate_price_chart(coin_data, historical_data, chart_path)
        send_telegram_photo(token, chat_id, chart_path, caption=f"7-day price chart for {coin_data['name']}")

        os.remove(chart_path)
        logger.info(f"Posted chart for {coin_id} to {chat_id}.")
    except Exception as e:
        logger.error(f"Error posting chart: {e}")
        sys.exit(1)

def seconds_until_next_boundary(now: Optional[datetime], minutes: int) -> float:
    """Calculates the number of seconds until the next time boundary."""
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
    """Runs the bot in a continuous loop, posting at regular intervals."""
    token = get_config("telegram", "bot_token", "TELEGRAM_BOT_TOKEN")
    chat_id = get_config("telegram", "chat_id", "TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.critical("Error: bot_token and chat_id must be set in config.ini or environment.")
        sys.exit(1)

    vs = get_config("settings", "currency", "CURRENCY", "usd")
    coin_ids_env = get_config("settings", "coin_ids", "COIN_IDS")
    top_n = get_int_config("settings", "top_n", "TOP_N", 10)
    include_mcap = get_bool_config("settings", "include_market_cap", "INCLUDE_MARKET_CAP", False)
    include_24h = get_bool_config("settings", "include_24h", "INCLUDE_24H", True)
    include_1h = get_bool_config("settings", "include_1h", "INCLUDE_1H", True)
    interval = max(1, get_int_config("settings", "interval_minutes", "INTERVAL_MINUTES", 60))

    stop = {"flag": False}

    def handle_sig(signum, frame):
        stop["flag"] = True
        logger.info("Received signal, shutting down...")

    try:
        signal.signal(signal.SIGINT, handle_sig)
        signal.signal(signal.SIGTERM, handle_sig)
    except Exception:
        pass

    wait = seconds_until_next_boundary(datetime.now(timezone.utc), interval)
    logger.info(f"Waiting {int(wait)}s until next {interval}-minute boundary (UTC) ...")
    time.sleep(wait)

    while not stop["flag"]:
        try:
            if coin_ids_env:
                ids = [x.strip() for x in coin_ids_env.split(",") if x.strip()]
                coins = get_coins_by_ids(ids, vs_currency=vs)
            else:
                coins = get_top_coins(vs_currency=vs, per_page=top_n)

            alerts = load_alerts()
            if alerts:
                fetched_coin_ids = {c['id'] for c in coins}
                missing_coin_ids = [a['coin_id'] for a in alerts if a['coin_id'] not in fetched_coin_ids]
                if missing_coin_ids:
                    coins.extend(get_coins_by_ids(missing_coin_ids, vs_currency=vs))

                notifications = check_price_alerts(coins, alerts)
                for alert_chat_id, message in notifications:
                    send_telegram_message(token, alert_chat_id, message)

            message = build_message(
                coins, vs=vs, include_1h=include_1h, include_24h=include_24h, include_mcap=include_mcap
            )
            send_telegram_message(token, chat_id, message)
            logger.info(f"Posted to {chat_id}")
        except Exception as e:
            logger.error(f"Error during post: {e}")
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
