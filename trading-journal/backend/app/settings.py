from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date as dt_date, datetime
from functools import lru_cache

try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")), override=False)
except ImportError:
    pass

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

DEFAULT_CORS_ORIGIN_REGEX = r"^https://black-knight-.*\\.vercel\\.app$"


def _as_bool(value: str  None, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _as_int(value: str  None, default: int) -> int:
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _as_float(value: str  None) -> float  None:
    if value is None:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _parse_cors_origins(value: str  None) -> list[str]:
    if not value:
        return DEFAULT_CORS_ORIGINS

    origins = [item.strip() for item in value.split(",") if item.strip()]
    return origins or DEFAULT_CORS_ORIGINS


def _parse_date_list(value: str  None) -> list[dt_date]:
    if not value:
        return []

    dates: list[dt_date] = []
    for raw in value.split(','):
        text = raw.strip()
        if not text:
            continue
        try:
            dates.append(datetime.strptime(text, "%Y-%m-%d").date())
        except ValueError:
            continue
    return dates


def _normalize_database_url(value: str  None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "sqlite:///black_knight_quant_journal.db"

    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)

    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)

    return raw


@dataclass(frozen=True)
class Settings:
    database_url: str
    api_host: str
    api_port: int
    cors_origins: list[str]
    cors_origin_regex: str  None
    enable_socket_server: bool
    socket_ip: str
    socket_port: int
    ingest_require_hmac: bool
    hmac_secret: str
    hmac_key_id: str
    hmac_max_skew_seconds: int
    default_org_id: int
    initial_balance: float  None
    ai_provider: str
    ollama_base_url: str
    ollama_model: str
    ollama_temperature: float
    ollama_max_tokens: int
    ai_timeout_seconds: int
    groq_api_key: str
    groq_model: str
    groq_temperature: float
    groq_max_tokens: int
    nvidia_api_key: str
    nvidia_model: str
    fred_api_key: str
    newsdata_api_key: str
    exclude_trade_dates: list[dt_date]
    enable_embedded_orchestrator: bool
    ai_rate_limit_per_minute: int
    macro_calendar_url: str
    macro_calendar_poll_seconds: int
    sentinel_internal_token: str
    sentinel_snapshot_ttl_seconds: int
    sentinel_context_ttl_seconds: int


@lru_cache
def get_settings() -> Settings:
    ai_provider = (os.getenv("AI_PROVIDER") or os.getenv("BK_AI_PROVIDER") or "ollama").strip().lower()
    if ai_provider not in {"ollama", "groq", "nvidia", "auto"}:
        ai_provider = "ollama"

    ollama_temperature_value = _as_float(os.getenv("OLLAMA_TEMPERATURE") or os.getenv("BK_OLLAMA_TEMPERATURE"))
    groq_temperature_value = _as_float(os.getenv("GROQ_TEMPERATURE"))

    return Settings(
        database_url=_normalize_database_url(os.getenv("BK_DATABASE_URL") or os.getenv("DATABASE_URL")),
        api_host=os.getenv("BK_API_HOST", "0.0.0.0"),
        api_port=_as_int(os.getenv("BK_API_PORT"), 8080),
        cors_origins=_parse_cors_origins(os.getenv("BK_CORS_ORIGINS")),
        cors_origin_regex=(os.getenv("BK_CORS_ORIGIN_REGEX") or DEFAULT_CORS_ORIGIN_REGEX).strip() or None,
        enable_socket_server=_as_bool(os.getenv("BK_ENABLE_SOCKET_SERVER"), False),
        socket_ip=os.getenv("BK_SOCKET_IP", "127.0.0.1"),
        socket_port=_as_int(os.getenv("BK_SOCKET_PORT"), 18080),
        ingest_require_hmac=_as_bool(os.getenv("BK_INGEST_REQUIRE_HMAC"), False),
        hmac_secret=os.getenv("BK_HMAC_SECRET", ""),
        hmac_key_id=os.getenv("BK_HMAC_KEY_ID", ""),
        hmac_max_skew_seconds=_as_int(os.getenv("BK_HMAC_MAX_SKEW_SECONDS"), 300),
        default_org_id=_as_int(os.getenv("BK_DEFAULT_ORG_ID"), 1),
        initial_balance=_as_float(os.getenv("BK_INITIAL_BALANCE")),
        ai_provider=ai_provider,
        ollama_base_url=(os.getenv("OLLAMA_BASE_URL") or os.getenv("BK_OLLAMA_BASE_URL") or "http://127.0.0.1:11434").strip().rstrip("/"),
        ollama_model=(os.getenv("OLLAMA_MODEL") or os.getenv("BK_OLLAMA_MODEL") or "llama3.2:3b").strip() or "llama3.2:3b",
        ollama_temperature=0.2 if ollama_temperature_value is None else ollama_temperature_value,
        ollama_max_tokens=_as_int(os.getenv("OLLAMA_MAX_TOKENS") or os.getenv("BK_OLLAMA_MAX_TOKENS"), 700),
        ai_timeout_seconds=_as_int(os.getenv("AI_TIMEOUT_SECONDS") or os.getenv("BK_AI_TIMEOUT_SECONDS"), 150),
        groq_api_key=(os.getenv("GROQ_API_KEY") or os.getenv("BK_GROQ_API_KEY") or "").strip(),
        groq_model=(os.getenv("GROQ_MODEL", "llama3-8b-8192").strip() or "llama3-8b-8192"),
        groq_temperature=0.2 if groq_temperature_value is None else groq_temperature_value,
        groq_max_tokens=_as_int(os.getenv("GROQ_MAX_TOKENS"), 700),
        nvidia_api_key=(os.getenv("NVIDIA_API_KEY") or "").strip(),
        nvidia_model=(os.getenv("NVIDIA_MODEL") or "meta/llama-3.1-405b-instruct").strip(),
        fred_api_key=(os.getenv("FRED_API_KEY") or "").strip(),
        newsdata_api_key=(os.getenv("NEWSDATA_API_KEY") or "").strip(),
        exclude_trade_dates=_parse_date_list(os.getenv("BK_EXCLUDE_TRADE_DATES")),
        enable_embedded_orchestrator=_as_bool(os.getenv("BK_ENABLE_EMBEDDED_ORCHESTRATOR"), True),
        ai_rate_limit_per_minute=max(1, _as_int(os.getenv("BK_AI_RATE_LIMIT_PER_MINUTE"), 20)),
        macro_calendar_url=(os.getenv("BK_MACRO_CALENDAR_URL") or "https://nfs.faireconomy.media/ff_calendar_thisweek.json").strip(),
        macro_calendar_poll_seconds=max(30, _as_int(os.getenv("BK_MACRO_CALENDAR_POLL_SECONDS"), 60)),
        sentinel_internal_token=(os.getenv("BK_SENTINEL_INTERNAL_TOKEN") or os.getenv("BK_HMAC_SECRET") or "").strip(),
        sentinel_snapshot_ttl_seconds=max(60, _as_int(os.getenv("BK_SENTINEL_SNAPSHOT_TTL_SECONDS"), 1200)),
        sentinel_context_ttl_seconds=max(30, _as_int(os.getenv("BK_SENTINEL_CONTEXT_TTL_SECONDS"), 300)),
    )


settings = get_settings()
