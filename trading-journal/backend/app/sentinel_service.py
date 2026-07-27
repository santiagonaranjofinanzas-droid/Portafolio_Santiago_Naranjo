from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, select

from .database import engine
from .models import (
    AccountSnapshot,
    EconomicEvent,
    MacroNews,
    SentinelContextSnapshot,
    TradeArchive,
    PortfolioLimits,
)
from .settings import settings


def _utc_naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime  None) -> str  None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _age_seconds(value: datetime  None, now: datetime) -> int  None:
    if value is None:
        return None
    return max(0, int((now - value.replace(tzinfo=None)).total_seconds()))


def _health(age: int  None, ttl: int) -> str:
    if age is None:
        return "offline"
    if age <= ttl:
        return "healthy"
    if age <= ttl * 3:
        return "degraded"
    return "stale"


def build_sentinel_context(
    organization_id: int,
    account_login: str  None = None,
    server_name: str  None = None,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    now = _utc_naive_now()
    with Session(engine) as session:
        account_query = select(AccountSnapshot).where(AccountSnapshot.organization_id == organization_id)
        if account_login:
            account_query = account_query.where(AccountSnapshot.account_login == account_login)
        if server_name:
            account_query = account_query.where(AccountSnapshot.server_name == server_name)
        account = session.exec(account_query.order_by(AccountSnapshot.captured_at.desc())).first()

        resolved_login = account_login or (account.account_login if account else None)
        resolved_server = server_name or (account.server_name if account else None)

        event_rows = session.exec(
            select(EconomicEvent)
            .where(
                (EconomicEvent.organization_id == organization_id)  (EconomicEvent.organization_id == 0),
                EconomicEvent.scheduled_at >= now - timedelta(hours=24),
                EconomicEvent.scheduled_at <= now + timedelta(days=7),
            )
            .order_by(EconomicEvent.scheduled_at.asc())
        ).all()
        news_rows = session.exec(
            select(MacroNews)
            .where(
                (MacroNews.organization_id == organization_id)  (MacroNews.organization_id == 0),
                MacroNews.published_at >= now - timedelta(hours=36),
            )
            .order_by(MacroNews.published_at.desc())
            .limit(50)
        ).all()

        trades_query = select(TradeArchive).where(TradeArchive.organization_id == organization_id)
        if resolved_login:
            trades_query = trades_query.where(TradeArchive.account_login == resolved_login)
        if resolved_server:
            trades_query = trades_query.where(TradeArchive.server_name == resolved_server)
        recent_trades = session.exec(trades_query.order_by(TradeArchive.exittime.desc()).limit(100)).all()

        # Fetch the latest BloombergSnapshot
        from .models import BloombergSnapshot
        bloomberg_query = select(BloombergSnapshot).where(
            (BloombergSnapshot.organization_id == organization_id)  (BloombergSnapshot.organization_id == 0)
        )
        if resolved_login:
            bloomberg_query = bloomberg_query.where(
                (BloombergSnapshot.account_login == resolved_login)  (BloombergSnapshot.account_login == None)
            )
        latest_bloomberg = session.exec(bloomberg_query.order_by(BloombergSnapshot.updated_at.desc())).first()

        latest_event_update = max((row.updated_at for row in event_rows), default=None)
        latest_news = max((row.published_at for row in news_rows), default=None)
        account_age = _age_seconds(account.captured_at if account else None, now)
        event_age = _age_seconds(latest_event_update, now)
        news_age = _age_seconds(latest_news, now)
        quant_age = _age_seconds(latest_bloomberg.updated_at if latest_bloomberg else None, now)

        source_health = {
            "account": {"status": _health(account_age, 300), "age_seconds": account_age},
            "calendar": {"status": _health(event_age, settings.sentinel_context_ttl_seconds), "age_seconds": event_age},
            "news": {"status": _health(news_age, 43200), "age_seconds": news_age},
            "quant": {"status": _health(quant_age, 300), "age_seconds": quant_age},
        }
        critical_statuses = {source_health["account"]["status"], source_health["calendar"]["status"], source_health["quant"]["status"]}
        all_statuses = {item["status"] for item in source_health.values()}
        if "stale" in critical_statuses or "offline" in critical_statuses:
            health_status = "stale"
        elif all_statuses == {"healthy"}:
            health_status = "healthy"
        else:
            health_status = "degraded"

        symbol_counts: dict[str, int] = {}
        net_pnl_by_symbol: dict[str, float] = {}
        for trade in recent_trades:
            symbol_counts[trade.symbol] = symbol_counts.get(trade.symbol, 0) + 1
            net_pnl_by_symbol[trade.symbol] = net_pnl_by_symbol.get(trade.symbol, 0.0) + float(trade.netpnl or 0.0)

        # Resolve portfolio limits (account -> org -> global)
        limits_query = select(PortfolioLimits).where(
            (PortfolioLimits.organization_id == organization_id)  (PortfolioLimits.organization_id == 0)
        )
        if resolved_login:
            limits_query = limits_query.where(
                (PortfolioLimits.account_login == resolved_login)  (PortfolioLimits.account_login == None)
            )
        limits_list = session.exec(limits_query).all()
        
        # Sort by specificity: account specific -> org specific -> global
        def limit_priority(l):
            if l.account_login == resolved_login and resolved_login is not None:
                return 0
            if l.organization_id == organization_id and organization_id > 0:
                return 1
            return 2
        
        limits_list.sort(key=limit_priority)
        
        max_qqq = 0.40
        max_gld = 0.20
        min_cash = 0.10
        if limits_list:
            best = limits_list[0]
            max_qqq = best.max_allocation_qqq
            max_gld = best.max_allocation_gld
            min_cash = best.min_cash
            
        portfolio_limits = {
            "max_allocation_qqq": max_qqq,
            "max_allocation_gld": max_gld,
            "min_cash": min_cash
        }

        # Fetch open positions
        from .engine import get_live_positions_data
        df_live = get_live_positions_data(account_login=resolved_login, server_name=resolved_server)
        positions_list = []
        if df_live is not None and not df_live.empty:
            positions_list = df_live.to_dict(orient='records')

        account_payload = None
        if account:
            account_payload = {
                "account_login": account.account_login,
                "server_name": account.server_name,
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "margin_free": account.margin_free,
                "margin_level": account.margin_level,
                "currency": account.currency,
                "captured_at": _iso(account.captured_at),
                "data_age_seconds": account_age,
            }

        bloomberg_payload = None
        if latest_bloomberg:
            try:
                weights = json.loads(latest_bloomberg.weights_json)
            except Exception:
                weights = {}
            try:
                top_highest = json.loads(latest_bloomberg.top_highest_corr) if isinstance(latest_bloomberg.top_highest_corr, str) else latest_bloomberg.top_highest_corr
            except Exception:
                top_highest = latest_bloomberg.top_highest_corr
            try:
                top_lowest = json.loads(latest_bloomberg.top_lowest_corr) if isinstance(latest_bloomberg.top_lowest_corr, str) else latest_bloomberg.top_lowest_corr
            except Exception:
                top_lowest = latest_bloomberg.top_lowest_corr

            bloomberg_payload = {
                "stress_prob": latest_bloomberg.stress_prob,
                "narrative": latest_bloomberg.narrative,
                "entropy": latest_bloomberg.entropy,
                "confidence": latest_bloomberg.confidence,
                "dominant_theme": latest_bloomberg.dominant_theme,
                "weights": weights,
                "xi": latest_bloomberg.xi,
                "lambda_dominant": latest_bloomberg.lambda_dominant,
                "entropy_spectral": latest_bloomberg.entropy_spectral,
                "mtl": latest_bloomberg.mtl,
                "kld": latest_bloomberg.kld,
                "top_highest_corr": top_highest,
                "top_lowest_corr": top_lowest,
                "universe_version": latest_bloomberg.universe_version,
                "dataset_hash": latest_bloomberg.dataset_hash,
                "data_provider": latest_bloomberg.data_provider,
                "data_frequency": latest_bloomberg.data_frequency,
                "data_coverage": latest_bloomberg.data_coverage,
                "pct_imputed": latest_bloomberg.pct_imputed,
                "observations": latest_bloomberg.observations,
                "data_status": latest_bloomberg.data_status,
                "shadow_mode": latest_bloomberg.shadow_mode,
                "approval_status": latest_bloomberg.approval_status,
                "updated_at": _iso(latest_bloomberg.updated_at),
                "data_age_seconds": quant_age,
            }

        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "generated_at": _iso(now),
            "organization_id": organization_id,
            "scope": {"account_login": resolved_login, "server_name": resolved_server},
            "health_status": health_status,
            "source_health": source_health,
            "account": account_payload,
            "portfolio_limits": portfolio_limits,
            "positions": positions_list,
            "bloomberg": bloomberg_payload,
            "events": [
                {
                    "event_key": row.event_key,
                    "title": row.title,
                    "currency": row.currency,
                    "scheduled_at": _iso(row.scheduled_at),
                    "impact": row.impact,
                    "impact_score": row.impact_score,
                    "actual": row.actual,
                    "forecast": row.forecast,
                    "previous": row.previous,
                    "status": "released" if row.scheduled_at <= now else "scheduled",
                    "source": row.source,
                }
                for row in event_rows
            ],
            "news": [
                {
                    "id": row.id,
                    "title": row.title,
                    "source": row.source,
                    "published_at": _iso(row.published_at),
                    "impact_score": row.impact_score,
                    "interpretation": row.ai_interpretation,
                    "suggestion": row.ai_suggestion,
                    "url": row.url,
                }
                for row in news_rows
            ],
            "account_activity": {
                "sample_size": len(recent_trades),
                "symbols": [
                    {"symbol": symbol, "trade_count": count, "net_pnl": round(net_pnl_by_symbol.get(symbol, 0.0), 2)}
                    for symbol, count in sorted(symbol_counts.items(), key=lambda item: item[1], reverse=True)
                ],
            },
        }
        identity_basis = {
            "organization_id": organization_id,
            "scope": payload["scope"],
            "account_captured_at": account_payload.get("captured_at") if account_payload else None,
            "events": payload["events"],
            "news_ids": [row["id"] for row in payload["news"]],
            "account_activity": payload["account_activity"],
        }
        identity = json.dumps(identity_basis, sort_keys=True, separators=(",", ":"), default=str)
        context_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        payload["context_id"] = context_id

        if persist:
            existing = session.exec(select(SentinelContextSnapshot).where(SentinelContextSnapshot.context_id == context_id)).first()
            if existing is None:
                session.add(SentinelContextSnapshot(
                    context_id=context_id,
                    organization_id=organization_id,
                    account_login=resolved_login,
                    server_name=resolved_server,
                    health_status=health_status,
                    payload_json=json.dumps(payload, ensure_ascii=True),
                    generated_at=now,
                ))
                session.commit()

        return payload
