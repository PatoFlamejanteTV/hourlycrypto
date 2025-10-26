# src/charts.py
import logging
import matplotlib.pyplot as plt
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def generate_price_chart(coin_data: Dict[str, Any], historical_data: List[Dict[str, Any]], output_path: str) -> None:
    """Generates a historical price chart for a given cryptocurrency."""
    try:
        prices = [item[1] for item in historical_data['prices']]
        timestamps = [item[0] for item in historical_data['prices']]

        plt.figure(figsize=(10, 6))
        plt.plot(timestamps, prices)
        plt.title(f"{coin_data['name']} ({coin_data['symbol'].upper()}) Price Chart")
        plt.xlabel("Date")
        plt.ylabel(f"Price ({'USD'.upper()})")
        plt.grid(True)
        plt.savefig(output_path)
        plt.close()
    except Exception as e:
        logger.error(f"Error generating price chart: {e}")
