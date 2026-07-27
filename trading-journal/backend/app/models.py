from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint
from typing import Optional
from datetime import datetime, timezone

class TradeArchive(SQLModel, table=True):
    organization_id: int = Field(primary_key=True)
    position_id: int = Field(primary_key=True)
    symbol: str
    account_login: Optional[str] = None
    server_name: Optional[str] = None
    entrytime: datetime
    exittime: datetime
    entryprice: float
    exitprice: float
    gross_pnl: float
    commission: float
    swap: float
    volume: float
    type_op: int # 0: Buy, 1: Sell
    direction: str # Buy or Sell
    exit_reason: int
    netpnl: float
    sl: float
    risk_price: float
    valid_sl: bool
    r_multiple: Optional[float] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    mae_r: Optional[float] = None
    mfe_r: Optional[float] = None
    tw_mae_r: Optional[float] = None
    tw_mfe_r: Optional[float] = None
    efficiency: Optional[float] = None
    magic_number: Optional[int] = None

    # SaaS specific columns
    user_notes: Optional[str] = None
    setup_tags: Optional[str] = None # JSON string array
    partials: Optional[str] = None # JSON string array representing partial exits
    m1_candles_json: Optional[str] = Field(default=None)

class CapitalLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(index=True)
    time: datetime
    amount: float
    note: str


class Organization(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    name: str
    owner_email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


class MacroNews(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(default=0, index=True) # 0 for global news
    title: str
    content: str
    published_at: datetime
    source: str
    url: Optional[str] = None
    impact_score: int # 1-10
    ai_interpretation: str
    ai_suggestion: str
    economic_event_key: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EconomicEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(default=0, index=True)
    event_key: str = Field(index=True, unique=True)
    title: str
    country: str
    currency: str
    scheduled_at: datetime = Field(index=True)
    impact: str
    impact_score: int
    forecast: Optional[str] = None
    previous: Optional[str] = None
    actual: Optional[str] = None
    source: str = "Fair Economy Calendar"
    released_to_feed: bool = Field(default=False, index=True)
    status: str = Field(default="scheduled", index=True)
    revision_count: int = 0
    surprise_value: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TradeJournal(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("organization_id", "position_id", name="uq_tradejournal_org_position"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(index=True)
    position_id: int = Field(index=True) # Linked to TradeArchive.position_id
    
    # Emotional Analysis
    emotional_state: int = Field(default=5) # 1-10
    emotional_tags: str = Field(default="") # Comma separated: FOMO, Calm, etc.
    
    # Qualitative Notes
    notes_pre: Optional[str] = None
    notes_during: Optional[str] = None
    notes_post: Optional[str] = None
    notes_general: Optional[str] = None
    
    # Technical Analysis (JSON string or separate logic)
    # Storing as JSON for flexibility in timeframes
    timeframe_data: str = Field(default="{}") 
    
    is_completed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ApiKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(index=True)
    key_id: str = Field(index=True)
    key_hash: str # For login/UI
    key_secret: str # Reversible or plain for HMAC verification
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: Optional[datetime] = None
    is_active: bool = True


class IngestionEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(index=True)
    event_id: str = Field(index=True)
    source: str = "mt5-agent"
    event_type: str = "trade"
    payload_json: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    status: str = "received"
    error_message: Optional[str] = None


class AccountSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(index=True)
    account_login: Optional[str] = Field(default=None, index=True)
    server_name: Optional[str] = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    balance: float
    equity: float
    margin: Optional[float] = None
    margin_free: Optional[float] = None
    margin_level: Optional[float] = None
    currency: Optional[str] = None


class Mt5Node(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(index=True)
    node_name: str
    terminal_path: Optional[str] = None
    account_login: Optional[str] = None
    server_name: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    is_active: bool = True

class BloombergSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(default=0, index=True) # 0 for global
    stress_prob: float
    narrative: str
    entropy: float = Field(default=0.42)
    confidence: float = Field(default=0.85)
    dominant_theme: str = Field(default="Stable")
    weights_json: str # JSON string for asset weights
    xi: float = Field(default=0.0)
    lambda_dominant: float = Field(default=0.0)
    entropy_spectral: float = Field(default=0.0)
    mtl: float = Field(default=0.0)
    kld: float = Field(default=0.0)
    top_highest_corr: str = Field(default="[]")
    top_lowest_corr: str = Field(default="[]")
    context_id: Optional[str] = Field(default=None, index=True)
    health_status: str = Field(default="degraded", index=True)
    source_health_json: str = Field(default="{}")
    model_version: Optional[str] = None
    feature_version: Optional[str] = None
    account_login: Optional[str] = Field(default=None, index=True)
    server_name: Optional[str] = None
    fallback_active: bool = False
    alternative_scenario: Optional[str] = Field(default=None)
    invalidation_conditions: Optional[str] = Field(default=None)
    evidence: Optional[str] = Field(default=None)
    account_implications: Optional[str] = Field(default=None)
    llm_model: Optional[str] = None
    prompt_version: Optional[str] = None
    context_sent: Optional[str] = None
    sources_used: Optional[str] = None
    api_latency_ms: Optional[int] = None
    call_cost_usd: Optional[float] = None
    prompt_hash: Optional[str] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



class SentinelContextSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    context_id: str = Field(index=True, unique=True)
    organization_id: int = Field(default=0, index=True)
    account_login: Optional[str] = Field(default=None, index=True)
    server_name: Optional[str] = None
    schema_version: str = "1.0"
    health_status: str = Field(default="degraded", index=True)
    payload_json: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class SentinelPrediction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prediction_id: str = Field(index=True, unique=True)
    context_id: Optional[str] = Field(default=None, index=True)
    organization_id: int = Field(default=0, index=True)
    account_login: Optional[str] = Field(default=None, index=True)
    model_version: Optional[str] = None
    feature_version: Optional[str] = None
    horizon_minutes: int = 5
    stress_probability: float
    confidence: Optional[float] = None
    regime_json: str = "{}"
    model_health_json: str = "{}"
    predicted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    evaluation_status: str = Field(default="pending", index=True)
    outcome_json: Optional[str] = None


class AIAuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    focus: str
    provider: str
    model: str
    status: str
    prompt_hash: str = Field(index=True)
    prompt_chars: int
    response_chars: int = 0
    latency_ms: int = 0
    account_login: Optional[str] = None
    server_name: Optional[str] = None
    selected_bot: Optional[int] = None
    error_message: Optional[str] = None


class PortfolioLimits(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    organization_id: int = Field(default=0, index=True) # 0 for global
    account_login: Optional[str] = Field(default=None, index=True)
    max_allocation_qqq: float = Field(default=0.40) # 40% default (conservative)
    max_allocation_gld: float = Field(default=0.20) # 20% default
    min_cash: float = Field(default=0.10) # 10% cash minimum
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

