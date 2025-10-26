# src/alerts.py
import json
import logging
from typing import List, Dict, Any, Tuple

from .config import get_config

logger = logging.getLogger(__name__)

def load_alerts() -> List[Dict[str, Any]]:
    """Loads price alerts from the alerts.json file."""
    alerts_file = get_config("alerts", "file", "ALERTS_FILE", "alerts.json")
    try:
        with open(alerts_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        logger.error(f"Error decoding {alerts_file}. Please check the file format.")
        return []

def check_price_alerts(coins: List[Dict[str, Any]], alerts: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Checks for triggered price alerts and returns a list of (chat_id, message) tuples."""
    notifications = []
    for alert in alerts:
        coin_id = alert.get("coin_id")
        threshold = alert.get("threshold")
        direction = alert.get("direction")
        chat_id = alert.get("chat_id")

        if not all([coin_id, threshold, direction, chat_id]):
            logger.warning(f"Skipping invalid alert: {alert}")
            continue

        for coin in coins:
            if coin.get("id") == coin_id:
                price = coin.get("current_price")
                if price is None:
                    continue

                if direction == "above" and price > threshold:
                    message = f"🚨 <b>Price Alert</b> 🚨\n\n<b>{coin['name']}</b> has crossed <b>${threshold}</b> and is now at <b>${price}</b>!"
                    notifications.append((chat_id, message))
                elif direction == "below" and price < threshold:
                    message = f"🚨 <b>Price Alert</b> 🚨\n\n<b>{coin['name']}</b> has dropped below <b>${threshold}</b> and is now at <b>${price}</b>!"
                    notifications.append((chat_id, message))
    return notifications
