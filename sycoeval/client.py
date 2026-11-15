"""Small OpenRouter chat client: one function that retries on failure and records usage and cost.

It uses plain `requests` against OpenRouter's OpenAI-compatible endpoint, so every field we send
and receive is visible here.
"""

import os
import random
import time

import requests

RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class OpenRouterError(RuntimeError):
    pass


def chat(
    messages: list[dict],
    model_id: str,
    *,
    reasoning: dict,
    provider: dict | None,
    temperature: float,
    max_tokens: int,
    base_url: str,
    timeout_s: int = 180,
    max_retries: int = 5,
) -> dict:
    """Send one chat request and return a flat dict with the reply plus its metadata.

    `messages` uses the OpenAI format: [{"role": "user" | "assistant", "content": "..."}].
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key.")

    body = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "reasoning": reasoning,
        # require_parameters: only route to providers that support every parameter we send
        # (most importantly `reasoning`), so a provider can't silently ignore the thinking switch.
        "provider": {"require_parameters": True, **(provider or {})},
        "usage": {"include": True},  # ask OpenRouter to report the cost of each call
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_error = ""
    for attempt in range(max_retries + 1):
        start = time.monotonic()
        try:
            resp = requests.post(base_url, json=body, headers=headers, timeout=timeout_s)
        except requests.RequestException as e:
            last_error = f"network error: {e}"
        else:
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    data = {"error": f"response was not JSON: {resp.text[:200]}"}
                if data.get("choices") and "error" not in data:
                    return _parse(data, time.monotonic() - start)
                last_error = f"error in response body: {data.get('error')}"
            elif resp.status_code in RETRY_STATUS:
                last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            else:  # 400, 401, 402, 404 and similar: retrying won't help
                raise OpenRouterError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        if attempt < max_retries:
            time.sleep(min(60, 2**attempt + random.random()))
    raise OpenRouterError(f"Gave up after {max_retries + 1} attempts. Last error: {last_error}")


def _parse(data: dict, latency_s: float) -> dict:
    choice = data["choices"][0]
    message = choice.get("message") or {}
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return {
        "content": message.get("content") or "",
        "reasoning": message.get("reasoning") or "",  # thinking text, if the provider returns it
        "finish_reason": choice.get("finish_reason"),  # "length" means the reply was cut off
        "native_finish_reason": choice.get("native_finish_reason"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": details.get("reasoning_tokens") or 0,
        "cost_usd": usage.get("cost"),
        "provider": data.get("provider"),
        "model": data.get("model"),
        "generation_id": data.get("id"),
        "latency_s": round(latency_s, 2),
    }
