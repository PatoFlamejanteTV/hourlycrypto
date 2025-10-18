# src/formatting.py
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

def format_price(v: Optional[float]) -> str:
    """Formats a float as a price string."""
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
    """Formats a float as a percentage string."""
    if p is None:
        return "?%"
    arrow = "▲" if p > 0 else "▼"
    sign = "+" if p > 0 else ""
    try:
        return f"{arrow}{sign}{p:.2f}%"
    except Exception:
        return f"{arrow}{p}%"

def build_message(
    coins: List[Dict[str, Any]],
    vs: str,
    include_1h: bool = True,
    include_24h: bool = True,
    include_mcap: bool = False,
) -> str:
    """Builds the Telegram message from a list of coin data."""
    now_utc = datetime.now(timezone.utc)
    header = f"Crypto Prices ({vs.upper()}) — {now_utc:%Y-%m-%d %H:%M} UTC\n"
    lines = [header]

    for c in coins:
        try:
            symbol = (c.get("symbol") or "").upper()
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
            if include_mcap and mcap is not None:
                parts.append(f"MC: ${format_price(mcap)}")

            lines.append(" ".join(parts))
        except Exception:
            lines.append(f"{c.get('symbol','?').upper()} ${format_price(c.get('current_price'))}")

    return "\n".join(lines)
