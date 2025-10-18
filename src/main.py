#!/usr/bin/env python3
"""
Hourly Crypto Telegram Bot
"""
import sys
import logging
from typing import List
from .config import load_env_from_dotenv, load_config
from .bot import post_once, demo_message, run_forever, post_chart
from .logger import setup_logging

def main(argv: List[str]) -> None:
    """Main entry point for the bot."""
    load_env_from_dotenv()
    load_config()
    setup_logging()

    args = set(a.lower() for a in argv[1:])
    if "--once" in args or "-1" in args:
        post_once()
    elif "--demo" in args:
        demo_message()
    elif "--chart" in args:
        coin_id = next((arg for arg in argv if not arg.startswith('--')), None)
        if coin_id:
            post_chart(coin_id)
        else:
            logging.error("Please specify a coin ID for the chart (e.g., --chart bitcoin).")
    else:
        run_forever()

if __name__ == "__main__":
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
        pass
