from fastapi import Request, HTTPException, Depends
from sqlmodel import Session, select
from .database import engine
from .models import ApiKey, Organization
from .settings import settings
import hashlib
import hmac
import time
from datetime import datetime, timezone

def get_db():
    with Session(engine) as session:
        yield session

def verify_tenant_ingest(request: Request, raw_body: bytes, session: Session) -> int:
    """
    Verifica la firma HMAC usando el secreto del tenant.
    Retorna el organization_id.
    """
    if not settings.ingest_require_hmac:
        # Fallback a default si no se requiere HMAC (dev mode)
        # Pero si hay un Key-Id, lo usamos para identificar al tenant
        key_id = request.headers.get("X-BK-Key-Id", "").strip()
        if key_id:
            try:
                api_key = session.exec(select(ApiKey).where(ApiKey.key_id == key_id, ApiKey.is_active == True)).first()
                if api_key:
                    return api_key.organization_id
            except Exception as e:
                print(f"Warning: ApiKey lookup failed (likely schema mismatch): {e}")
        return settings.default_org_id

    timestamp = request.headers.get("X-BK-Timestamp", "").strip()
    signature = request.headers.get("X-BK-Signature", "").strip()
    key_id = request.headers.get("X-BK-Key-Id", "").strip()

    if not key_id or not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing HMAC headers (Key-Id, Timestamp, Signature)")

    api_key = session.exec(select(ApiKey).where(ApiKey.key_id == key_id, ApiKey.is_active == True)).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key ID")

    # Check timestamp skew
    try:
        ts_value = int(timestamp)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    now_ts = int(time.time())
    if abs(now_ts - ts_value) > settings.hmac_max_skew_seconds:
        raise HTTPException(status_code=401, detail="Timestamp skew too large")

    # Re-calculate signature
    payload = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(api_key.key_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    provided = signature[7:] if signature.startswith("sha256=") else signature

    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    # Update last used
    api_key.last_used_at = datetime.now(timezone.utc)
    session.add(api_key)
    session.commit()

    return api_key.organization_id

def get_current_org_id(request: Request, session: Session = Depends(get_db)) -> int:
    """
    Dependency para rutas GET/POST de la UI.
    Para el MVP, usaremos un header o el default.
    """
    org_slug = request.headers.get("X-BK-Org-Slug")
    if org_slug:
        org = session.exec(select(Organization).where(Organization.slug == org_slug, Organization.is_active == True)).first()
        if org:
            return org.id
            
    return settings.default_org_id
