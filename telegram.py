# telegram.py
import requests
from config import log

from typing import Dict, Optional

def send_telegram_message(token: str, chat_id: str, text: str, proxies: Optional[Dict[str, str]]) -> None:
    log("📤 Sending message to Telegram...")
    url = f"httpshttps://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20, proxies=proxies)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    log("✅ Telegram message sent successfully.")


def send_telegram_photo(token: str, chat_id: str, photo_path: str, caption: str, proxies: Optional[Dict[str, str]]) -> None:
    log("📤 Sending photo to Telegram...")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    files = {"photo": open(photo_path, "rb")}
    payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    r = requests.post(url, files=files, data=payload, timeout=30, proxies=proxies)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    log("✅ Telegram photo sent successfully.")
