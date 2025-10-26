def get_groq_summary(coins, global_metrics, fear_greed_index, vs):
    import os
    import requests

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[Groq Debug] Missing GROQ_API_KEY environment variable.")
        return "\n\n[Groq summary skipped: no API key]"

    extra_prompt = os.getenv("GROQ_EXTRA_PROMPT", "")

    try:
        # Build a summary of top coin performance
        quick_summary = ", ".join([
            f"{c.symbol.upper()} {c.p24h:+.1f}%"
            for c in coins[:10] if c.p24h is not None
        ]) or "No data available"

        # Build market context string
        market_context = []
        if global_metrics:
            total_mcap = global_metrics.get("total_market_cap", {}).get(vs.lower())
            mcap_change = global_metrics.get("market_cap_change_percentage_24h_usd")
            if total_mcap and mcap_change:
                market_context.append(f"Total Market Cap: ~${int(total_mcap)} ({mcap_change:+.1f}%)")

        if fear_greed_index:
            value = fear_greed_index.get("value")
            classification = fear_greed_index.get("value_classification")
            if value and classification:
                market_context.append(f"Fear/Greed Index: {value} ({classification})")

        context_str = ". ".join(market_context)

        prompt = (
            f"Top Coins ({vs.upper()}): {quick_summary}. "
            f"Market Context: {context_str}. "
            "Based on this data, make exactly one short, funny, dumb, light-hearted line reacting to the market mood."
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