"""Raw JSON calls to Ollama / Gemini (used by the photo recognition)."""
import asyncio
import base64
import json
import re

import httpx

from .config import settings

RETRY_CODES = {429, 500, 502, 503, 504}
TIMEOUT = httpx.Timeout(60.0, connect=15.0)


def extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start : end + 1])


async def _ollama(prompt: str, image_b64: str | None) -> str:
    msg: dict = {"role": "user", "content": prompt}
    if image_b64:
        msg["images"] = [image_b64]
    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [msg],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Ollama {r.status_code}: {r.text[:300]}")
        return r.json()["message"]["content"]


async def _gemini(prompt: str, image_b64: str | None) -> str:
    parts: list[dict] = [{"text": prompt}]
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }

    models = [settings.gemini_model]
    fb = settings.gemini_fallback_model
    if fb and fb != settings.gemini_model:
        models.append(fb)

    last_error = "unknown error"
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for attempt in range(2):
                try:
                    r = await c.post(url, headers={"x-goog-api-key": settings.gemini_api_key}, json=body)
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_error = f"{type(e).__name__} while calling {model} (slow or no connection)"
                    await asyncio.sleep(1)
                    continue  # try again, then move to the backup model
                if r.status_code < 400:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                last_error = f"Gemini {r.status_code} ({model}): {r.text[:300]}"
                if r.status_code in RETRY_CODES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if r.status_code == 404:  # this model name is gone, try the backup model
                    break
                raise RuntimeError(last_error)  # 400/401/403: key or request problem
    raise RuntimeError(last_error)


async def ask_json(prompt: str, image_bytes: bytes | None = None) -> dict:
    image_b64 = base64.b64encode(image_bytes).decode() if image_bytes else None
    if settings.vlm_provider == "gemini":
        raw = await _gemini(prompt, image_b64)
    else:
        raw = await _ollama(prompt, image_b64)
    return extract_json(raw)