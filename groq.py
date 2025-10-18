import os
import requests

def get_groq_summary(coins_list, vs):
    """
    Generates a quick, funny two-line crypto summary using Groq's fastest model.
    coins_list: list of coin dicts (from CoinGecko or fallback APIs)
    vs: currency string, e.g. 'usd'
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "\n\n[Groq summary skipped: no API key]"

    try:
        # Build a quick summary from coin symbols and % change
        quick_summary = ", ".join([
            f"{c.get('symbol', '').upper()} {c.get('price_change_percentage_24h_in_currency', 0):+.1f}%"
            for c in coins_list[:10]
            if 'price_change_percentage_24h_in_currency' in c
        ]) or "No data available"

        prompt = (
            f"Crypto today ({vs.upper()}): {quick_summary}\n"
            "Make exactly 2 short, funny lines reacting to the market mood. "
            "Be simple, dumb, and light-hearted."
        )

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mixtral-8x7b",
                "messages": [
                    {"role": "system", "content": "You are a goofy crypto market commentator."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 40,
                "temperature": 0.9
            },
            timeout=10
        )

        data = response.json()
        summary = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        if not summary:
            summary = "[Summary unavailable]"
        return "\n\n" + summary

    except Exception as e:
        print(f"Groq summary failed: {e}")
        return "\n\n[Summary unavailable]"