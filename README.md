# Hourly Crypto Telegram Bot

Fetches the latest crypto prices from CoinGecko and posts them to a Telegram channel or group every hour (or on a custom interval).

- Minimal dependencies (only `requests`)
- Posts top N coins by market cap
- Includes price, 1h and 24h changes, optional market cap
- Run once or continuously, aligned to the top of the hour (UTC)

---

## Project Structure

- `hourly_crypto_bot.py` — main Python script
- `.env` — optional local configuration file (not committed)

---

## Requirements

- Python 3.8+
- A Telegram bot token from @BotFather
- `requests` Python package

Install dependency:

```bash
python -m pip install requests
```

---

## Telegram Setup

1. Talk to @BotFather and create a new bot. Copy the given `TELEGRAM_BOT_TOKEN`.
2. Add the bot to your target channel or group.
3. For channels, make the bot an Administrator with permission to post.
4. Use one of the following as `TELEGRAM_CHAT_ID`:
   - Public channel/group: `@channelusername`
   - Private channel/group: numeric chat id (e.g., `-1001234567890`)

---

## Configuration

Set configuration using environment variables or a `.env` file placed next to the script.

Supported variables:

- `TELEGRAM_BOT_TOKEN` — Telegram bot token from BotFather (required)
- `TELEGRAM_CHAT_ID` — Target chat id or `@channelusername` (required)
- `CURRENCY` — Fiat currency code for prices (default: `usd`)
- `TOP_N` — Number of top coins to show (default: `10`)
- `INCLUDE_MARKET_CAP` — `true/false` include market cap (default: `false`)
- `INCLUDE_24H` — `true/false` include 24h change (default: `true`)
- `INCLUDE_1H` — `true/false` include 1h change (default: `true`)
- `INTERVAL_MINUTES` — Interval for continuous posting (default: `60`)

Example `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-YourBotToken
TELEGRAM_CHAT_ID=@yourchannelusername
CURRENCY=usd
TOP_N=10
INCLUDE_MARKET_CAP=false
INCLUDE_24H=true
INCLUDE_1H=true
INTERVAL_MINUTES=60
```

Note: Values in a `.env` file are loaded only if the variable is not already set in your environment.

---

## Usage

### Option 1: Deploy on Vercel (Recommended - Always Running)

Deploy to Vercel for automatic, scheduled execution without keeping your computer on:

1. Follow the detailed guide in `VERCEL_DEPLOYMENT.md`
2. Set environment variables in Vercel Dashboard
3. The bot will automatically post every hour (or your configured schedule)

**Benefits**: No computer needed, reliable, free tier sufficient, automatic execution

### Option 2: Run Locally

Run from the project directory:

- Post once and exit (useful for schedulers like Task Scheduler/cron):

```bash
python hourly_crypto_bot.py --once
```

- Run continuously, posting at the top of each hour (UTC) by default:

```bash
python hourly_crypto_bot.py
```

To customize the interval, set `INTERVAL_MINUTES` (e.g., 15, 30, 60). The bot aligns posting to the next N-minute UTC boundary to avoid drift.

### Option 3: Windows Task Scheduler (Local Hourly Posting)

1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily → Repeat task every: 1 hour (or set a specific schedule)
3. Action: Start a program
   - Program/script: `python`
   - Add arguments: `c:\Users\mcmco\hourlycrypto\hourly_crypto_bot.py --once`
   - Start in: `c:\Users\mcmco\hourlycrypto`
4. Ensure your environment variables or `.env` file are accessible to the task user.

**Note**: Computer must remain on for Task Scheduler to work. Consider Vercel deployment for 24/7 operation.

---

## Message Format

Example message:

```
Crypto Prices (USD) — 2025-01-01 12:00 UTC
BTC $43,012 | 1h: ▲+0.35% | 24h: ▼-1.12%
ETH $2,311 | 1h: ▲+0.28% | 24h: ▲+0.94%
...
```

- Price precision adapts to magnitude
- 1h/24h changes with arrow indicators
- Optional Market Cap with `INCLUDE_MARKET_CAP=true`

---

## Notes & Limits

- Data source: CoinGecko public API (`/coins/markets`), no API key required.
- Rate limits: Be considerate; avoid too frequent intervals.
- Timezone: Posting schedule is aligned to UTC boundaries for consistency.
- Chat ID: For channels, `@channelusername` is recommended; for private channels/groups, use numeric id.
- Formatting: Messages use `parse_mode=HTML` and disable link previews.

---

## Troubleshooting

- 400 Bad Request (Telegram):
  - Invalid `TELEGRAM_CHAT_ID` or missing bot permissions.
  - Bot not added as admin in a channel.
- 401/403 (Telegram):
  - Invalid `TELEGRAM_BOT_TOKEN` or bot blocked by the chat.
- Connection/Timeout errors:
  - Temporary network/CoinGecko issues; the script logs the error and continues (in continuous mode).
- No output:
  - Ensure `requests` is installed and you are running the correct Python interpreter.

---

## Development

- Single-file script for ease of deployment
- No external Telegram libraries required (uses Telegram HTTP API directly)
- PRs and improvements can extend:
  - Custom coin lists
  - Alternative price providers
  - Rich formatting and charts (sparklines)
  - Caching and backoff strategies

---

## Security

- Keep your `TELEGRAM_BOT_TOKEN` secret.
- Prefer environment variables or a local `.env` file that is not committed.
- If you deploy to hosted schedulers, store secrets in their secure secret stores.
