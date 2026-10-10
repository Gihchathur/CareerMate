"""Shared AI-provider layer for Ollama, OpenAI, and OpenAI-compatible APIs.

API credentials are read only from backend/.env or the process environment. They
are never returned by the settings API and never written to the JSON preferences.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

AIProviderId = Literal["ollama", "openai", "openai_compatible"]
PROVIDER_IDS: tuple[str, ...] = ("ollama", "openai", "openai_compatible")
PROVIDER_LABELS = {
    "ollama": "Ollama (local)",
    "openai": "OpenAI API",
    "openai_compatible": "OpenAI-compatible API",
}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
SETTINGS_PATH = PROJECT_ROOT / "data" / "settings" / "ai_settings.json"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:e4b"
DEFAULT_OPENAI_MODEL = "gpt-6-luna"


def _load_backend_env() -> None:
    """Load a local backend/.env if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND_DIR / ".env", override=False)
    except ImportError:
        # Process environment variables also work without python-dotenv.
        return


_load_backend_env()


class AIProviderError(RuntimeError):
    """Safe, user-facing AI provider error without credentials or raw payloads."""


def _default_preferences() -> dict[str, Any]:
    provider_from_env = os.getenv("CAREERMATE_AI_PROVIDER", "ollama").strip().lower()
    if provider_from_env not in PROVIDER_IDS:
        provider_from_env = "ollama"
    return {
        "provider": provider_from_env,
        "cloud_data_sharing_acknowledged": False,
        "providers": {
            "ollama": {
                "model": os.getenv("CAREERMATE_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
                "base_url": os.getenv("CAREERMATE_OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
            },
            "openai": {
                "model": os.getenv("CAREERMATE_OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
                "base_url": "",
            },
            "openai_compatible": {
                "model": os.getenv("CAREERMATE_OPENAI_COMPATIBLE_MODEL", ""),
                "base_url": os.getenv("CAREERMATE_OPENAI_COMPATIBLE_BASE_URL", ""),
            },
        },
    }


def _read_preferences() -> dict[str, Any]:
    preferences = _default_preferences()
    if not SETTINGS_PATH.exists():
        return preferences
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return preferences
        provider = raw.get("provider")
        if provider in PROVIDER_IDS:
            preferences["provider"] = provider
        preferences["cloud_data_sharing_acknowledged"] = bool(
            raw.get("cloud_data_sharing_acknowledged", False)
        )
        providers = raw.get("providers")
        if isinstance(providers, dict):
            for provider_id in PROVIDER_IDS:
                item = providers.get(provider_id)
                if not isinstance(item, dict):
                    continue
                for key in ("model", "base_url"):
                    value = item.get(key)
                    if isinstance(value, str) and len(value) <= 1000:
                        preferences["providers"][provider_id][key] = value
    except (OSError, json.JSONDecodeError):
        logger.warning("Ignoring unreadable AI preferences; using environment defaults")
    return preferences


def _atomic_save_preferences(preferences: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SETTINGS_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(SETTINGS_PATH)


def _api_key(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY", "").strip()
    if provider == "openai_compatible":
        return (
            os.getenv("CAREERMATE_OPENAI_COMPATIBLE_API_KEY", "").strip()
            or os.getenv("OPENROUTER_API_KEY", "").strip()
        )
    return ""


def _validate_base_url(provider: str, base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        if provider == "ollama":
            return DEFAULT_OLLAMA_HOST
        if provider == "openai":
            return ""
        raise AIProviderError("Enter the API base URL for your OpenAI-compatible provider.")

    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise AIProviderError("Enter a valid API base URL without embedded credentials, query parameters, or fragments.")
    if provider == "openai_compatible" and parsed.scheme != "https":
        host = (parsed.hostname or "").casefold()
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise AIProviderError("Use HTTPS for remote API endpoints so credentials are not sent in clear text.")
    return value


def get_ai_settings() -> dict[str, Any]:
    """Return UI-safe provider settings and credential readiness, never secrets."""
    preferences = _read_preferences()
    provider_status: dict[str, dict[str, Any]] = {}
    for provider_id in PROVIDER_IDS:
        options = preferences["providers"][provider_id]
        model = str(options.get("model", "")).strip()
        base_url = str(options.get("base_url", "")).strip()
        key_ready = bool(_api_key(provider_id)) if provider_id != "ollama" else True
        config_ready = bool(model) and key_ready
        if provider_id != "ollama":
            config_ready = config_ready and preferences["cloud_data_sharing_acknowledged"]
        if provider_id == "openai_compatible":
            config_ready = config_ready and bool(base_url)
        provider_status[provider_id] = {
            "id": provider_id,
            "label": PROVIDER_LABELS[provider_id],
            "model": model,
            "base_url": base_url,
            "configured": config_ready,
            "api_key_configured": key_ready if provider_id != "ollama" else None,
            "requires_api_key": provider_id != "ollama",
            "data_location": "local" if provider_id == "ollama" else "external provider",
        }
    return {
        "success": True,
        "provider": preferences["provider"],
        "cloud_data_sharing_acknowledged": preferences["cloud_data_sharing_acknowledged"],
        "providers": provider_status,
    }


def save_ai_settings(
    provider: str,
    model: str,
    base_url: str = "",
    confirm_cloud_data_sharing: bool = False,
) -> dict[str, Any]:
    if provider not in PROVIDER_IDS:
        raise AIProviderError("Select one of the supported AI providers.")
    model = model.strip()
    if not model or len(model) > 160:
        raise AIProviderError("Enter a model ID (1–160 characters).")
    if provider != "ollama" and not confirm_cloud_data_sharing:
        raise AIProviderError(
            "Confirm that profile/CV content and job details may be sent to the selected online AI provider."
        )
    base_url_value = _validate_base_url(provider, base_url) if provider in {"ollama", "openai_compatible"} else ""
    if provider == "openai" and not _api_key(provider):
        raise AIProviderError(
            "OpenAI API key is missing. Add OPENAI_API_KEY to backend/.env, restart CareerMate, then save this provider."
        )
    if provider == "openai_compatible" and not _api_key(provider):
        raise AIProviderError(
            "API key is missing. Add CAREERMATE_OPENAI_COMPATIBLE_API_KEY to backend/.env, restart CareerMate, then save this provider."
        )

    preferences = _read_preferences()
    preferences["provider"] = provider
    preferences["providers"][provider] = {"model": model, "base_url": base_url_value}
    if provider != "ollama":
        preferences["cloud_data_sharing_acknowledged"] = True
    _atomic_save_preferences(preferences)
    return get_ai_settings()


def get_active_provider_identity() -> tuple[str, str]:
    preferences = _read_preferences()
    provider = preferences["provider"]
    return provider, str(preferences["providers"][provider].get("model", ""))


def _runtime_config(
    provider_override: str | None = None,
    model_override: str | None = None,
    base_url_override: str | None = None,
) -> dict[str, str]:
    preferences = _read_preferences()
    provider = provider_override or str(preferences["provider"])
    if provider not in PROVIDER_IDS:
        raise AIProviderError("The selected AI provider is not supported.")
    # An environment override must never silently send candidate/job content
    # to a hosted provider. The user must confirm this in the settings UI first.
    if provider_override is None and provider != "ollama" and not preferences.get("cloud_data_sharing_acknowledged", False):
        raise AIProviderError(
            "Before using a hosted AI provider, open AI settings and explicitly confirm that task content may be sent to it."
        )

    options = preferences["providers"][provider]
    model = (model_override if model_override is not None else str(options.get("model", ""))).strip()
    base_url_raw = base_url_override if base_url_override is not None else str(options.get("base_url", ""))
    if not model:
        raise AIProviderError(f"Enter a model ID for {PROVIDER_LABELS[provider]} in AI settings.")

    if provider == "openai":
        base_url = ""
        key = _api_key(provider)
        if not key:
            raise AIProviderError(
                "OpenAI API key is missing. Add OPENAI_API_KEY to backend/.env, then restart CareerMate."
            )
    elif provider == "openai_compatible":
        base_url = _validate_base_url(provider, base_url_raw)
        key = _api_key(provider)
        if not key:
            raise AIProviderError(
                "API key is missing. Add CAREERMATE_OPENAI_COMPATIBLE_API_KEY to backend/.env, then restart CareerMate."
            )
    else:
        base_url = _validate_base_url(provider, base_url_raw)
        key = ""
    return {"provider": provider, "model": model, "base_url": base_url, "api_key": key}


def _strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Pydantic JSON schema for OpenAI strict structured output."""
    excluded_keys = {"title", "default", "examples", "minLength", "maxLength", "minItems", "maxItems"}

    def visit(value: Any) -> Any:
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: visit(item) for key, item in value.items() if key not in excluded_keys}
        if result.get("type") == "object":
            properties = result.get("properties", {})
            if isinstance(properties, dict):
                result["properties"] = {key: visit(item) for key, item in properties.items()}
                result["required"] = list(properties.keys())
            result["additionalProperties"] = False
        return result

    return visit(schema)


def _extract_openai_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text.strip()
    return ""


def generate_text(
    prompt: str,
    *,
    json_schema: dict[str, Any] | None = None,
    max_tokens: int = 1200,
    temperature: float = 0.0,
    context_window: int = 8192,
    provider_override: str | None = None,
    model_override: str | None = None,
    base_url_override: str | None = None,
) -> str:
    """Generate text or schema-constrained JSON using the active provider."""
    config = _runtime_config(provider_override, model_override, base_url_override)
    provider = config["provider"]
    model = config["model"]
    try:
        if provider == "ollama":
            from ollama import Client

            client = Client(host=config["base_url"])
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx": context_window,
                },
                "think": False,
            }
            if json_schema is not None:
                kwargs["format"] = json_schema
            response = client.chat(**kwargs)
            content = getattr(getattr(response, "message", None), "content", "") or ""
        elif provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=config["api_key"], timeout=90.0, max_retries=2)
            kwargs = {"model": model, "input": prompt, "max_output_tokens": max_tokens}
            if json_schema is not None:
                schema_name = "careermate_output"
                kwargs["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": _strict_json_schema(json_schema),
                    }
                }
            response = client.responses.create(**kwargs)
            content = _extract_openai_text(response)
        else:
            from openai import OpenAI

            client = OpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"],
                timeout=90.0,
                max_retries=2,
            )
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if json_schema is not None:
                # JSON mode is widely supported by OpenAI-compatible endpoints;
                # Pydantic validation still verifies the exact application schema.
                kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(**kwargs)
            choices = getattr(response, "choices", [])
            content = ""
            if choices:
                content = getattr(getattr(choices[0], "message", None), "content", "") or ""
    except AIProviderError:
        raise
    except ImportError as exc:
        dependency = "openai" if provider != "ollama" else "ollama"
        raise AIProviderError(
            f"The {dependency} Python package is missing. Install backend/requirements.txt and restart CareerMate."
        ) from exc
    except Exception as exc:
        logger.warning("AI request failed for provider=%s error_type=%s", provider, type(exc).__name__)
        if provider == "ollama":
            message = f"Could not reach Ollama model '{model}'. Check that Ollama is running and the model is installed."
        elif provider == "openai":
            message = "The OpenAI API request failed. Check the model ID, API key, account quota, and API billing."
        else:
            message = "The AI API request failed. Check the provider URL, model ID, API key, and account quota."
        raise AIProviderError(message) from exc

    content = str(content or "").strip()
    if not content:
        raise AIProviderError(f"{PROVIDER_LABELS[provider]} returned an empty response. Try again or select another model.")
    return content[:100000]


def test_provider_connection(provider: str, model: str, base_url: str = "") -> dict[str, Any]:
    """Run a tiny, non-personal test prompt against a selected provider."""
    text = generate_text(
        "Reply with exactly this text and nothing else: CareerMate connection successful.",
        max_tokens=40,
        temperature=0,
        provider_override=provider,
        model_override=model,
        base_url_override=base_url,
    )
    return {
        "success": True,
        "provider": provider,
        "model": model,
        "message": text[:300],
    }
