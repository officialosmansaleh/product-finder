import os
from typing import Any, Dict, Optional


_CACHE: Optional[Dict[str, str]] = None


def _default_config_path() -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, "config", "runtime_config.txt")


def _load_config() -> Dict[str, str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    cfg_path = os.getenv("RUNTIME_CONFIG_PATH", "").strip() or _default_config_path()
    out: Dict[str, str] = {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if key:
                    out[key] = val
    except Exception:
        # Keep silent and rely on in-code defaults.
        out = {}

    _CACHE = out
    return _CACHE


def _cast_by_default(value: str, default: Any) -> Any:
    if isinstance(default, bool):
        v = value.strip().lower()
        return v in {"1", "true", "yes", "on"}
    if isinstance(default, int) and not isinstance(default, bool):
        return int(float(value.strip()))
    if isinstance(default, float):
        return float(value.strip())
    return value


def cfg(key: str, default: Any) -> Any:
    raw = _load_config().get(key)
    if raw is None:
        return default
    try:
        return _cast_by_default(raw, default)
    except Exception:
        return default


def cfg_float(key: str, default: float) -> float:
    try:
        return float(cfg(key, default))
    except Exception:
        return float(default)


def cfg_int(key: str, default: int) -> int:
    try:
        return int(float(cfg(key, default)))
    except Exception:
        return int(default)


def cfg_bool(key: str, default: bool) -> bool:
    try:
        return bool(cfg(key, default))
    except Exception:
        return bool(default)


def cfg_list(key: str, default: list[str]) -> list[str]:
    raw = _load_config().get(key)
    if raw is None:
        return list(default)
    out = [x.strip() for x in str(raw).split(",")]
    out = [x for x in out if x]
    return out or list(default)
