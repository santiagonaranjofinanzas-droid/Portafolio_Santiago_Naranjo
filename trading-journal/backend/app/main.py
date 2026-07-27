from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from .engine import calculate_stats, get_live_positions_data, get_trade_m1_data, get_db_data_for_metrics, calculate_trade_physics, _account_scope_condition
from .ai import AIRequest, AIRateLimitError, build_ai_response
from .database import create_db_and_tables, engine as db_engine, get_session
from .auth import verify_tenant_ingest, get_current_org_id, get_db
from .models import TradeArchive, IngestionEvent, TradeJournal, MacroNews, EconomicEvent, AccountSnapshot, Mt5Node, ApiKey, BloombergSnapshot, AIAuditEvent, SentinelPrediction
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from .macro_service import MacroService
from .sentinel_service import build_sentinel_context
import uvicorn
import os
import json
import glob
import re
import time
import secrets
import copy
from datetime import datetime, timedelta, timezone
from threading import Thread
import hashlib
import hmac
import pandas as pd
import logging

from .settings import settings
import subprocess

logger = logging.getLogger("black_knight.api")

def run_bloomberg_orchestrator():
    """Starts the cloud-native orchestrator for Macro Intel."""
    try:
        # Use sys.executable to run with the same python environment
        import sys
        orch_path = os.path.join(os.getcwd(), "backend", "bloomberg", "master_orchestrator.py")
        if not os.path.exists(orch_path):
            orch_path = os.path.join(os.getcwd(), "bloomberg", "master_orchestrator.py")
            
        if os.path.exists(orch_path):
            print(f"[STARTUP] Starting Sentinel Orchestrator: {orch_path}", flush=True)
            subprocess.Popen([sys.executable, orch_path], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL,
                             cwd=os.path.dirname(orch_path),
                             env=os.environ.copy())
        else:
            print(f"[STARTUP][WARN] Orchestrator not found at {orch_path}", flush=True)
    except Exception as e:
        print(f"[STARTUP][ERROR] Failed to start Bloomberg Orchestrator: {e}", flush=True)

from contextlib import asynccontextmanager

def _is_account_snapshot_payload(payload: dict) -> bool:
    return payload.get("event_type") == "account_snapshot" or (
        "balance" in payload and "equity" in payload and "position_id" not in payload
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("[STARTUP] Initializing Black Knight API...", flush=True)
    print(f"[STARTUP] Database backend: {settings.database_url.split(':', 1)[0]}", flush=True)
    print(f"[STARTUP] Socket enabled: {settings.enable_socket_server}", flush=True)

    try:
        create_db_and_tables()
        print("[STARTUP] Database schema ready.", flush=True)
    except Exception as e:
        print(f"[STARTUP][WARN] Database init failed: {e}", flush=True)

    if settings.enable_socket_server:
        try:
            Thread(target=start_socket_server, daemon=True).start()
            print("[STARTUP] Socket thread started.", flush=True)
        except Exception as e:
            print(f"[STARTUP][WARN] Socket thread failed: {e}", flush=True)
    else:
        print("Socket server disabled via BK_ENABLE_SOCKET_SERVER.", flush=True)
    
    if settings.enable_embedded_orchestrator:
        Thread(target=run_bloomberg_orchestrator, daemon=True).start()

    start_macro_updater()
    start_prediction_evaluator()
    
    yield
    # Shutdown logic (optional)
    print("[SHUTDOWN] Cleaning up...", flush=True)

app = FastAPI(title="Black_Knight_Quant MT5 Node API", version="1.0.0", lifespan=lifespan)



def _event_id_from_payload(payload: dict, explicit_event_id: str  None) -> str:
    if explicit_event_id:
        return explicit_event_id.strip()

    if _is_account_snapshot_payload(payload):
        login = str(payload.get("account_login", "unknown")).strip()
        captured_at = str(payload.get("captured_at", "na")).strip()
        return f"snapshot:{login}:{captured_at}"

    login = str(payload.get("account_login", "unknown")).strip()
    server = str(payload.get("server_name", "unknown")).strip()
    deal_ticket = str(payload.get("deal_ticket", "na")).strip()
    pid = str(payload.get("position_id", "unknown")).strip()
    exittime = str(payload.get("exittime", "na")).strip()
    return f"trade:{login}:{server}:{pid}:{deal_ticket}:{exittime}"


def _validate_trade_payload(payload: dict) -> None:
    pid = payload.get("position_id")
    if pid is None or str(pid).strip() == "":
        raise HTTPException(status_code=400, detail="Missing position_id for trade payload")

    try:
        int(pid)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid position_id for trade payload") from exc

    type_val = _coerce_int(payload.get("type_op"))
    if type_val is None:
        type_val = _coerce_int(payload.get("type"))

    if type_val == 2:
        required_fields = (
            "entrytime",
            "type_op",
        )
    else:
        required_fields = (
            "symbol",
            "entrytime",
            "exittime",
            "entryprice",
            "exitprice",
            "gross_pnl",
            "volume",
            "type_op",
            "netpnl",
            "exit_reason",
        )

    missing: list[str] = []
    for field in required_fields:
        value = payload.get(field)
        if value is None:
            missing.append(field)
            continue
        if isinstance(value, str) and value.strip() == "":
            missing.append(field)

    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing)}")


def _validate_snapshot_payload(payload: dict) -> None:
    if payload.get("balance") is None or payload.get("equity") is None:
        raise HTTPException(status_code=400, detail="Snapshot payload must include balance and equity")

    try:
        float(payload.get("balance"))
        float(payload.get("equity"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid snapshot balance/equity values") from exc


def _coerce_int(value) -> int  None:
    if value is None:
        return None
    try:
        return int(float(value))
    except:
        return None


def _coerce_float(value) -> float  None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _calculate_price_r_multiple(
    type_op,
    entryprice,
    exitprice,
    risk_price,
    valid_sl=True,
) -> float  None:
    type_val = _coerce_int(type_op)
    entry = _coerce_float(entryprice)
    exit_ = _coerce_float(exitprice)
    risk = _coerce_float(risk_price)
    if type_val not in (0, 1) or entry is None or exit_ is None or risk is None:
        return None
    if not _coerce_bool(valid_sl) or risk <= 0:
        return None
    direction_mult = 1.0 if type_val == 0 else -1.0
    return direction_mult * (exit_ - entry) / risk


def _refresh_trade_r_multiple(trade) -> None:
    r_multiple = _calculate_price_r_multiple(
        getattr(trade, "type_op", None),
        getattr(trade, "entryprice", None),
        getattr(trade, "exitprice", None),
        getattr(trade, "risk_price", None),
        getattr(trade, "valid_sl", None),
    )
    trade.r_multiple = r_multiple

class Mql5TradePayload(BaseModel):
    ticket: int # El identificador único de la ejecución (Deal)
    position_id: int # El identificador de la operación agrupada
    entry_type: int # 0: IN, 1: OUT, 2: INOUT, etc.
    symbol: str
    type: int # 0: Buy, 1: Sell
    volume: float
    price: float
    profit: float
    commission: float
    magic: int
    reason: int
    time: str
    organization_id: int
    swap: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    account_login: str  None = None
    server_name: str  None = None

@app.post("/api/v1/ingest/mql5")
async def ingest_mql5_trade(request: Request, payload: Mql5TradePayload, db: Session = Depends(get_db)):
    """Direct ingestion from MetaTrader 5 via WebRequest with API Key validation"""
    # 1. Validate API Key from header
    api_key_raw = request.headers.get("X-API-KEY")
    
    # Limpieza de la llave (MT5 a veces manda basura invisible)
    api_key_header = api_key_raw.strip().replace('"', '').replace("'", "") if api_key_raw else None
    
    # Diagnóstico reforzado
    print(f">>> [AUTH CHECK] Key received: [{api_key_header}]", flush=True)
    print(f">>> [AUTH CHECK] OrgID in payload: {payload.organization_id}", flush=True)

    if not api_key_header:
        print(">>> [AUTH FAILED] No X-API-KEY header found", flush=True)
        # Log to DB
        db.add(IngestionEvent(organization_id=payload.organization_id, event_id=f"auth_fail_{datetime.now(timezone.utc).timestamp()}", payload_json=f"Missing Header. Payload: {payload.json()}", status="auth_failed", error_message="Missing X-API-KEY header"))
        db.commit()
        raise HTTPException(status_code=401, detail="Missing X-API-KEY header")
    
    # Check if key exists
    target_org_id = payload.organization_id if payload.organization_id > 0 else 1

    key_record = db.exec(select(ApiKey).where(
        ApiKey.key_secret == api_key_header, 
        ApiKey.organization_id == target_org_id,
        ApiKey.is_active == True
    )).first()
    
    if not key_record:
        # LOG DE ERROR DEFINITIVO
        print(f">>> [AUTH FAILED] Key Mismatch! Received: [{api_key_header}] for OrgID {target_org_id}", flush=True)
        
        # Log to DB
        db.add(IngestionEvent(organization_id=target_org_id, event_id=f"auth_fail_{datetime.now(timezone.utc).timestamp()}", payload_json=f"Key Received: [{api_key_header}]. Payload: {payload.json()}", status="auth_failed", error_message="Key Mismatch"))
        db.commit()

        sample_key = db.exec(select(ApiKey).where(ApiKey.organization_id == target_org_id)).first()
        if sample_key:
            print(f">>> [AUTH DB HINT] Expected key starts with: [{sample_key.key_secret[:5]}...]", flush=True)
        
        raise HTTPException(status_code=401, detail="Invalid API Key or Organization ID mismatch")

    try:
        import json

        # Determine operation direction
        if payload.type == 0:
            direction = "Buy"
        elif payload.type == 1:
            direction = "Sell"
        elif payload.type == 2:
            direction = "Deposit" if payload.profit >= 0 else "Withdrawal"
        else:
            direction = "Other"
            
        time_obj = _parse_timestamp(payload.time)
        if time_obj is None:
            time_obj = datetime.strptime(payload.time, "%Y.%m.%d %H:%M:%S")

        event_id = f"mql5:{payload.ticket}"
        existing_event = db.exec(select(IngestionEvent).where(
            IngestionEvent.organization_id == payload.organization_id,
            IngestionEvent.event_id == event_id,
            IngestionEvent.source == "mql5-bridge",
        )).first()
        if existing_event and existing_event.status == "processed":
            return {"status": "duplicate", "ticket": payload.ticket, "position_id": payload.position_id}

        # Log event para rastrear tickets individuales y no duplicar syncs
        event = IngestionEvent(
            organization_id=payload.organization_id,
            event_id=event_id,
            source="mql5-bridge",
            event_type="trade",
            payload_json=payload.json(),
            status="processed",
            processed_at=datetime.now(timezone.utc)
        )
        db.add(event)

        # Upsert logic para agrupar en TradeArchive (Position)
        existing = db.exec(select(TradeArchive).where(
            TradeArchive.organization_id == payload.organization_id,
            TradeArchive.position_id == payload.position_id
        )).first()

        if payload.type == 2:
            # Operaciones de balance, se guardan tal cual
            if not existing:
                netpnl = payload.profit + payload.commission + payload.swap
                new_trade = TradeArchive(
                    organization_id=payload.organization_id,
                    position_id=payload.position_id,
                    symbol=payload.symbol,
                    entrytime=time_obj, exittime=time_obj,
                    entryprice=0, exitprice=0,
                    gross_pnl=payload.profit, commission=0, swap=0, volume=0,
                    type_op=payload.type, direction=direction, exit_reason=payload.reason,
                    netpnl=netpnl, sl=0, risk_price=0, valid_sl=False, magic_number=0,
                    account_login=payload.account_login, server_name=payload.server_name
                )
                db.add(new_trade)
        else:
            if not existing:
                risk_price = abs(payload.price - payload.sl) if payload.sl > 0 else 0.0
                # Crear la posición base
                existing = TradeArchive(
                    organization_id=payload.organization_id,
                    position_id=payload.position_id,
                    symbol=payload.symbol,
                    entrytime=time_obj, exittime=time_obj,
                    entryprice=payload.price, exitprice=payload.price,
                    gross_pnl=0, commission=0, swap=0, volume=payload.volume,
                    type_op=payload.type, direction=direction, exit_reason=payload.reason,
                    netpnl=0, sl=payload.sl, risk_price=risk_price, valid_sl=(payload.sl > 0), 
                    magic_number=payload.magic, partials="[]",
                    account_login=payload.account_login, server_name=payload.server_name
                )
                db.add(existing)

            # Si es Deal de Entrada (IN = 0)
            if payload.entry_type == 0:
                if existing.entrytime is None or time_obj < existing.entrytime:
                    existing.entrytime = time_obj
                if existing.volume and existing.volume > 0:
                    total_volume = existing.volume + payload.volume
                    if total_volume > 0:
                        existing.entryprice = (
                            (existing.entryprice * existing.volume) + (payload.price * payload.volume)
                        ) / total_volume
                    existing.volume = total_volume
                else:
                    existing.entryprice = payload.price
                    existing.volume = payload.volume
                if payload.sl > 0:
                    existing.sl = payload.sl
                    existing.valid_sl = True
                    existing.risk_price = abs(existing.entryprice - payload.sl)
                existing.commission += payload.commission
                existing.netpnl = existing.gross_pnl + existing.commission + existing.swap
                _refresh_trade_r_multiple(existing)
            
            # Si es Deal de Salida (OUT = 1)
            elif payload.entry_type in (1, 2):
                existing.exittime = time_obj
                existing.exit_reason = payload.reason
                existing.gross_pnl += payload.profit
                existing.commission += payload.commission
                existing.swap += payload.swap
                existing.netpnl = existing.gross_pnl + existing.commission + existing.swap
                if payload.sl > 0:
                    existing.sl = payload.sl
                    existing.valid_sl = True
                    existing.risk_price = abs(existing.entryprice - payload.sl)
                
                # Registrar el parcial en el historial JSON
                partials = json.loads(existing.partials) if existing.partials else []
                partials.append({
                    "ticket": payload.ticket,
                    "volume": payload.volume,
                    "price": payload.price,
                    "profit": payload.profit,
                    "commission": payload.commission,
                    "time": payload.time
                })
                existing.partials = json.dumps(partials)

                total_exit_volume = sum(p.get("volume", 0) for p in partials if p.get("volume") is not None)
                if total_exit_volume > 0:
                    weighted_exit = sum(
                        (p.get("price", 0) or 0) * (p.get("volume", 0) or 0) for p in partials
                    )
                    existing.exitprice = weighted_exit / total_exit_volume
                else:
                    existing.exitprice = payload.price
                _refresh_trade_r_multiple(existing)
                
                # Trigger advanced physics calculation (MAE/MFE)
                try:
                    import pandas as pd
                    from .engine import get_trade_m1_data
                    
                    rates = None
                    if existing.m1_candles_json:
                        try:
                            rates = json.loads(existing.m1_candles_json)
                        except Exception:
                            rates = None
                    
                    if not rates:
                        rates = get_trade_m1_data(existing.symbol, existing.entrytime, existing.exittime)
                        if rates:
                            existing.m1_candles_json = json.dumps(rates)
                    
                    # Convert to Series-like dict for engine compatibility
                    trade_row = {
                        'symbol': existing.symbol,
                        'entrytime': existing.entrytime,
                        'exittime': existing.exittime,
                        'entryprice': existing.entryprice,
                        'exitprice': existing.exitprice,
                        'type_op': existing.type_op,
                        'sl': existing.sl or 0.0,
                        'netpnl': existing.netpnl or 0.0,
                        'volume': existing.volume or 0.01
                    }
                    physics = calculate_trade_physics(trade_row, rates_list=rates)
                    existing.mae = float(physics['mae']) if not pd.isna(physics['mae']) else None
                    existing.mfe = float(physics['mfe']) if not pd.isna(physics['mfe']) else None
                    existing.mae_r = float(physics['mae_r']) if not pd.isna(physics['mae_r']) else None
                    existing.mfe_r = float(physics['mfe_r']) if not pd.isna(physics['mfe_r']) else None
                    existing.efficiency = float(physics['efficiency']) if not pd.isna(physics['efficiency']) else None
                except Exception as phys_err:
                    print(f"Physics calc failed for {payload.position_id}: {phys_err}")

        db.commit()
        return {"status": "success", "ticket": payload.ticket, "position_id": payload.position_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sync/status/{organization_id}")
async def get_sync_status(organization_id: int, db: Session = Depends(get_db)):
    """Returns a list of all Deal Tickets already synced for this organization"""
    events = db.exec(select(IngestionEvent.event_id).where(
        IngestionEvent.organization_id == organization_id,
        IngestionEvent.source == "mql5-bridge"
    )).all()
    # event_id format: "mql5:{ticket}"
    tickets = [int(e.split(":")[1]) for e in events if ":" in e]
    return {"synced_ids": tickets}


def _coerce_bool(value) -> bool  None:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        if value != value:
            return None
        return bool(int(value))

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _normalize_text(value) -> str  None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _parse_timestamp(value) -> datetime  None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 1e12:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)
        except Exception:
            return None

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(".", "-")
    try:
        iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(iso_text)
    except Exception:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _extract_trade_bot_id(payload: dict) -> int  None:
    candidate_keys = (
        "entry_magic",
        "open_magic",
        "entry_bot_id",
        "magic_number",
        "exit_magic",
        "magic",
        "magicNumber",
        "bot_id",
        "botId",
        "ea_id",
        "expert_id",
    )

    for key in candidate_keys:
        parsed = _coerce_int(payload.get(key))
        if parsed is not None:
            return parsed

    # Fallback: detect from comment text patterns like "bot 29201" or "magic=30001".
    comment_keys = ("comment", "deal_comment", "order_comment", "expert_comment", "user_notes")
    for key in comment_keys:
        raw = payload.get(key)
        if raw is None:
            continue
        text = str(raw)
        match = re.search(r"(?:botnodemagic)[^0-9]{0,8}(\d{2,10})", text, flags=re.IGNORECASE)
        if match:
            parsed = _coerce_int(match.group(1))
            if parsed is not None:
                return parsed

    return None


def _normalize_trade_payload(trade_data: dict) -> dict:
    normalized = dict(trade_data)
    normalized["position_id"] = _coerce_int(normalized.get("position_id"))
    normalized["type_op"] = _coerce_int(normalized.get("type_op"))
    if normalized["type_op"] is None and normalized.get("type") is not None:
        normalized["type_op"] = _coerce_int(normalized.get("type"))

    type_op = normalized["type_op"]
    if type_op == 2:
        if not normalized.get("symbol"):
            normalized["symbol"] = "DEPOSIT"
        if not normalized.get("exittime"):
            normalized["exittime"] = normalized.get("entrytime") or normalized.get("time")

    normalized["magic_number"] = _extract_trade_bot_id(normalized)
    normalized["account_login"] = _normalize_text(normalized.get("account_login"))
    normalized["server_name"] = _normalize_text(normalized.get("server_name"))
    normalized["valid_sl"] = _coerce_bool(normalized.get("valid_sl"))

    if normalized.get("commission") is None:
        normalized["commission"] = 0.0
    if normalized.get("swap") is None:
        normalized["swap"] = 0.0
    if normalized.get("sl") is None:
        normalized["sl"] = 0.0

    sl_val = _coerce_float(normalized.get("sl"))
    if sl_val is None or sl_val == 0.0:
        normalized["risk_price"] = 0.0
        normalized["valid_sl"] = False
    else:
        normalized["valid_sl"] = True
        entry_price = _coerce_float(normalized.get("entryprice"))
        if entry_price is not None:
            normalized["risk_price"] = abs(entry_price - sl_val)
        else:
            normalized["risk_price"] = 0.0

    if normalized.get("netpnl") is None:
        gross = _coerce_float(normalized.get("gross_pnl"))
        if gross is None:
            gross = _coerce_float(normalized.get("profit"))
        commission = _coerce_float(normalized.get("commission")) or 0.0
        swap = _coerce_float(normalized.get("swap")) or 0.0
        normalized["netpnl"] = (gross or 0.0) + commission + swap

    if not normalized.get("direction") and normalized.get("type_op") in (0, 1):
        normalized["direction"] = "Buy" if normalized.get("type_op") == 0 else "Sell"

    r_multiple = _calculate_price_r_multiple(
        normalized.get("type_op"),
        normalized.get("entryprice"),
        normalized.get("exitprice"),
        normalized.get("risk_price"),
        normalized.get("valid_sl"),
    )
    normalized["r_multiple"] = r_multiple

    # Normalize partials to a valid JSON string
    import json
    partials_val = normalized.get("partials")
    if isinstance(partials_val, list):
        normalized["partials"] = json.dumps(partials_val)
    elif isinstance(partials_val, str) and partials_val.strip() != "":
        try:
            json.loads(partials_val)
            normalized["partials"] = partials_val
        except Exception:
            normalized["partials"] = "[]"
    else:
        normalized["partials"] = "[]"

    # Drop aliases so the SQLModel payload uses one canonical field.
    for alias in ("magic", "magicNumber", "bot_id", "botId", "ea_id", "expert_id"):
        normalized.pop(alias, None)

    return normalized


#Signature verification moved to auth.py


#Shared logic for both API and Socket ingestion
def process_trade_ingestion(trade_data: dict, session, organization_id: int):
    from .models import TradeArchive
    allowed_fields = set(getattr(TradeArchive, "model_fields", {}).keys())
    normalized_trade_data = {
        key: value
        for key, value in _normalize_trade_payload(trade_data).items()
        if key in allowed_fields
    }

    pid_raw = normalized_trade_data.get("position_id")
    if pid_raw is None or str(pid_raw).strip() == "":
        raise HTTPException(status_code=400, detail="Missing position_id for trade payload")
    try:
        pid = int(pid_raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid position_id for trade payload") from exc

    type_op = normalized_trade_data.get("type_op")
    if type_op is None:
        raise HTTPException(status_code=400, detail="Invalid type_op for trade payload")

    if not normalized_trade_data.get("direction") and type_op in (0, 1):
        normalized_trade_data["direction"] = "Buy" if type_op == 0 else "Sell"
    
    # Normalize dates
    for key in ["entrytime", "exittime"]:
        parsed = _parse_timestamp(normalized_trade_data.get(key))
        if parsed is not None:
            normalized_trade_data[key] = parsed

    existing = session.get(TradeArchive, (organization_id, pid))
    incoming_magic = _coerce_int(normalized_trade_data.get("magic_number"))

    if existing:
        # Overwrite semantics per position_id. Replay-safe when EA payload is cumulative per position.
        for key, value in normalized_trade_data.items():
            if key == "magic_number":
                continue
            if hasattr(existing, key):
                setattr(existing, key, value)

        current_magic = _coerce_int(getattr(existing, "magic_number", None))
        if incoming_magic is not None and (current_magic is None or current_magic == 0 or incoming_magic != 0):
            existing.magic_number = incoming_magic
    else:
        normalized_trade_data["organization_id"] = organization_id
        if incoming_magic is not None:
            normalized_trade_data["magic_number"] = incoming_magic
        existing = TradeArchive(**normalized_trade_data)

    # Trigger advanced physics calculation (MAE/MFE) if exit data is available
    if existing and existing.exittime and existing.entryprice and existing.exitprice:
        _refresh_trade_r_multiple(existing)
        try:
            from .engine import calculate_trade_physics, get_trade_m1_data
            import json
            
            rates = None
            if existing.m1_candles_json:
                try:
                    rates = json.loads(existing.m1_candles_json)
                except Exception:
                    rates = None
            
            if not rates:
                rates = get_trade_m1_data(existing.symbol, existing.entrytime, existing.exittime)
                if rates:
                    existing.m1_candles_json = json.dumps(rates)
            
            # Convert to Series-like dict for engine compatibility
            trade_row = {
                'symbol': existing.symbol,
                'entrytime': existing.entrytime,
                'exittime': existing.exittime,
                'entryprice': existing.entryprice,
                'exitprice': existing.exitprice,
                'type_op': existing.type_op,
                'sl': existing.sl or 0.0,
                'netpnl': existing.netpnl or 0.0,
                'volume': existing.volume or 0.01
            }
            physics = calculate_trade_physics(trade_row, rates_list=rates)
            existing.mae = float(physics['mae']) if not pd.isna(physics['mae']) else None
            existing.mfe = float(physics['mfe']) if not pd.isna(physics['mfe']) else None
            existing.mae_r = float(physics['mae_r']) if not pd.isna(physics['mae_r']) else None
            existing.mfe_r = float(physics['mfe_r']) if not pd.isna(physics['mfe_r']) else None
            existing.efficiency = float(physics['efficiency']) if not pd.isna(physics['efficiency']) else None
        except Exception as phys_err:
            print(f"Physics calc failed for {pid}: {phys_err}")

    session.add(existing)
    session.commit()
    print(f"Ingested Trade: {pid}  Symbol: {normalized_trade_data.get('symbol')}  Bot ID: {incoming_magic}", flush=True)


def process_account_snapshot_ingestion(snapshot_data: dict, session, organization_id: int):
    from .models import AccountSnapshot

    captured_at = snapshot_data.get("captured_at")
    parsed_captured = _parse_timestamp(captured_at)
    snapshot_data["captured_at"] = parsed_captured or datetime.now(timezone.utc)

    row = AccountSnapshot(
        organization_id=organization_id,
        account_login=_normalize_text(snapshot_data.get("account_login")),
        server_name=_normalize_text(snapshot_data.get("server_name")),
        captured_at=snapshot_data["captured_at"],
        balance=float(snapshot_data.get("balance", 0.0)),
        equity=float(snapshot_data.get("equity", 0.0)),
        margin=float(snapshot_data.get("margin", 0.0)) if snapshot_data.get("margin") is not None else None,
        margin_free=float(snapshot_data.get("margin_free", 0.0)) if snapshot_data.get("margin_free") is not None else None,
        margin_level=float(snapshot_data.get("margin_level", 0.0)) if snapshot_data.get("margin_level") is not None else None,
        currency=str(snapshot_data.get("currency", "")) or None,
    )
    session.add(row)
    session.commit()
    print(f"Ingested AccountSnapshot: balance={row.balance} equity={row.equity}", flush=True)

def start_socket_server():
    """Bulletproof TCP bridge for MT5 -> Python bypasses all WebRequest/Proxy blocks."""
    import socket
    from sqlmodel import Session
    from .database import engine as db_engine
    
    server_ip = settings.socket_ip
    server_port = settings.socket_port
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((server_ip, server_port))
        server.listen(5)
        print(f"Black Knight SOCKET Server listening on {server_ip}:{server_port}", flush=True)
        
        while True:
            conn, addr = server.accept()
            try:
                data = conn.recv(8192).decode('utf-8').strip('\x00').strip()
                if data:
                    trade_json = json.loads(data)
                    with Session(db_engine) as session:
                        process_trade_ingestion(trade_json, session, settings.default_org_id)
                conn.sendall(b"OK")
            except Exception as e:
                print(f"Socket Data Error: {e}", flush=True)
            finally:
                conn.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"Socket Critical Error: {e}", flush=True)
    finally:
        server.close()

def start_ipc_watcher():
    """Background thread to process MQL5 IPC JSON drops."""
    from .models import TradeArchive
    from sqlmodel import Session
    from .database import engine as db_engine
    
    appdata = os.environ.get('APPDATA')
    # STRICT IPC: Use the Common folder which is predictable across all MT5 instances
    common_ipc_path = os.path.join(appdata, "MetaQuotes", "Terminal", "Common", "Files", "BlackKnight")
    
    # Ensure the directory exists
    os.makedirs(common_ipc_path, exist_ok=True)
    print(f"Black Knight IPC Watcher started on Common Path: {common_ipc_path}", flush=True)
    
    while True:
        try:
            # Poll ONLY the common folder (MQL5 v2.2 forced output)
            files = glob.glob(os.path.join(common_ipc_path, "*.json"))
                
            if files:
                with Session(db_engine) as session:
                    for file_path in files:
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                trade_data = json.load(f)
                            
                            for key in ["entrytime", "exittime"]:
                                if isinstance(trade_data.get(key), str):
                                    try:
                                        trade_data[key] = datetime.strptime(trade_data[key].replace(".", "-"), "%Y-%m-%d %H:%M:%S")
                                    except: pass
                            
                            pid = int(trade_data.get("position_id", 0))
                            if pid > 0:
                                existing = session.get(TradeArchive, (settings.default_org_id, pid))
                                if existing:
                                    for key, value in trade_data.items():
                                        if hasattr(existing, key):
                                            setattr(existing, key, value)
                                else:
                                    new_trade = TradeArchive(organization_id=settings.default_org_id, **trade_data)
                                    session.add(new_trade)
                                
                                session.commit()
                            
                            os.remove(file_path) # Telemetry consumed
                            print(f"IPC Ingested: {os.path.basename(file_path)}", flush=True)
                        except Exception as inner_e:
                            print(f"IPC Parse Error for {file_path}: {inner_e}", flush=True)
                            try:
                                os.rename(file_path, file_path + ".err")
                            except: pass
        except Exception as e:
            print(f"IPC Watcher Error: {e}", flush=True)
        
        time.sleep(1) # Poll every second

#Startup logic moved to lifespan handler

#CORS for Next.js communication
cors_allow_credentials = "*" not in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        int((time.perf_counter() - started) * 1000),
    )
    return response

@app.get("/health")
def health():
    from sqlalchemy import text
    checks = {"database": False, "sentinel": False}
    details = {}
    try:
        with Session(db_engine) as session:
            session.exec(text("SELECT 1")).one()
            checks["database"] = True
            latest = session.exec(select(BloombergSnapshot).order_by(BloombergSnapshot.updated_at.desc())).first()
            if latest and latest.updated_at:
                updated = latest.updated_at.replace(tzinfo=timezone.utc) if latest.updated_at.tzinfo is None else latest.updated_at
                age_seconds = max(0, int((datetime.now(timezone.utc) - updated).total_seconds()))
                details["sentinel_age_seconds"] = age_seconds
                checks["sentinel"] = age_seconds <= 3600
    except Exception as exc:
        details["database_error"] = str(exc)[:200]
    status = "healthy" if checks["database"] else "unhealthy"
    return {
        "status": status,
        "checks": checks,
        "details": details,
        "socket_server_enabled": settings.enable_socket_server,
        "embedded_orchestrator": settings.enable_embedded_orchestrator,
    }

@app.post("/api/v1/sync")
def sync_data():
    """Disabled manual sync - Now use IPC only for data integrity"""
    return {"status": "warning", "message": "Manual sync disabled. Use Black Knight MQL5 EA for live telemetry."}

@app.post("/api/v1/ingest/trade")
async def ingest_trade(request: Request):
    """Entry point for MQL5 Reporter EA WebRequest. Ultra-robust ingestion."""
    from sqlmodel import Session, select
    from .database import engine as db_engine
    from .models import IngestionEvent
    
    try:
        raw_body = await request.body()
        if not raw_body:
            raise HTTPException(status_code=400, detail="Missing request body")

        with Session(db_engine) as session:
            org_id = verify_tenant_ingest(request, raw_body, session)

            try:
                trade_data = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

            if not isinstance(trade_data, dict):
                raise HTTPException(status_code=400, detail="Trade payload must be a JSON object")

            event_id = _event_id_from_payload(trade_data, request.headers.get("X-BK-Event-Id"))
            event_type = "account_snapshot" if _is_account_snapshot_payload(trade_data) else "trade"

            if event_type == "account_snapshot":
                _validate_snapshot_payload(trade_data)
            else:
                _validate_trade_payload(trade_data)

            existing_event = session.exec(
                select(IngestionEvent).where(
                    IngestionEvent.organization_id == org_id,
                    IngestionEvent.event_id == event_id,
                )
            ).first()

            if existing_event and existing_event.status == "processed":
                return {
                    "status": "duplicate",
                    "event_id": event_id,
                    "position_id": trade_data.get("position_id"),
                }

            if existing_event is None:
                ingestion_event = IngestionEvent(
                    organization_id=org_id,
                    event_id=event_id,
                    event_type=event_type,
                    payload_json=raw_body.decode("utf-8"),
                    status="received",
                )
                session.add(ingestion_event)
                session.commit()
            else:
                ingestion_event = existing_event

            if event_type == "account_snapshot":
                process_account_snapshot_ingestion(trade_data, session, org_id)
            else:
                process_trade_ingestion(trade_data, session, org_id)

            ingestion_event.status = "processed"
            ingestion_event.processed_at = datetime.now(timezone.utc)
            ingestion_event.error_message = None
            session.add(ingestion_event)
            session.commit()

        return {
            "status": "success",
            "event_id": event_id,
            "event_type": event_type,
            "position_id": trade_data.get("position_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Ingestion HTTP Error: {e}")
        try:
            from sqlmodel import Session, select
            from .database import engine as db_engine
            from .models import IngestionEvent

            raw_body = await request.body()
            fallback_trade_data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            event_id = _event_id_from_payload(fallback_trade_data if isinstance(fallback_trade_data, dict) else {}, request.headers.get("X-BK-Event-Id"))

            with Session(db_engine) as session:
                event_row = session.exec(
                    select(IngestionEvent).where(
                        IngestionEvent.organization_id == settings.default_org_id,
                        IngestionEvent.event_id == event_id,
                    )
                ).first()
                if event_row:
                    event_row.status = "error"
                    event_row.error_message = str(e)[:500]
                    session.add(event_row)
                    session.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

_METRICS_CACHE = {}

def _snapshot_payload(latest_snapshot):
    if latest_snapshot is None:
        return None

    server = getattr(latest_snapshot, "server_name", None)
    srv_lower = server.lower() if server else ""
    is_demo = any(x in srv_lower for x in ["demo", "stage", "test", "contest", "practice", "ctrader"])
    account_type = "Demo" if is_demo else "Real"

    return {
        "balance": latest_snapshot.balance,
        "equity": latest_snapshot.equity,
        "captured_at": latest_snapshot.captured_at,
        "currency": latest_snapshot.currency,
        "account_login": getattr(latest_snapshot, "account_login", None),
        "server_name": server,
        "account_type": account_type
    }


def _metrics_cache_get(cache_key: str):
    cached = _METRICS_CACHE.get(cache_key)
    if cached is None:
        return None
    return copy.deepcopy(cached)


def _metrics_cache_set(cache_key: str, stats: dict) -> None:
    if len(_METRICS_CACHE) > 100:
        _METRICS_CACHE.clear()
    _METRICS_CACHE[cache_key] = copy.deepcopy(stats)


@app.get("/api/v1/metrics")
def get_metrics(
    bot_id: int  None = None, 
    days: int  None = None, 
    account_login: str  None = None,
    server_name: str  None = None,
    org_id: int = Depends(get_current_org_id)
):
    """Reads strictly from Database. Insanely fast, unbrickable by MT5."""
    try:
        from sqlmodel import Session, select
        from sqlalchemy import func
        from .database import engine as db_engine
        from .models import AccountSnapshot, TradeArchive

        latest_snapshot = None
        active_account_login = account_login
        active_server_name = server_name

        # If manual account not specified, fallback to latest snapshot
        if not active_account_login:
            with Session(db_engine) as session:
                latest_snapshot = session.exec(
                    select(AccountSnapshot)
                    .where(AccountSnapshot.organization_id == org_id)
                    .order_by(AccountSnapshot.captured_at.desc())
                ).first()

            if latest_snapshot is not None:
                active_account_login = _normalize_text(getattr(latest_snapshot, "account_login", None))
                active_server_name = _normalize_text(getattr(latest_snapshot, "server_name", None))
        else:
            # Fetch latest snapshot specifically for this account_login/server_name
            with Session(db_engine) as session:
                latest_snapshot_query = select(AccountSnapshot).where(
                    AccountSnapshot.organization_id == org_id,
                    AccountSnapshot.account_login == active_account_login
                )
                if active_server_name:
                    latest_snapshot_query = latest_snapshot_query.where(AccountSnapshot.server_name == active_server_name)
                latest_snapshot = session.exec(
                    latest_snapshot_query.order_by(AccountSnapshot.captured_at.desc())
                ).first()

        include_unscoped = (account_login is None)
        scope_condition = _account_scope_condition(active_account_login, active_server_name, include_unscoped=include_unscoped)

        if days is not None:
            try:
                days = int(days)
            except Exception:
                days = None

        if days is not None and days <= 0:
            days = None

        if days is not None:
            days = min(days, 3650)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days is not None else None
        cutoff_compare = cutoff.replace(tzinfo=None) if cutoff is not None else None

        with Session(db_engine) as session:
            trade_sig_stmt = select(
                func.count(TradeArchive.position_id),
                func.max(TradeArchive.exittime),
                func.coalesce(func.sum(TradeArchive.netpnl), 0.0),
            ).where(
                TradeArchive.organization_id == org_id,
                TradeArchive.type_op != 2,
            )
            deposit_sig_stmt = select(
                func.count(TradeArchive.position_id),
                func.max(TradeArchive.entrytime),
                func.coalesce(func.sum(TradeArchive.netpnl), 0.0),
            ).where(
                TradeArchive.organization_id == org_id,
                TradeArchive.type_op == 2,
            )
            bots_stmt = select(TradeArchive.magic_number).distinct().where(TradeArchive.organization_id == org_id)

            if scope_condition is not None:
                trade_sig_stmt = trade_sig_stmt.where(scope_condition)
                deposit_sig_stmt = deposit_sig_stmt.where(scope_condition)
                bots_stmt = bots_stmt.where(scope_condition)
            if bot_id is not None:
                trade_sig_stmt = trade_sig_stmt.where(TradeArchive.magic_number == bot_id)
            if cutoff is not None:
                trade_sig_stmt = trade_sig_stmt.where(TradeArchive.entrytime >= cutoff)

            trade_count, last_trade_time, window_net_profit = session.exec(trade_sig_stmt).one()
            dep_count, last_dep_time, total_deposits = session.exec(deposit_sig_stmt).one()
            bots = session.exec(bots_stmt).all()

        snapshot_key = ""
        if latest_snapshot is not None:
            snapshot_key = f"{latest_snapshot.balance}:{latest_snapshot.account_login}:{latest_snapshot.server_name}"

        cache_key = ":".join(
            [
                str(org_id),
                str(bot_id),
                str(days),
                str(active_account_login),
                str(active_server_name),
                str(trade_count),
                str(last_trade_time),
                str(round(float(window_net_profit or 0.0), 8)),
                str(dep_count),
                str(last_dep_time),
                str(round(float(total_deposits or 0.0), 8)),
                snapshot_key,
            ]
        )

        cached_stats = _metrics_cache_get(cache_key)
        if cached_stats is not None:
            cached_stats["cached"] = True
            cached_stats["available_bots"] = sorted({int(b) for b in bots if b is not None})
            cached_stats["selected_bot"] = bot_id
            snapshot = _snapshot_payload(latest_snapshot)
            if snapshot is not None:
                cached_stats["account_snapshot"] = snapshot
            return cached_stats

        df = get_db_data_for_metrics(
            organization_id=org_id,
            bot_id=bot_id,
            account_login=active_account_login,
            server_name=active_server_name,
            days=days,
            include_unscoped=include_unscoped,
        )

        # If no trades in DB, return empty state
        if df is None or df.empty:
            empty_response = {
                "summary": { "sqn": 0, "expectancy": 0, "sharpe": 0, "net_profit": 0, "start_cap": 0, "total_return": 0 },
                "perf": {
                    "cagr": 0,
                    "pf": 0,
                    "profit_factor": 0,
                    "calmar": 0,
                    "win_rate": 0,
                    "payoff": 0,
                    "max_drawdown": 0,
                    "max_drawdown_cash": 0,
                    "recovery_factor": 0,
                    "optimal_risk_kelly": 0,
                    "suggested_risk_half_kelly": 0,
                    "trades_per_year": 0,
                    "tail_ratio": 0,
                },
                "risk": {
                    "avg_risk": 0,
                    "max_risk": 0,
                    "var": 0,
                    "cvar": 0,
                    "cf_var": 0,
                    "garch_var": 0,
                    "vol_regime": "Stable",
                },
                "quant": {
                    "skewness": 0,
                    "kurtosis": 0,
                    "jarque_bera_stat": 0,
                    "jarque_bera_pvalue": 1,
                    "is_normal": True,
                    "psr": 0,
                    "significance": "Low (Noise)",
                    "runs_zscore": 0,
                    "serial_independent": True,
                    "mc_dd_p10": 0,
                    "mc_dd_p1": 0,
                    "prob_ruin_10pct": 0,
                    "prob_ruin_20pct": 0,
                    "e_ratio": None,
                    "commission_drag_pct": 0,
                },
                "history": [],
                "equity_curve": [],
                "available_bots": [],
                "selected_bot": bot_id,
            }
            if latest_snapshot is not None:
                empty_response["account_snapshot"] = _snapshot_payload(latest_snapshot)
            return empty_response

        start_cap = settings.initial_balance
        capital_source = "configured" if start_cap else "unavailable"
        window_net_profit = float(df['netpnl'].sum()) if 'netpnl' in df.columns else 0.0
        window_deposits = 0.0

        with Session(db_engine) as session:
            # PnL solo suma operaciones de trading (Buy/Sell = 0/1)
            net_profit_stmt = select(func.coalesce(func.sum(TradeArchive.netpnl), 0.0)).where(
                TradeArchive.organization_id == org_id,
                TradeArchive.type_op != 2
            )
            
            # Depósitos/Retiros (Balance = 2)
            deposits_stmt = select(func.coalesce(func.sum(TradeArchive.netpnl), 0.0)).where(
                TradeArchive.organization_id == org_id,
                TradeArchive.type_op == 2
            )
            
            if active_account_login:
                net_profit_stmt = net_profit_stmt.where(TradeArchive.account_login == active_account_login)
                deposits_stmt = deposits_stmt.where(TradeArchive.account_login == active_account_login)

            if active_server_name:
                net_profit_stmt = net_profit_stmt.where(TradeArchive.server_name == active_server_name)
                deposits_stmt = deposits_stmt.where(TradeArchive.server_name == active_server_name)

            if days is not None:
                window_deposits_stmt = select(func.coalesce(func.sum(TradeArchive.netpnl), 0.0)).where(
                    TradeArchive.organization_id == org_id,
                    TradeArchive.type_op == 2,
                    TradeArchive.entrytime >= cutoff,
                )
                if active_account_login:
                    window_deposits_stmt = window_deposits_stmt.where(TradeArchive.account_login == active_account_login)
                if active_server_name:
                    window_deposits_stmt = window_deposits_stmt.where(TradeArchive.server_name == active_server_name)
                window_deposits = float(session.exec(window_deposits_stmt).one())

            global_net_profit = session.exec(net_profit_stmt).one()
            total_deposits = session.exec(deposits_stmt).one()

            # Fetch all balance/deposit transactions sorted by time
            all_dep_stmt = select(TradeArchive).where(
                TradeArchive.organization_id == org_id,
                TradeArchive.type_op == 2
            ).order_by(TradeArchive.entrytime.asc())
            
            if active_account_login:
                all_dep_stmt = all_dep_stmt.where(TradeArchive.account_login == active_account_login)
            if active_server_name:
                all_dep_stmt = all_dep_stmt.where(TradeArchive.server_name == active_server_name)
                
            dep_records = session.exec(all_dep_stmt).all()
            
            initial_deposit_val = 0.0
            initial_deposit_time = None
            subsequent_records = []
            
            if dep_records:
                # The first deposit is the real Initial Capital
                initial_deposit_val = float(dep_records[0].netpnl)
                initial_deposit_time = dep_records[0].entrytime
                # Subsequent records are active capital flows (deposits/withdrawals)
                subsequent_records = dep_records[1:]

            window_subsequent_records = [
                record
                for record in subsequent_records
                if cutoff_compare is None or record.entrytime >= cutoff_compare
            ]
            funding_in_window = bool(
                initial_deposit_val > 0
                and (
                    cutoff_compare is None
                    or (initial_deposit_time is not None and initial_deposit_time >= cutoff_compare)
                )
            )
                
            # Determine start_cap dynamically
            if days is None:
                if initial_deposit_val > 0:
                    start_cap = initial_deposit_val
                    capital_source = "first_balance_operation"
                elif latest_snapshot is not None:
                    # Fallback if no balance deals are in TradeArchive
                    start_cap = float(latest_snapshot.balance) - float(global_net_profit or 0.0)
                    capital_source = "reconstructed_from_latest_snapshot"
                else:
                    start_cap = settings.initial_balance
            else:
                # A positive first balance operation is the funded account baseline,
                # not a flow that should be subtracted from that same baseline.
                if funding_in_window:
                    start_cap = initial_deposit_val
                    capital_source = "first_balance_operation"
                elif latest_snapshot is not None:
                    window_flow_total = sum(float(record.netpnl or 0.0) for record in window_subsequent_records)
                    start_cap = float(latest_snapshot.balance) - (window_net_profit + window_flow_total)
                    capital_source = "reconstructed_window_from_latest_snapshot"
                else:
                    start_cap = (
                        settings.initial_balance
                        if settings.initial_balance is not None
                        else None
                    )

            # Only include external flows that occur inside the analyzed window.
            df_deposits_detailed = pd.DataFrame([r.dict() for r in window_subsequent_records]) if window_subsequent_records else pd.DataFrame()
            if not df_deposits_detailed.empty:
                # Rename to match engine expectations: Fecha, Monto
                df_deposits_detailed = df_deposits_detailed.rename(columns={'entrytime': 'Fecha', 'netpnl': 'Monto'})

            reconciliation_gap = 0.0
            if latest_snapshot is not None and start_cap is not None:
                included_flows = sum(float(record.netpnl or 0.0) for record in window_subsequent_records)
                projected_balance = float(start_cap) + window_net_profit + included_flows
                reconciliation_gap = float(latest_snapshot.balance) - projected_balance
                if abs(reconciliation_gap) >= 0.005:
                    adjustment = pd.DataFrame([
                        {
                            'Fecha': latest_snapshot.captured_at,
                            'Monto': reconciliation_gap,
                            'Nota': 'MT5 balance reconciliation',
                        }
                    ])
                    df_deposits_detailed = pd.concat([df_deposits_detailed, adjustment], ignore_index=True)

        analysis_start_time = initial_deposit_time if funding_in_window else None
        stats = calculate_stats(df, start_cap, df_deposits_detailed, capital_start_time=analysis_start_time)
        if not stats.get("methodology", {}).get("capital_verified"):
            capital_source = "unavailable_or_nonpositive"
        stats.setdefault("methodology", {})["capital_source"] = capital_source
        stats["methodology"]["balance_reconciliation_adjustment"] = round(reconciliation_gap, 6)
        stats['cached'] = False
        _metrics_cache_set(cache_key, stats)

        stats['available_bots'] = sorted({int(b) for b in bots if b is not None})
        stats['selected_bot'] = bot_id
        snapshot = _snapshot_payload(latest_snapshot)
        if snapshot is not None:
            stats['account_snapshot'] = snapshot
            
        return stats
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/accounts")
def get_accounts(org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)):
    """Lists all unique MT5 accounts seen in the database for this organization"""
    from sqlmodel import select
    from .models import AccountSnapshot, TradeArchive
    
    # 1. Get unique logins from AccountSnapshot
    snapshots = db.exec(
        select(AccountSnapshot.account_login, AccountSnapshot.server_name)
        .where(AccountSnapshot.organization_id == org_id)
        .distinct()
    ).all()
    
    # 2. Get unique logins from TradeArchive
    trades = db.exec(
        select(TradeArchive.account_login, TradeArchive.server_name)
        .where(TradeArchive.organization_id == org_id)
        .distinct()
    ).all()
    
    # Combine and deduplicate
    unique_accounts = set()
    for login, server in snapshots:
        if login:
            unique_accounts.add((str(login), str(server or "")))
    for login, server in trades:
        if login:
            unique_accounts.add((str(login), str(server or "")))
            
    # For each unique account, find the latest snapshot (to get current balance, equity, currency, captured_at)
    result = []
    for login, server in unique_accounts:
        latest = db.exec(
            select(AccountSnapshot)
            .where(
                AccountSnapshot.organization_id == org_id,
                AccountSnapshot.account_login == login,
                AccountSnapshot.server_name == server
            )
            .order_by(AccountSnapshot.captured_at.desc())
        ).first()
        
        # Classify as Real/Demo
        srv_lower = server.lower()
        is_demo = any(x in srv_lower for x in ["demo", "stage", "test", "contest", "practice", "ctrader"])
        account_type = "Demo" if is_demo else "Real"
        
        if latest:
            result.append({
                "account_login": login,
                "server_name": server,
                "balance": latest.balance,
                "equity": latest.equity,
                "currency": latest.currency or "USD",
                "captured_at": latest.captured_at.isoformat(),
                "account_type": account_type
            })
        else:
            # If no snapshot exists, try to get some info from TradeArchive
            latest_trade = db.exec(
                select(TradeArchive)
                .where(
                    TradeArchive.organization_id == org_id,
                    TradeArchive.account_login == login,
                    TradeArchive.server_name == server
                )
                .order_by(TradeArchive.exittime.desc())
            ).first()
            
            result.append({
                "account_login": login,
                "server_name": server,
                "balance": 0.0,
                "equity": 0.0,
                "currency": "USD",
                "captured_at": latest_trade.exittime.isoformat() if latest_trade else None,
                "account_type": account_type
            })
            
    # Sort: Real first, then newest snapshot, then login so fresh live accounts surface immediately.
    def _account_sort_key(item: dict):
        captured_at = item.get("captured_at")
        try:
            captured_ts = datetime.fromisoformat(captured_at).timestamp() if captured_at else 0.0
        except Exception:
            captured_ts = 0.0
        return (
            item["account_type"] != "Real",
            -captured_ts,
            item["account_login"],
        )

    result.sort(key=_account_sort_key)
    return result

#--- ADMIN ROUTES ---

@app.post("/api/v1/admin/orgs")
def create_org(name: str, slug: str, owner_email: str  None = None):
    from .models import Organization
    with Session(db_engine) as session:
        existing = session.exec(select(Organization).where(Organization.slug == slug)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slug already exists")
        
        org = Organization(name=name, slug=slug, owner_email=owner_email)
        session.add(org)
        session.commit()
        session.refresh(org)
        return org

@app.post("/api/v1/admin/orgs/{org_id}/keys")
def create_org_key(org_id: int):
    from .models import ApiKey
    with Session(db_engine) as session:
        key_id = f"bk_{secrets.token_hex(8)}"
        key_secret = secrets.token_urlsafe(32)
        
        # Simple hash for login/identity (optional, we mostly care about secret for HMAC)
        key_hash = hashlib.sha256(key_secret.encode()).hexdigest()
        
        api_key = ApiKey(
            organization_id=org_id,
            key_id=key_id,
            key_hash=key_hash,
            key_secret=key_secret
        )
        session.add(api_key)
        session.commit()
        
        return {
            "key_id": key_id,
            "key_secret": key_secret,
            "note": "Save the secret! It will not be shown again."
        }

@app.get("/api/v1/live")
def get_live(
    account_login: str  None = None,
    server_name: str  None = None,
    org_id: int = Depends(get_current_org_id),
):
    df_live = get_live_positions_data(account_login=account_login, server_name=server_name)
    if df_live is None:
        return []
    
    return df_live.to_dict(orient='records')

@app.get("/api/v1/trade/chart")
def get_trade_chart(
    symbol: str, 
    entry: int, 
    exit: int,
    position_id: int  None = None,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db)
):
    """entry and exit are unix timestamps"""
    try:
        import json
        from .models import TradeArchive
        from sqlmodel import select
        
        e_time = datetime.fromtimestamp(entry, timezone.utc).replace(tzinfo=None)
        x_time = datetime.fromtimestamp(exit, timezone.utc).replace(tzinfo=None)
        
        trade = None
        if position_id is not None:
            trade = db.get(TradeArchive, (org_id, position_id))
            
        if not trade:
            trade = db.exec(
                select(TradeArchive)
                .where(
                    TradeArchive.organization_id == org_id,
                    TradeArchive.symbol == symbol,
                    TradeArchive.entrytime >= e_time - timedelta(seconds=5),
                    TradeArchive.entrytime <= e_time + timedelta(seconds=5)
                )
            ).first()
            
        if trade and trade.m1_candles_json:
            try:
                cached_data = json.loads(trade.m1_candles_json)
                if cached_data:
                    return cached_data
            except Exception:
                pass
                
        data = get_trade_m1_data(symbol, e_time, x_time)
        
        if data and trade:
            try:
                trade.m1_candles_json = json.dumps(data)
                db.add(trade)
                db.commit()
            except Exception as cache_err:
                db.rollback()
                print(f"Failed to cache candles in get_trade_chart: {cache_err}", flush=True)
                
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ai/chat")
def ai_chat(payload: AIRequest, org_id: int = Depends(get_current_org_id)):
    try:
        return build_ai_response(payload, mode="chat", organization_id=org_id)
    except AIRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@app.post("/api/v1/ai/insight")
def ai_insight(payload: AIRequest, org_id: int = Depends(get_current_org_id)):
    try:
        return build_ai_response(payload, mode="insight", organization_id=org_id)
    except AIRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@app.get("/api/v1/ai/macro-context")
def get_ai_macro_context(org_id: int = Depends(get_current_org_id)):
    from .ai import _get_macro_intel_context
    try:
        return {"context": _get_macro_intel_context(org_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ai/audit")
def get_ai_audit(limit: int = 50, org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)):
    safe_limit = min(max(limit, 1), 200)
    return db.exec(
        select(AIAuditEvent)
        .where(AIAuditEvent.organization_id == org_id)
        .order_by(AIAuditEvent.created_at.desc())
        .limit(safe_limit)
    ).all()

#--- MACRO NEWS ---

@app.get("/api/v1/macro/news")
def get_macro_news(limit: int = 20, org_id: int = Depends(get_current_org_id)):
    from .models import MacroNews
    with Session(db_engine) as session:
        news = session.exec(
            select(MacroNews)
            .where((MacroNews.organization_id == org_id)  (MacroNews.organization_id == 0))
            .order_by(MacroNews.published_at.desc())
            .limit(limit)
        ).all()
        return news


@app.get("/api/v1/macro/events")
def get_macro_events(days: int = 7, org_id: int = Depends(get_current_org_id)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    end = now + timedelta(days=min(max(days, 1), 14))
    with Session(db_engine) as session:
        return session.exec(
            select(EconomicEvent)
            .where(
                (EconomicEvent.organization_id == org_id)  (EconomicEvent.organization_id == 0),
                EconomicEvent.scheduled_at >= now - timedelta(hours=24),
                EconomicEvent.scheduled_at <= end,
            )
            .order_by(EconomicEvent.scheduled_at.asc())
        ).all()

#--- TRADING JOURNAL ---

@app.get("/api/v1/journal/pending")
def get_pending_journal(
    account_login: str  None = None,
    server_name: str  None = None,
    org_id: int = Depends(get_current_org_id),
):
    from .models import TradeArchive, TradeJournal
    with Session(db_engine) as session:
        # Trades in TradeArchive that don't have a COMPLETED journal
        # We look for trades in the last 30 days to keep it clean
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        
        # Subquery for position_ids that have completed journals
        completed_ids = session.exec(
            select(TradeJournal.position_id)
            .where(TradeJournal.organization_id == org_id, TradeJournal.is_completed == True)
        ).all()
        
        pending_query = select(TradeArchive).where(
            TradeArchive.organization_id == org_id,
            TradeArchive.exittime > cutoff,
            ~TradeArchive.position_id.in_(completed_ids),
        )
        if account_login:
            pending_query = pending_query.where(TradeArchive.account_login == account_login)
        if server_name:
            pending_query = pending_query.where(TradeArchive.server_name == server_name)

        pending_trades = session.exec(pending_query.order_by(TradeArchive.exittime.desc())).all()
        
        return pending_trades

@app.get("/api/v1/journal/{position_id}")
def get_trade_journal(
    position_id: int,
    account_login: str  None = None,
    server_name: str  None = None,
    org_id: int = Depends(get_current_org_id),
):
    from .models import TradeJournal, TradeArchive
    with Session(db_engine) as session:
        journal = session.exec(
            select(TradeJournal).where(TradeJournal.position_id == position_id, TradeJournal.organization_id == org_id)
        ).first()
        
        trade_query = select(TradeArchive).where(
            TradeArchive.position_id == position_id,
            TradeArchive.organization_id == org_id,
        )
        if account_login:
            trade_query = trade_query.where(TradeArchive.account_login == account_login)
        if server_name:
            trade_query = trade_query.where(TradeArchive.server_name == server_name)
        trade_data = session.exec(trade_query).first()
        
        if not trade_data:
            raise HTTPException(status_code=404, detail="Trade execution data not found")
            
        return {
            "trade": trade_data,
            "journal": journal or {
                "position_id": position_id,
                "emotional_state": 5,
                "emotional_tags": "",
                "notes_pre": "",
                "notes_during": "",
                "notes_post": "",
                "notes_general": "",
                "timeframe_data": "{}",
                "is_completed": False
            }
        }

@app.post("/api/v1/journal/{position_id}")
def save_trade_journal(
    position_id: int,
    data: dict,
    account_login: str  None = None,
    server_name: str  None = None,
    org_id: int = Depends(get_current_org_id),
):
    from .models import TradeArchive, TradeJournal
    with Session(db_engine) as session:
        trade_query = select(TradeArchive).where(
            TradeArchive.position_id == position_id,
            TradeArchive.organization_id == org_id,
        )
        if account_login:
            trade_query = trade_query.where(TradeArchive.account_login == account_login)
        if server_name:
            trade_query = trade_query.where(TradeArchive.server_name == server_name)
        if session.exec(trade_query).first() is None:
            raise HTTPException(status_code=404, detail="Trade execution data not found for selected account")

        journal = session.exec(
            select(TradeJournal).where(TradeJournal.position_id == position_id, TradeJournal.organization_id == org_id)
        ).first()
        
        if not journal:
            journal = TradeJournal(
                position_id=position_id,
                organization_id=org_id
            )
            
        # Map fields
        journal.emotional_state = data.get("emotional_state", journal.emotional_state)
        journal.emotional_tags = data.get("emotional_tags", journal.emotional_tags)
        journal.notes_pre = data.get("notes_pre", journal.notes_pre)
        journal.notes_during = data.get("notes_during", journal.notes_during)
        journal.notes_post = data.get("notes_post", journal.notes_post)
        journal.notes_general = data.get("notes_general", journal.notes_general)
        
        # timeframe_data should be a JSON string
        tf_data = data.get("timeframe_data")
        if isinstance(tf_data, (dict, list)):
            journal.timeframe_data = json.dumps(tf_data)
            
        journal.is_completed = data.get("is_completed", True)
        journal.updated_at = datetime.now(timezone.utc)
        
        session.add(journal)
        session.commit()
        session.refresh(journal)
        return journal

@app.get("/api/v1/macro/status")
def get_macro_status():
    try:
        return {
            "api_configured": True,
            "status": "KEYLESS_READY",
            "provider": "Keyless",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "sources": ["Reddit", "GDELT"],
        }
    except Exception as e:
        return {
            "api_configured": False,
            "status": "ERROR",
            "message": str(e),
            "provider": "Keyless"
        }

@app.post("/api/v1/macro/refresh")
def refresh_macro_news():
    try:
        calendar = MacroService.sync_economic_calendar()
        MacroService.update_news_feed()
        return {"status": "success", "message": "Macro feed updated", "calendar": calendar}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/journal/{position_id}/ai_review")
def get_ai_journal_review(
    position_id: int,
    account_login: str  None = None,
    server_name: str  None = None,
    org_id: int = Depends(get_current_org_id),
):
    from .models import TradeJournal, TradeArchive
    with Session(db_engine) as session:
        journal = session.exec(
            select(TradeJournal).where(TradeJournal.position_id == position_id, TradeJournal.organization_id == org_id)
        ).first()
        
        trade_query = select(TradeArchive).where(
            TradeArchive.position_id == position_id,
            TradeArchive.organization_id == org_id,
        )
        if account_login:
            trade_query = trade_query.where(TradeArchive.account_login == account_login)
        if server_name:
            trade_query = trade_query.where(TradeArchive.server_name == server_name)
        trade = session.exec(trade_query).first()
        
        if not journal or not trade:
            raise HTTPException(status_code=404, detail="Journal or Trade not found")
            
        prompt = f"""Actúa como el mentor senior 'Black Knight AI'. 
Analiza este trade y el diario del trader:
EJECUCIÓN: {trade.symbol} {trade.direction}, PnL: {trade.netpnl}, R-Multiple: {trade.r_multiple}
PSICOLOGÍA: Estado {journal.emotional_state}/10, Tags: {journal.emotional_tags}
NOTAS: {journal.notes_general}

Proporciona:
1. Una crítica constructiva sobre la ejecución vs psicología.
2. Sugerencia de riesgo para el siguiente trade (ej. 0.25%, 0.5%).
3. Plan de acción inmediato.
"""
        payload = AIRequest(prompt=prompt, focus="Mentoría Black Knight")
        response = build_ai_response(payload, mode="insight", organization_id=org_id)
        return response

def start_macro_updater():
    def run():
        headline_cycle = 0
        while True:
            try:
                MacroService.sync_economic_calendar()
                if headline_cycle % max(1, 900 // settings.macro_calendar_poll_seconds) == 0:
                    MacroService.update_news_feed()
            except Exception as e:
                print(f"Error updating macro feed: {e}")
            headline_cycle += 1
            time.sleep(settings.macro_calendar_poll_seconds)
            
    thread = Thread(target=run, daemon=True)
    thread.start()


def _verify_sentinel_internal(request: Request) -> None:
    expected = settings.sentinel_internal_token
    if not expected:
        return
    provided = request.headers.get("X-Sentinel-Token", "").strip()
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        provided = auth[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid Sentinel internal token")


def redact_sensitive_info(text: str  None) -> str  None:
    if not text:
        return text
    import re
    text = re.sub(r'(?i)\b(api[_-]?keysecretpasswordpasswdtokenauthcredentialkey)\b\s*[:=]\s*["\']([^"\']+)["\']', r'\1: "[REDACTED]"', text)
    text = re.sub(r'(?i)\b(bearertoken)\s+([a-zA-Z0-9_\-\.]+)', r'\1 [REDACTED]', text)
    text = re.sub(r'\bsk-[a-zA-Z0-9\-]{20,}\b', '[REDACTED_API_KEY]', text)
    return text

class SentinelUpdatePayload(BaseModel):
    stress_prob: float = Field(ge=0.0, le=1.0)
    narrative: str = Field(min_length=1, max_length=12000)
    weights: dict[str, float] = Field(default_factory=dict)
    organization_id: int = Field(default=0, ge=0)
    entropy: float = Field(default=0.0, ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    dominant_theme: str = Field(default="Neutral", max_length=200)
    xi: float = 0.0
    lambda_dominant: float = 0.0
    entropy_spectral: float = 0.0
    mtl: float = 0.0
    kld: float = 0.0
    top_highest_corr: list[dict] = Field(default_factory=list)
    top_lowest_corr: list[dict] = Field(default_factory=list)
    context_id: str  None = Field(default=None, max_length=80)
    health_status: str = Field(default="degraded", pattern="^(healthydegradedstaleoffline)$")
    source_health: dict = Field(default_factory=dict)
    model_version: str  None = Field(default=None, max_length=100)
    feature_version: str  None = Field(default=None, max_length=100)
    account_login: str  None = Field(default=None, max_length=100)
    server_name: str  None = Field(default=None, max_length=200)
    fallback_active: bool = False
    quant_prediction: dict  None = None
    # MiroFish LLM Metadata fields
    llm_model: str  None = Field(default=None, max_length=100)
    prompt_version: str  None = Field(default=None, max_length=100)
    context_sent: str  None = Field(default=None)
    sources_used: str  None = Field(default=None)
    api_latency_ms: int  None = Field(default=None)
    call_cost_usd: float  None = Field(default=None)
    prompt_hash: str  None = Field(default=None, max_length=100)


def _sentinel_snapshot_payload(snapshot: BloombergSnapshot  None) -> dict:
    if snapshot is None:
        return {
            "status": "offline",
            "health_status": "offline",
            "stress_prob": 0.0,
            "narrative": "No intelligence feed active.",
            "weights": {},
            "source_health": {},
            "data_age_seconds": None,
        }

    def safe_json_load(value, default):
        try:
            return json.loads(value) if value else default
        except Exception:
            return default

    updated = snapshot.updated_at.replace(tzinfo=None)
    age = max(0, int((datetime.now(timezone.utc).replace(tzinfo=None) - updated).total_seconds()))
    stored_health = getattr(snapshot, "health_status", "degraded") or "degraded"
    if age > settings.sentinel_snapshot_ttl_seconds * 3:
        health = "stale"
    elif age > settings.sentinel_snapshot_ttl_seconds and stored_health == "healthy":
        health = "degraded"
    else:
        health = stored_health
    return {
        "status": "online" if health == "healthy" else health,
        "health_status": health,
        "stress_prob": snapshot.stress_prob,
        "narrative": snapshot.narrative,
        "weights": safe_json_load(snapshot.weights_json, {}),
        "entropy": snapshot.entropy,
        "confidence": snapshot.confidence,
        "dominant_theme": snapshot.dominant_theme,
        "xi": getattr(snapshot, "xi", 0.0),
        "lambda_dominant": getattr(snapshot, "lambda_dominant", 0.0),
        "entropy_spectral": getattr(snapshot, "entropy_spectral", 0.0),
        "mtl": getattr(snapshot, "mtl", 0.0),
        "kld": getattr(snapshot, "kld", 0.0),
        "top_highest_corr": safe_json_load(getattr(snapshot, "top_highest_corr", "[]"), []),
        "top_lowest_corr": safe_json_load(getattr(snapshot, "top_lowest_corr", "[]"), []),
        "context_id": getattr(snapshot, "context_id", None),
        "source_health": safe_json_load(getattr(snapshot, "source_health_json", "{}"), {}),
        "model_version": getattr(snapshot, "model_version", None),
        "feature_version": getattr(snapshot, "feature_version", None),
        "account_login": getattr(snapshot, "account_login", None),
        "server_name": getattr(snapshot, "server_name", None),
        "fallback_active": bool(getattr(snapshot, "fallback_active", False)),
        "updated_at": snapshot.updated_at.isoformat(),
        "data_age_seconds": age,
        "ttl_seconds": settings.sentinel_snapshot_ttl_seconds,
    }


@app.get("/api/v1/sentinel/context")
def get_sentinel_context(
    account_login: str  None = None,
    server_name: str  None = None,
    org_id: int = Depends(get_current_org_id),
):
    return build_sentinel_context(org_id, account_login, server_name)


@app.get("/api/v1/sentinel/predictions")
def get_sentinel_predictions(
    limit: int = 50,
    evaluation_status: str  None = None,
    org_id: int = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    query = select(SentinelPrediction).where(
        (SentinelPrediction.organization_id == org_id)  (SentinelPrediction.organization_id == 0)
    )
    if evaluation_status:
        query = query.where(SentinelPrediction.evaluation_status == evaluation_status)
    return db.exec(query.order_by(SentinelPrediction.predicted_at.desc()).limit(min(max(limit, 1), 200))).all()

@app.get("/api/v1/bloomberg/status")
async def get_bloomberg_status(account_login: str  None = None, server_name: str  None = None, org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)):
    # Try to get the latest snapshot for this org or global (0)
    query = select(BloombergSnapshot).where(
        (BloombergSnapshot.organization_id == org_id)  (BloombergSnapshot.organization_id == 0)
    )
    if account_login:
        query = query.where((BloombergSnapshot.account_login == account_login)  (BloombergSnapshot.account_login == None))
    if server_name:
        query = query.where((BloombergSnapshot.server_name == server_name)  (BloombergSnapshot.server_name == None))
    snapshot = db.exec(query.order_by(BloombergSnapshot.account_login.desc(), BloombergSnapshot.updated_at.desc())).first()

    return _sentinel_snapshot_payload(snapshot)

@app.get("/api/v1/bloomberg/latest")
async def get_bloomberg_latest(account_login: str  None = None, server_name: str  None = None, org_id: int = Depends(get_current_org_id), db: Session = Depends(get_db)):
    """Returns the most recent intelligence snapshot for the dashboard."""
    query = select(BloombergSnapshot).where((BloombergSnapshot.organization_id == org_id)  (BloombergSnapshot.organization_id == 0))
    if account_login:
        query = query.where((BloombergSnapshot.account_login == account_login)  (BloombergSnapshot.account_login == None))
    if server_name:
        query = query.where((BloombergSnapshot.server_name == server_name)  (BloombergSnapshot.server_name == None))
    snapshot = db.exec(query.order_by(BloombergSnapshot.account_login.desc(), BloombergSnapshot.updated_at.desc())).first()
    return _sentinel_snapshot_payload(snapshot)

@app.post("/api/v1/bloomberg/update")
async def update_bloomberg_status(data: SentinelUpdatePayload, request: Request, db: Session = Depends(get_db)):
    _verify_sentinel_internal(request)
    payload = data.model_dump()
    
    top_highest = payload.get("top_highest_corr", [])
    top_lowest = payload.get("top_lowest_corr", [])
    
    top_highest_str = json.dumps(top_highest) if isinstance(top_highest, list) else str(top_highest)
    top_lowest_str = json.dumps(top_lowest) if isinstance(top_lowest, list) else str(top_lowest)

    new_snap = BloombergSnapshot(
        organization_id=payload.get("organization_id", 0),
        stress_prob=payload["stress_prob"],
        narrative=payload["narrative"],
        entropy=payload.get("entropy", 0.0),
        confidence=payload.get("confidence", 0.0),
        dominant_theme=payload.get("dominant_theme", "Neutral"),
        weights_json=json.dumps(payload.get("weights", {})),
        xi=payload.get("xi", 0.0),
        lambda_dominant=payload.get("lambda_dominant", 0.0),
        entropy_spectral=payload.get("entropy_spectral", 0.0),
        mtl=payload.get("mtl", 0.0),
        kld=payload.get("kld", 0.0),
        top_highest_corr=top_highest_str,
        top_lowest_corr=top_lowest_str,
        context_id=payload.get("context_id"),
        health_status=payload.get("health_status", "degraded"),
        source_health_json=json.dumps(payload.get("source_health", {})),
        model_version=payload.get("model_version"),
        feature_version=payload.get("feature_version"),
        account_login=payload.get("account_login"),
        server_name=payload.get("server_name"),
        fallback_active=payload.get("fallback_active", False),
        
        # MiroFish LLM Metadata fields with redaction
        llm_model=payload.get("llm_model"),
        prompt_version=payload.get("prompt_version"),
        context_sent=redact_sensitive_info(payload.get("context_sent")),
        sources_used=payload.get("sources_used"),
        api_latency_ms=payload.get("api_latency_ms"),
        call_cost_usd=payload.get("call_cost_usd"),
        prompt_hash=payload.get("prompt_hash"),
        
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(new_snap)
    quant = payload.get("quant_prediction") or {}
    if quant:
        prediction_id = quant.get("prediction_id") or f"sentinel-{secrets.token_hex(8)}"
        db.add(SentinelPrediction(
            prediction_id=prediction_id,
            context_id=payload.get("context_id"),
            organization_id=payload.get("organization_id", 0),
            account_login=payload.get("account_login"),
            model_version=payload.get("model_version"),
            feature_version=payload.get("feature_version"),
            horizon_minutes=int(quant.get("horizon_minutes", 5)),
            stress_probability=payload["stress_prob"],
            confidence=payload.get("confidence"),
            regime_json=json.dumps(quant.get("regime_probabilities", {})),
            model_health_json=json.dumps(quant.get("model_health", {})),
        ))
    db.commit()
    return {"status": "success", "context_id": payload.get("context_id")}

def get_sp500_vol_threshold() -> float:
    try:
        import yfinance as yf
        import numpy as np
        df = yf.download("^GSPC", period="5d", interval="1m", progress=False)
        if not df.empty:
            close = df["Close"].values
            log_returns = np.diff(np.log(close))
            rolling_vol = []
            for i in range(len(log_returns) - 4):
                vol = np.std(log_returns[i:i+5])
                rolling_vol.append(vol)
            if rolling_vol:
                return float(np.percentile(rolling_vol, 90))
    except Exception as e:
        print(f"Error calculating volatility threshold: {e}")
    return 0.0012

def get_realized_volatility(predicted_at: datetime) -> float  None:
    try:
        import yfinance as yf
        import numpy as np
        start_time = predicted_at
        end_time = predicted_at + timedelta(minutes=5)
        df = yf.download("^GSPC", start=start_time - timedelta(minutes=2), end=end_time + timedelta(minutes=2), interval="1m", progress=False)
        if not df.empty:
            df_filtered = df[(df.index >= pd.Timestamp(start_time)) & (df.index <= pd.Timestamp(end_time))]
            if len(df_filtered) >= 3:
                close = df_filtered["Close"].values
                log_returns = np.diff(np.log(close))
                return float(np.std(log_returns))
    except Exception as e:
        print(f"Error fetching realized volatility: {e}")
    return None

def start_prediction_evaluator():
    def worker():
        print("[STARTUP] Prediction Evaluator Daemon started.", flush=True)
        import time
        from sqlmodel import Session, select
        from .database import engine as db_engine
        from .models import SentinelPrediction
        import numpy as np
        
        while True:
            try:
                time.sleep(30)
                threshold = get_sp500_vol_threshold()
                
                with Session(db_engine) as session:
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
                    cutoff_naive = cutoff.replace(tzinfo=None)
                    
                    stmt = select(SentinelPrediction).where(
                        SentinelPrediction.evaluation_status == "pending",
                        SentinelPrediction.predicted_at <= cutoff_naive
                    )
                    pending = session.exec(stmt).all()
                    
                    for pred in pending:
                        pred_time_utc = pred.predicted_at.replace(tzinfo=timezone.utc) if pred.predicted_at.tzinfo is None else pred.predicted_at
                        realized_vol = get_realized_volatility(pred_time_utc)
                        
                        if realized_vol is not None:
                            actual_stress = 1.0 if realized_vol > threshold else 0.0
                            p = pred.stress_probability
                            
                            brier = (p - actual_stress) ** 2
                            p_clipped = max(1e-15, min(1.0 - 1e-15, p))
                            log_loss = -(actual_stress * np.log(p_clipped) + (1.0 - actual_stress) * np.log(1.0 - p_clipped))
                            
                            pred_class = 1.0 if p >= 0.5 else 0.0
                            tp = 1 if pred_class == 1.0 and actual_stress == 1.0 else 0
                            fp = 1 if pred_class == 1.0 and actual_stress == 0.0 else 0
                            tn = 1 if pred_class == 0.0 and actual_stress == 0.0 else 0
                            fn = 1 if pred_class == 0.0 and actual_stress == 1.0 else 0
                            
                            outcome = {
                                "realized_volatility": realized_vol,
                                "volatility_threshold": threshold,
                                "actual_stress": actual_stress,
                                "brier_score": brier,
                                "log_loss": log_loss,
                                "confusion_matrix": {
                                    "tp": tp, "fp": fp, "tn": tn, "fn": fn
                                }
                            }
                            
                            pred.outcome_json = json.dumps(outcome)
                            pred.evaluation_status = "evaluated"
                            session.add(pred)
                            session.commit()
                            print(f"[EVALUATOR] Evaluated prediction {pred.prediction_id}: prob={p:.4f}, stress={actual_stress}, brier={brier:.4f}", flush=True)
            except Exception as e:
                print(f"[EVALUATOR][ERROR] Loop error: {e}", flush=True)
                
    Thread(target=worker, daemon=True).start()

@app.get("/api/v1/sentinel/accuracy")
def get_sentinel_accuracy(db: Session = Depends(get_db)):
    from sqlmodel import select
    from .models import SentinelPrediction
    import numpy as np
    
    evaluated = db.exec(select(SentinelPrediction).where(SentinelPrediction.evaluation_status == "evaluated")).all()
    if not evaluated:
        return {
            "total_evaluated": 0,
            "average_brier_score": 0.0,
            "average_log_loss": 0.0,
            "confusion_matrix": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0
        }
        
    brier_scores = []
    log_losses = []
    tp, fp, tn, fn = 0, 0, 0, 0
    
    for pred in evaluated:
        try:
            outcome = json.loads(pred.outcome_json)
            brier_scores.append(outcome.get("brier_score", 0.0))
            log_losses.append(outcome.get("log_loss", 0.0))
            cm = outcome.get("confusion_matrix", {})
            tp += cm.get("tp", 0)
            fp += cm.get("fp", 0)
            tn += cm.get("tn", 0)
            fn += cm.get("fn", 0)
        except Exception:
            continue
            
    avg_brier = float(np.mean(brier_scores)) if brier_scores else 0.0
    avg_log_loss = float(np.mean(log_losses)) if log_losses else 0.0
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "total_evaluated": len(evaluated),
        "average_brier_score": avg_brier,
        "average_log_loss": avg_log_loss,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": precision,
        "recall": recall,
        "f1_score": f1
    }

if __name__ == "__main__":
    create_db_and_tables()
    start_macro_updater()
    start_prediction_evaluator()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
