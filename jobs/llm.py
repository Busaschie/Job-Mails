"""LLM-Zugriff mit umschaltbarem Anbieter (LLM_PROVIDER in .env)."""
import json
import re

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
    raise RuntimeError(f"LLM_PROVIDER '{prov}' nicht unterstützt (ollama | anthropic).")
