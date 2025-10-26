# config.py
import os
from datetime import datetime, timezone
from typing import Optional

def log(msg: str) -> None:
    """Print timestamped debug message."""
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

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

def fmt_pct(p: Optional[float]) -> str:
    if p is None:
        return "?"
    emoji = "💚" if p > 0 else "❤️" if p < 0 else "🤍"
    sign = "+" if p > 0 else ""
    try:
        return f"{emoji} {sign}{p:.2f}%"
    except Exception:
        return f"{emoji} {p}%"
