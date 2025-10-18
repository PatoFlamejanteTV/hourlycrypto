# AGENTS.md — Operations Guide

This document explains how the Hourly Crypto Telegram Bot works and provides runbooks for operating, scheduling, monitoring, troubleshooting, and maintaining it.


## 1) Overview

- Purpose: Post the latest crypto prices to a Telegram channel/group at a fixed cadence (default: hourly).
- Source: CoinGecko public markets API (no API key needed).
- Destination: Telegram chat via Bot API `sendMessage`.
- Runtime: Single Python script with one dependency (`requests`).


## 2) Architecture and Data Flow

1. Load configuration from process environment and a local `.env` file (if present).
2. Query CoinGecko `/api/v3/coins/markets` for the top N coins (by market cap).
3. Format a compact text summary including price, 1h and 24h change, and optional market cap.
4. POST the message to Telegram’s Bot API `sendMessage` for the configured chat.
5. In continuous mode, sleep and post again at the next N‑minute boundary (aligned to UTC to avoid drift).


## 3) Components

- `hourly_crypto_bot.py`
  - `load_env_from_dotenv()`: Loads KEY=VALUE pairs from `.env` if not already set in the environment.
  - `get_top_coins(vs_currency, per_page)`: Queries CoinGecko for market data.
  - `build_message(...)`: Assembles a readable message with price, 1h/24h changes, and optional market cap.
  - `send_telegram_message(token, chat_id, text)`: Sends the message via Telegram Bot API.
  - `post_once()`: One-shot execution (fetch + post, then exit).
  - `run_forever()`: Continuous loop aligned to the next N‑minute UTC boundary (default 60 minutes). Handles SIGINT/SIGTERM for graceful shutdown.


## 4) Configuration & Precedence

Set via environment variables or a `.env` file next to the script. The `.env` values are only applied if a variable is NOT already set in the process environment.

Required:
- `TELEGRAM_BOT_TOKEN`: Bot token from @BotFather.
- `TELEGRAM_CHAT_ID`: Target chat identifier (e.g., `@channelusername` or numeric like `-1001234567890`).

Optional:
- `CURRENCY`: Fiat currency for prices (default: `usd`).
- `TOP_N`: Number of top coins (default: `10`).
- `INCLUDE_MARKET_CAP`: `true/false` (default: `false`).
- `INCLUDE_24H`: `true/false` (default: `true`).
- `INCLUDE_1H`: `true/false` (default: `true`).
- `INTERVAL_MINUTES`: Posting cadence when running continuously (default: `60`).

Type parsing rules:
- Booleans: case-insensitive `true/false/1/0/yes/no/on/off`.
- Integers: non-numeric values fall back to defaults.


## 5) Run Modes

- One-shot mode (recommended for schedulers):
  - Command: `python hourly_crypto_bot.py --once`
  - Behavior: Fetch prices and post a single message, then exit with code 0 on success.

- Continuous daemon mode:
  - Command: `python hourly_crypto_bot.py`
  - Behavior: Aligns to the next `INTERVAL_MINUTES` UTC boundary, posts, and repeats.
  - Signals: Responds to Ctrl+C (SIGINT) and SIGTERM (best effort on Windows) for graceful stop.
  - Drift avoidance: Schedules to the next boundary precisely, not a fixed sleep cycle.


## 6) Scheduling (Windows Task Scheduler)

Use one-shot mode on a schedule.

Minimal setup:
- Program/script: `python`
- Add arguments: `c:\Users\mcmco\hourlycrypto\hourly_crypto_bot.py --once`
- Start in: `c:\Users\mcmco\hourlycrypto`

Recommended trigger options:
- Trigger Daily, Repeat task every: 1 hour, for a duration of: Indefinitely.
- Start at minute 0 for top-of-hour posting. The script itself does not need alignment in one-shot mode.

Hints:
- Run whether user is logged on or not (store credentials if needed).
- Ensure the run user has access to `.env` or environment variables.
- Enable “Stop task if it runs longer than” 5 minutes to avoid overlaps.

Alternative: Keep the script running in a terminal (continuous mode) if you prefer fewer scheduler interactions.


## 7) Logging & Monitoring

- Output: Prints to stdout/stderr.
- Sample success line: `[2025-01-01 12:00:00 UTC] Posted to @yourchannelusername`
- Suggested practice: Redirect output to a file when running as a scheduled task or daemon, e.g. `python hourly_crypto_bot.py >> bot.log 2>&1`.
- Health checks: Verify that a message appears in the target chat at the expected cadence.


## 8) Error Handling & Common Failures

- Telegram 400 Bad Request: Invalid `TELEGRAM_CHAT_ID`, malformed message, or missing bot permissions.
- Telegram 401/403: Invalid `TELEGRAM_BOT_TOKEN`, bot removed/blocked, or insufficient permissions.
- CoinGecko timeouts/5xx/429: Temporary upstream issue; try again later or increase interval.
- Network errors: Local connectivity or DNS/TLS issues.

Behavior:
- One-shot mode: Raises error and exits non-zero.
- Continuous mode: Logs the error and continues to the next scheduled tick.


## 9) Rate Limits & Cadence

- CoinGecko: Public API is rate-limited; hourly or every 15–30 minutes is reasonable. Avoid aggressive cadences.
- Telegram: Respect message frequency to prevent anti-spam measures.
- Best practice: Keep `INTERVAL_MINUTES >= 5` if you change from the default.


## 10) Security & Secrets

- Store secrets in environment variables or a local, non-committed `.env` file.
- Limit read permissions on `.env` to your user.
- Rotate `TELEGRAM_BOT_TOKEN` if compromised:
  1) Create a new token in @BotFather.
  2) Update the environment/.env on the host.
  3) For continuous mode: restart the process to pick up changes.
  4) For scheduled tasks: next run will pick up the new token.


## 11) Change Management

- Configuration change:
  - Update `.env` or environment variables.
  - For daemon mode: restart to apply.

- Code update:
  - Replace `hourly_crypto_bot.py` with the new version.
  - Test via `--once` against a staging chat before production.

- Rollback:
  - Restore a previously working copy of `hourly_crypto_bot.py`.


## 12) Customization Playbooks

- Change currency: set `CURRENCY` (e.g., `eur`, `gbp`).
- Adjust list length: set `TOP_N`.
- Toggle metrics: `INCLUDE_1H`, `INCLUDE_24H`, `INCLUDE_MARKET_CAP`.
- Change cadence: set `INTERVAL_MINUTES` when running continuously, or adjust your scheduler trigger.
- Message format: Update `build_message()` to alter header or line formatting.
- Target a fixed set of coins (advanced):
  - Replace the CoinGecko query with a coin IDs list, or filter the returned list by `id`.


## 13) Testing & Validation

- Smoke test (staging chat):
  1) Create a test channel or group.
  2) Add the bot as a member (admin for channels).
  3) Set `TELEGRAM_CHAT_ID` to the test chat and run `--once`.
  4) Verify the message content and formatting.

- Production dry run: Not applicable (the bot posts when run). Use a staging chat for validation.


## 14) Troubleshooting Checklist

- Python not found: Use `py -m pip install requests` and run with `py hourly_crypto_bot.py --once`.
- Missing dependency: Install `requests` for the target interpreter.
- No messages arrive:
  - Verify chat id (`@channelusername` vs numeric) and bot permissions.
  - Ensure the bot is an Admin in channels.
- Wrong time alignment: In continuous mode, posting aligns to UTC boundaries; verify your expectations vs UTC.
- TLS/Firewall: Ensure outbound HTTPS to api.coingecko.com and api.telegram.org is allowed.


## 15) FAQ

- How to find a private channel’s numeric chat id?
  - Add your bot as an admin. Post a message in the channel. Use a helper bot like `@userinfobot` or forward a message to it to reveal the ID, or use your own tooling with `getUpdates` if the bot uses polling elsewhere.
- Can I use a username instead of numeric id?
  - Yes, `@channelusername` is supported and recommended for public channels.
- What timezone does the timestamp use?
  - UTC, by design, to ensure predictable alignment.


## 16) Dependencies & Versions

- Python: 3.8+
- Packages: `requests` (recommend `requests>=2.31,<3` for reproducibility)

Install/upgrade:
- `python -m pip install --upgrade "requests>=2.31,<3"`


## 17) Compliance & Usage Notes

- Respect CoinGecko’s usage guidelines and fair use limits.
- This bot shares public market data; no user data is collected.
- Do not treat outputs as financial advice.


## 18) Operational Summary

- Preferred mode for reliability: One-shot on a scheduler (hourly). Simpler failure domain; each run is independent.
- Continuous mode is convenient for manual runs or environments where a long-lived process is acceptable.
- Monitor for delivery at expected times; investigate credentials, permissions, or connectivity if messages stop.
