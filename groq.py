def get_groq_summary(coins_list, vs):
    import os
    import requests

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[Groq Debug] Missing GROQ_API_KEY environment variable.")
        return "\n\n[Groq summary skipped: no API key]"

    extra_prompt = os.getenv("GROQ_EXTRA_PROMPT", "")

    try:
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

        # Append extra prompt from .env
        if extra_prompt:
            prompt += " " + extra_prompt

        print(f"[Groq Debug] Sending request to Groq API...\nPrompt:\n{prompt}\n")

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": "You are a goofy crypto market commentator."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 140,
                "temperature": 1
            },
            timeout=25
        )

        print(f"[Groq Debug] Status code: {response.status_code}")
        print(f"[Groq Debug] Raw response: {response.text}")

        if response.status_code != 200:
            return f"\n\n[Groq API error: {response.status_code}]"

        data = response.json()
        summary = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not summary:
            print("[Groq Debug] Empty summary content.")
            return "\n\n[Summary unavailable]"

        print(f"[Groq Debug] Generated summary:\n{summary}\n")
        return "\n\n" + summary

    except Exception as e:
        print(f"[Groq Debug] Exception occurred: {e}")
        return "\n\n[Summary unavailable]"
