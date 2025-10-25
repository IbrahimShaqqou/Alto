# services/agents/adk_pkg/openrouter_client.py
import os
import httpx
from typing import List, Dict, Any, Optional

class OpenRouterError(RuntimeError):
    ...

def _get(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val.strip() if isinstance(val, str) else default

def openrouter_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout_s: float = 15.0,
) -> str:
    """
    Minimal OpenRouter chat call. Returns the assistant text.
    Raises OpenRouterError on HTTP/JSON issues.
    """
    api_key = _get("OPENROUTER_API_KEY")
    base_url = _get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    referer = _get("OPENROUTER_HTTP_REFERER", "http://localhost")
    app_title = _get("OPENROUTER_APP_TITLE", "Alto")
    model = model or _get("EXPLAIN_MODEL", "openai/gpt-4o-mini")

    if temperature is None:
        try:
            temperature = float(_get("EXPLAIN_TEMPERATURE", "0.2"))
        except ValueError:
            temperature = 0.2

    if not api_key:
        raise OpenRouterError("Missing OPENROUTER_API_KEY")

    url = "{}/chat/completions".format(base_url.rstrip("/"))
    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "HTTP-Referer": referer,
        "X-Title": app_title,
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(url, headers=headers, json=payload)
        if r.status_code >= 300:
            raise OpenRouterError("OpenRouter HTTP {}: {}".format(r.status_code, r.text[:300]))
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise OpenRouterError("OpenRouter bad payload: {}; body: {}".format(e, str(data)[:300]))
