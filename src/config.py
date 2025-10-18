# src/config.py
import os
import configparser

config = configparser.ConfigParser()

def load_config(path: str = "config.ini") -> None:
    """Loads configuration from a .ini file."""
    if os.path.isfile(path):
        config.read(path)

def load_env_from_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a .env file into os.environ if not already set."""
    try:
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as e:
        print(f"Warning: failed to read .env file: {e}")

def get_config(section: str, key: str, env_var: str, default: str = "") -> str:
    """Gets a configuration value from environment variables or config.ini."""
    value = os.getenv(env_var)
    if value is not None:
        return value
    return config.get(section, key, fallback=default)

def get_bool_config(section: str, key: str, env_var: str, default: bool = False) -> bool:
    """Gets a boolean configuration value."""
    value = os.getenv(env_var)
    if value is not None:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return config.getboolean(section, key, fallback=default)

def get_int_config(section: str, key: str, env_var: str, default: int = 0) -> int:
    """Gets an integer configuration value."""
    value = os.getenv(env_var)
    if value is not None:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    return config.getint(section, key, fallback=default)
