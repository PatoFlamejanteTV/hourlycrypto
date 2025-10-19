def get_groq_summary(coins_list, global_metrics, fear_greed_index, vs):
    import os
    import requests

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[Groq Debug] Missing GROQ_API_KEY environment variable.")
        return "\n\n[Groq summary skipped: no API key]"

    extra_prompt = os.getenv("GROQ_EXTRA_PROMPT", "")

    try:
        coin_summary = ", ".join([
            f"{c.symbol.upper()} {c.p24h:+.1f}%"
            for c in coins_list[:5]
            if c.p24h is not None
        ])

        mcap_change = global_metrics.get("market_cap_change_percentage_24h_usd", 0)
        fear_greed_val = fear_greed_index.get("value", "N/A")
        fear_greed_class = fear_greed_index.get("value_classification", "N/A")

        market_context = (
            f"Top movers: {coin_summary}. "
            f"Market cap 24h change: {mcap_change:+.1f}%. "
            f"Fear/Greed Index: {fear_greed_val} ({fear_greed_class})."
        )

        prompt = (
            f"Analyze this crypto market data: {market_context}\n"
            "Create a 1-sentence, witty, and slightly cynical summary. "
            "Focus on the overall mood. No financial advice."
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
                "max_tokens": 180,
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
        usage = data.get("usage", {})

        # Extract timing and token metrics
        total_time = usage.get("total_time")
        total_tokens = usage.get("total_tokens")
        tps = (total_tokens / total_time) if total_time else None

        if total_time is not None and total_tokens is not None and tps is not None:
            print(f"[Groq Debug] Total time: {total_time:.3f}s | Total tokens: {total_tokens} | Tokens/sec: {tps:.2f}")

        if not summary:
            print("[Groq Debug] Empty summary content.")
            return "\n\n[Summary unavailable]"

        print(f"[Groq Debug] Generated summary:\n{summary}\n")
        return "\n\n" + summary

    except Exception as e:
        print(f"[Groq Debug] Exception occurred: {e}")
        return "\n\n[Summary unavailable]"