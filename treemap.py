# treemap.py
from typing import List, Optional
import matplotlib.pyplot as plt
import squarify
from crypto_data import Coin
from config import log

from config import fmt_pct

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

        plt.savefig(path, bbox_inches='tight', pad_inches=0.1)
        plt.close()
        log(f"✅ Treemap saved to {path}")
        return path
    except Exception as e:
        log(f"⚠️ Failed to generate treemap: {e}")
        return None
