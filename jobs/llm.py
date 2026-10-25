"""LLM-Zugriff mit umschaltbarem Anbieter (LLM_PROVIDER in .env)."""
import json
import re
import time

import requests
from django.conf import settings


def _json_aus_text(txt):
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def complete_json(system, user):
    """Sendet Prompt, gibt geparstes JSON (dict) zurück."""
    prov = settings.LLM_PROVIDER.lower()
    if prov == "ollama":
        r = requests.post(
            f"{settings.OLLAMA_URL}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "stream": False,
                "think": False,
                "format": "json",
                "options": {"temperature": 0, "num_ctx": 8192},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=settings.OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        return _json_aus_text(r.json()["message"]["content"])
    if prov == "groq":
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY fehlt.")
        payload = {
            "model": settings.GROQ_MODEL,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if "gpt-oss" in settings.GROQ_MODEL:
            payload["reasoning_effort"] = "low"
        for versuch in range(5):
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json=payload, timeout=120,
            )
            if r.status_code == 429:  # Rate-Limit: kurz warten und erneut versuchen
                time.sleep(min(float(r.headers.get("retry-after", 5 * (versuch + 1))), 60))
                continue
            if not r.ok:
                raise RuntimeError(f"Groq HTTP {r.status_code}: {r.text[:300]}")
            return _json_aus_text(r.json()["choices"][0]["message"]["content"])
        raise RuntimeError("Groq: Rate-Limit nach 5 Versuchen weiter aktiv.")
    if prov == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY fehlt.")
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={"model": settings.ANTHROPIC_MODEL, "max_tokens": 2000, "temperature": 0,
                  "system": system, "messages": [{"role": "user", "content": user}]},
            timeout=120,
        )
        r.raise_for_status()
        return _json_aus_text("".join(b.get("text", "") for b in r.json()["content"]))
    raise RuntimeError(f"LLM_PROVIDER '{prov}' nicht unterstützt (ollama | groq | anthropic).")
