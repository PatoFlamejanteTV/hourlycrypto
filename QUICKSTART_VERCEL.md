# Quick Start: Deploy to Vercel in 5 Minutes

## Prerequisites
- Vercel account (free): https://vercel.com/signup
- Telegram bot token from @BotFather
- Your Telegram channel/group ID

## Steps

### 1. Install Vercel CLI
```bash
npm install -g vercel
```

### 2. Login to Vercel
```bash
vercel login
```

### 3. Deploy
```bash
cd c:\Users\mcmco\hourlycrypto
vercel
```

Follow prompts:
- Link to existing project? → **No**
- Project name? → **hourly-crypto-bot** (or your choice)
- Directory? → **./`**
- Override settings? → **No**

### 4. Add Environment Variables
```bash
vercel env add TELEGRAM_BOT_TOKEN
# Paste your bot token when prompted

vercel env add TELEGRAM_CHAT_ID
# Paste your chat ID (e.g., @yourchannel or -1001234567890)
```

### 5. Deploy to Production
```bash
vercel --prod
```

### 6. Test
Visit the URL shown (e.g., `https://your-project.vercel.app/api/cron`) or wait for the next hour to see your first automated post!

## Done! 🎉

Your bot is now running on Vercel and will automatically post crypto prices every hour. You can turn off your computer - it runs in the cloud!

## Optional: Customize

Add more environment variables:
```bash
vercel env add CURRENCY
# Enter: usd, eur, gbp, etc.

vercel env add TOP_N
# Enter: 5, 10, 15, etc.

vercel env add COIN_IDS
# Enter: bitcoin,ethereum,tether (comma-separated)
```

Then redeploy:
```bash
vercel --prod
```

## Change Schedule

Edit `vercel.json` to change posting frequency:
- Every 30 minutes: `"*/30 * * * *"`
- Every 6 hours: `"0 */6 * * *"`
- Daily at 9 AM: `"0 9 * * *"`

Then redeploy:
```bash
vercel --prod
```

## View Logs

Go to https://vercel.com/dashboard → Your Project → Cron Jobs

## Need Help?

See `VERCEL_DEPLOYMENT.md` for detailed documentation.