"""LLM-backed alert briefing with a deterministic offline fallback."""
import json
from urllib.parse import quote

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

SYSTEM_PROMPT = (
    "You are a SOC analyst assistant for insider-threat detection. Write a concise briefing "
    "(max 120 words) in plain English: what happened, why it is suspicious versus the user's "
    "baseline, and 2-3 concrete next steps. No markdown headings. Do not invent facts beyond the data."
)


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LLM_PROVIDER: str = "none"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""


def template_summary(payload: dict) -> str:
    employee = payload["employee"]
    reasons = [r["text"].strip() for r in payload["reasons"] if isinstance(r.get("text"), str) and r["text"].strip()]
    name = employee.get("full_name") or "The user"
    detail = "; ".join(reasons) if reasons else "No explanation was recorded."
    return (f"{name} has a {payload['risk_level']} risk score of {payload['risk_score']} "
            f"for {payload['date']}. Findings: {detail}")


def _call_provider(provider: str, key: str, model: str, payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if provider == "openai":
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "instructions": SYSTEM_PROMPT, "input": data, "store": False},
            timeout=30.0,
        )
        response.raise_for_status()
        body = response.json()
        pieces = [part.get("text", "") for item in body.get("output", [])
                  for part in item.get("content", []) if part.get("type") == "output_text"]
        text = "".join(pieces).strip()
    elif provider == "gemini":
        model_name = model.removeprefix("models/")
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model_name, safe='')}:generateContent",
            headers={"x-goog-api-key": key},
            json={"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                  "contents": [{"role": "user", "parts": [{"text": data}]}]},
            timeout=30.0,
        )
        response.raise_for_status()
        body = response.json()
        pieces = [part.get("text", "") for candidate in body.get("candidates", [])
                  for part in candidate.get("content", {}).get("parts", [])]
        text = "".join(pieces).strip()
    else:
        raise ValueError("Unsupported LLM provider")
    if not text:
        raise ValueError("Provider returned an empty summary")
    return text


def summarize(payload: dict) -> dict[str, str]:
    fallback = template_summary(payload)
    try:
        config = LLMSettings()
        provider = config.LLM_PROVIDER.strip().lower()
        key, model = config.LLM_API_KEY.strip(), config.LLM_MODEL.strip()
        if provider not in ("openai", "gemini") or not key or not model:
            return {"summary": fallback, "source": "template"}
        return {"summary": _call_provider(provider, key, model, payload), "source": "llm"}
    except Exception:
        return {"summary": fallback, "source": "template"}
