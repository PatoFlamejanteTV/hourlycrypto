# Vercel Deployment Guide

This guide explains how to deploy the Hourly Crypto Telegram Bot on Vercel with automatic scheduled execution.

## Overview

The bot has been adapted to run as a Vercel serverless function with Vercel Cron Jobs for scheduled execution. It will automatically post crypto prices to your Telegram channel every hour.

## Architecture

- **Serverless Function**: `api/cron.py` - Handles fetching crypto data and posting to Telegram
- **Cron Job**: Configured in `vercel.json` to run every hour (at minute 0)
- **Dependencies**: Listed in `requirements.txt` (only `requests` library needed)

## Prerequisites

1. A Vercel account (free tier works fine) - Sign up at https://vercel.com
2. Telegram bot token from @BotFather
3. Telegram chat ID for your target channel/group
4. Git installed on your machine (optional but recommended)

## Deployment Steps

### Option 1: Deploy via Vercel CLI (Recommended)

1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel**:
   ```bash
   vercel login
   ```

3. **Deploy from your project directory**:
   ```bash
   cd c:\Users\mcmco\hourlycrypto
   vercel
   ```

4. **Follow the prompts**:
   - Link to existing project? → No
   - Project name? → `hourly-crypto-bot` (or your preferred name)
   - Directory? → `./` (current directory)
   - Override settings? → No

5. **Set environment variables** (after first deployment):
   ```bash
   vercel env add TELEGRAM_BOT_TOKEN
   vercel env add TELEGRAM_CHAT_ID
   ```
   
   Optional variables:
   ```bash
   vercel env add CURRENCY
   vercel env add TOP_N
   vercel env add COIN_IDS
   vercel env add INCLUDE_MARKET_CAP
   vercel env add INCLUDE_24H
   vercel env add INCLUDE_1H
   ```

6. **Redeploy to apply environment variables**:
   ```bash
   vercel --prod
   ```

### Option 2: Deploy via Vercel Dashboard

1. **Push code to GitHub** (if not already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Vercel deployment"
   git remote add origin https://github.com/yourusername/hourly-crypto-bot.git
   git push -u origin main
   ```

2. **Import project in Vercel**:
   - Go to https://vercel.com/new
   - Click "Import Git Repository"
   - Select your GitHub repository
   - Click "Import"

3. **Configure environment variables**:
   - In the import screen, expand "Environment Variables"
   - Add the following required variables:
     - `TELEGRAM_BOT_TOKEN` → Your bot token from @BotFather
     - `TELEGRAM_CHAT_ID` → Your channel/group ID (e.g., `@yourchannel` or `-1001234567890`)
   
   - Optional variables:
     - `CURRENCY` → `usd` (default)
     - `TOP_N` → `10` (default)
     - `COIN_IDS` → Comma-separated coin IDs (e.g., `bitcoin,ethereum,tether`)
     - `INCLUDE_MARKET_CAP` → `false` (default)
     - `INCLUDE_24H` → `true` (default)
     - `INCLUDE_1H` → `true` (default)

4. **Deploy**:
   - Click "Deploy"
   - Wait for deployment to complete

## Configuration

### Cron Schedule

The default schedule is set to run every hour at minute 0 (e.g., 1:00, 2:00, 3:00, etc.).

To change the schedule, edit `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/cron",
      "schedule": "0 * * * *"
    }
  ]
}
```

Common schedule examples:
- Every hour: `"0 * * * *"`
- Every 30 minutes: `"*/30 * * * *"`
- Every 15 minutes: `"*/15 * * * *"`
- Every 6 hours: `"0 */6 * * *"`
- Daily at 9 AM UTC: `"0 9 * * *"`

**Note**: Vercel Cron uses standard cron syntax (minute hour day month weekday).

### Environment Variables

All configuration is done via environment variables in Vercel:

**Required**:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Target chat ID or username

**Optional**:
- `CURRENCY` - Currency code (default: `usd`)
- `TOP_N` - Number of top coins (default: `10`)
- `COIN_IDS` - Specific coins to track (overrides TOP_N)
- `INCLUDE_MARKET_CAP` - Show market cap (default: `false`)
- `INCLUDE_24H` - Show 24h change (default: `true`)
- `INCLUDE_1H` - Show 1h change (default: `true`)

To update environment variables:
1. Go to your project in Vercel Dashboard
2. Navigate to Settings → Environment Variables
3. Add/edit variables
4. Redeploy for changes to take effect

## Testing

### Manual Test

You can manually trigger the function to test it:

```bash
curl https://your-project.vercel.app/api/cron
```

Or visit the URL in your browser. You should see a success message and a new post in your Telegram channel.

### Check Logs

View function logs in Vercel Dashboard:
1. Go to your project
2. Click on "Deployments"
3. Click on the latest deployment
4. Click "Functions" tab
5. Select the `api/cron.py` function
6. View logs and execution history

## Monitoring

### Vercel Cron Logs

Vercel automatically logs all cron job executions:
1. Go to your project dashboard
2. Navigate to "Cron Jobs" tab
3. View execution history, success/failure status, and logs

### Telegram Verification

Simply check your Telegram channel to verify messages are being posted at the expected times.

## Troubleshooting

### Cron Job Not Running

1. **Verify cron configuration**: Check `vercel.json` syntax
2. **Check environment variables**: Ensure all required variables are set
3. **View logs**: Check Vercel dashboard for error messages
4. **Verify bot permissions**: Ensure bot is admin in the channel

### Messages Not Appearing

1. **Check bot token**: Verify `TELEGRAM_BOT_TOKEN` is correct
2. **Check chat ID**: Verify `TELEGRAM_CHAT_ID` is correct
3. **Bot permissions**: Ensure bot is added to channel and has post permissions
4. **API limits**: Check if you're hitting CoinGecko rate limits

### Function Timeout

Vercel free tier has a 10-second timeout for serverless functions. If you're fetching many coins:
- Reduce `TOP_N` value
- Use specific `COIN_IDS` instead of top N

## Costs

- **Vercel Free Tier**: Includes 100 GB-hours of serverless function execution per month
- **This bot's usage**: Approximately 1-2 seconds per execution
- **Hourly execution**: ~720 executions per month = ~24 minutes of execution time
- **Conclusion**: Well within free tier limits

## Advantages of Vercel Deployment

1. **Always Running**: No need to keep your computer on
2. **Reliable**: Vercel's infrastructure ensures high uptime
3. **Automatic**: Cron jobs run automatically without manual intervention
4. **Scalable**: Easy to adjust schedule and configuration
5. **Free**: Free tier is more than sufficient for this use case
6. **Logs**: Built-in logging and monitoring
7. **Easy Updates**: Push code changes and Vercel auto-deploys

## Updating the Bot

### Via CLI:
```bash
cd c:\Users\mcmco\hourlycrypto
# Make your changes
vercel --prod
```

### Via Git:
```bash
git add .
git commit -m "Update bot configuration"
git push
# Vercel auto-deploys on push
```

## Rollback

If something goes wrong:
1. Go to Vercel Dashboard → Deployments
2. Find a previous working deployment
3. Click "..." → "Promote to Production"

## Security Notes

- Never commit `.env` files or expose your bot token
- Use Vercel's environment variables for all secrets
- Rotate your bot token if compromised (via @BotFather)
- Limit bot permissions to only what's needed

## Support

For issues specific to:
- **Vercel deployment**: Check Vercel documentation or support
- **Bot functionality**: Refer to `AGENTS.md` and `README.md`
- **Telegram API**: Check Telegram Bot API documentation

## Migration from Windows Task Scheduler

If you were previously using Windows Task Scheduler:
1. Deploy to Vercel following this guide
2. Test the Vercel deployment
3. Once confirmed working, disable the Windows Task Scheduler task
4. You can now turn off your computer - the bot runs on Vercel!