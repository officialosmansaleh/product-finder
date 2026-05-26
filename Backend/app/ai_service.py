from __future__ import annotations

import base64
import logging
import json
import os
import threading
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from openai import OpenAI
from pydantic import BaseModel


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


_load_env_file()
_client: Optional[OpenAI] = None
_client_init_failed = False
_JSON_RESPONSE_INSTRUCTION = "Return valid JSON only."
_DEFAULT_TEXT_MODELS = ("gpt-4o-2024-08-06", "gpt-4.1-mini")
_DEFAULT_IMAGE_MODELS = ("gpt-4.1-mini", "gpt-4o-mini")
_AI_INTERROGATION_LOGGER_NAME = "product_finder.external_ai_interrogations"
_DEFAULT_AI_INTERROGATION_LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "external_ai_interrogations.jsonl"
_ai_interrogation_logger: Optional[logging.Logger] = None
_ai_interrogation_logger_path = ""
_ai_interrogation_logger_lock = threading.Lock()


def _ai_interrogation_log_path() -> Path:
    raw = (
        str(os.getenv("EXTERNAL_AI_INTERROGATION_LOG_PATH", "")).strip()
        or str(os.getenv("AI_INTERROGATION_LOG_PATH", "")).strip()
    )
    return Path(raw).expanduser() if raw else _DEFAULT_AI_INTERROGATION_LOG_PATH


def _get_ai_interrogation_logger() -> logging.Logger:
    global _ai_interrogation_logger, _ai_interrogation_logger_path
    path = _ai_interrogation_log_path()
    path_key = str(path)
    with _ai_interrogation_logger_lock:
        if _ai_interrogation_logger is not None and _ai_interrogation_logger_path == path_key:
            return _ai_interrogation_logger
        path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(_AI_INTERROGATION_LOGGER_NAME)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        _ai_interrogation_logger = logger
        _ai_interrogation_logger_path = path_key
        return logger


def _sanitize_ai_log_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        sanitized = []
        for item in content:
            if not isinstance(item, dict):
                sanitized.append(item)
                continue
            item_type = str(item.get("type") or "").strip()
            if item_type == "image_url":
                sanitized.append({"type": "image_url", "image_url": "[image data omitted]"})
            else:
                sanitized.append(dict(item))
        return sanitized
    return content


def _messages_for_ai_interrogation_log(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for message in messages:
        sanitized.append({
            "role": str(message.get("role") or ""),
            "content": _sanitize_ai_log_content(message.get("content")),
        })
    return sanitized


def _log_ai_interrogation(
    *,
    model: str,
    attempt: int,
    messages: list[dict[str, Any]],
    response_model: type[BaseModel],
    log_context: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider": "openai",
            "model": model,
            "attempt": attempt,
            "response_model": getattr(response_model, "__name__", str(response_model)),
            "context": dict(log_context or {}),
            "messages": _messages_for_ai_interrogation_log(messages),
        }
        _get_ai_interrogation_logger().info(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        # Logging the outgoing AI question must never block the actual search flow.
        pass


def _get_client() -> Optional[OpenAI]:
    global _client, _client_init_failed
    if _client is not None:
        return _client
    if _client_init_failed:
        return None
    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return None
    try:
        _client = OpenAI(api_key=api_key)
    except Exception as exc:
        print(f"LLM client disabled: {exc}")
        _client_init_failed = True
        return None
    return _client


def _model_candidates_from_env(env_key: str, defaults: Iterable[str]) -> list[str]:
    raw = str(os.getenv(env_key, "") or "").strip()
    if raw:
        models = [part.strip() for part in raw.split(",") if part.strip()]
        if models:
            return models
    return [str(model).strip() for model in defaults if str(model).strip()]


def _ai_disabled_result(message: str) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "provider": "openai",
        "model": "",
        "used_retry": False,
        "message": message,
    }


def _ensure_json_instruction(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    has_json_word = False
    normalized: list[dict[str, Any]] = []
    for message in messages:
        current = dict(message)
        content = current.get("content")
        if isinstance(content, str):
            if "json" in content.lower():
                has_json_word = True
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and "json" in text.lower():
                        has_json_word = True
        normalized.append(current)
    if has_json_word:
        return normalized
    if normalized and normalized[0].get("role") == "system" and isinstance(normalized[0].get("content"), str):
        normalized[0]["content"] = f"{normalized[0]['content'].rstrip()} {_JSON_RESPONSE_INSTRUCTION}"
        return normalized
    return [{"role": "system", "content": _JSON_RESPONSE_INSTRUCTION}, *normalized]


def _is_retryable_error(exc: Exception) -> bool:
    text = str(exc or "").strip().lower()
    if not text:
        return False
    retry_markers = (
        "timeout",
        "timed out",
        "temporar",
        "rate limit",
        "too many requests",
        "connection",
        "connect",
        "overloaded",
        "unavailable",
        "server error",
        "internal error",
        "bad gateway",
        "gateway timeout",
        "429",
        "500",
        "502",
        "503",
        "504",
    )
    return any(marker in text for marker in retry_markers)


def _request_json_completion(
    *,
    messages: list[dict[str, Any]],
    response_model: type[BaseModel],
    model_candidates: Iterable[str],
    max_attempts: int = 2,
    sleep_seconds: float = 0.25,
    log_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    client = _get_client()
    if client is None:
        return {
            **_ai_disabled_result("OpenAI API key is missing or the client could not be initialized."),
            "content": {},
        }
    messages = _ensure_json_instruction(messages)

    last_exc: Optional[Exception] = None
    models = [str(m).strip() for m in model_candidates if str(m).strip()]
    used_retry = False
    for model in models:
        for attempt in range(1, max_attempts + 1):
            try:
                _log_ai_interrogation(
                    model=model,
                    attempt=attempt,
                    messages=messages,
                    response_model=response_model,
                    log_context=log_context,
                )
                parse_fn = getattr(client.chat.completions, "parse", None)
                if callable(parse_fn):
                    completion = parse_fn(
                        model=model,
                        messages=messages,
                        response_format=response_model,
                        temperature=0,
                    )
                    parsed = completion.choices[0].message.parsed
                    obj = parsed if isinstance(parsed, response_model) else response_model.model_validate(parsed)
                else:
                    completion = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0,
                    )
                    content = completion.choices[0].message.content or "{}"
                    obj = response_model.model_validate(json.loads(content))
                return {
                    "status": "ok" if not used_retry else "degraded",
                    "provider": "openai",
                    "model": model,
                    "used_retry": used_retry,
                    "message": "" if not used_retry else "AI response succeeded after a retry/fallback.",
                    "content": obj.model_dump(exclude_none=True),
                }
            except Exception as exc:
                last_exc = exc
                should_retry = attempt < max_attempts and _is_retryable_error(exc)
                if should_retry:
                    used_retry = True
                    time.sleep(sleep_seconds)
                    continue
                break

    if last_exc is not None:
        return {
            "status": "error",
            "provider": "openai",
            "model": "",
            "used_retry": used_retry,
            "message": f"AI inference unavailable right now: {last_exc}",
            "content": {},
        }
    return {
        "status": "error",
        "provider": "openai",
        "model": "",
        "used_retry": used_retry,
        "message": "AI inference unavailable right now.",
        "content": {},
    }


def infer_text_filters(
    *,
    text: str,
    allowed_families: Optional[list[str]],
    response_model: type[BaseModel],
    system_prompt: str,
    log_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = _request_json_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text or ""},
        ],
        response_model=response_model,
        model_candidates=_model_candidates_from_env("OPENAI_TEXT_MODELS", _DEFAULT_TEXT_MODELS),
        log_context=log_context,
    )
    return result


def infer_image_filters(
    *,
    image_bytes: bytes,
    mime_type: str,
    response_model: type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    log_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not image_bytes:
        return {
            "status": "error",
            "provider": "openai",
            "model": "",
            "used_retry": False,
            "message": "No image provided for AI inference.",
            "content": {},
        }

    mime = str(mime_type or "image/jpeg").strip().lower()
    if not mime.startswith("image/"):
        mime = "image/jpeg"
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    return _request_json_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        response_model=response_model,
        model_candidates=_model_candidates_from_env("OPENAI_IMAGE_MODELS", _DEFAULT_IMAGE_MODELS),
        log_context=log_context,
    )
