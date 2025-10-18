import os
import requests

def get_groq_summary(coins, vs):
    """Fetch a fast & funny two-line summary using Groq AI (mixtral-8x7b)."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "\n\n[Groq summary skipped: no API key]"

    try:
        quick_summary = ", ".join([
            f"{c.get('symbol','').upper()} {c.get('price_change_percentage_24h_in_currency', 0):+.1f}%"
            for c in coins[:10]
            if 'price_change_percentage_24h_in_currency' in c
        ])

        prompt = (
            f"Crypto today ({vs.upper()}): {quick_summary}\n"
            "Make 2 short funny lines reacting to the market mood. "
            "Use very simple humor, nothing poetic or deep."
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
                    {"role": "system", "content": "You write funny but dumb crypto comments."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 40,
                "temperature": 0.9
            },
            timeout=15
        )

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        return "\n\n" + content

    except Exception as e:
        print(f"Groq summary failed: {e}")
        return "\n\n[Summary unavailable]"