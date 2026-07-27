import requests
import json
import datetime
import hashlib
import os
import time
from typing import List, Dict, Optional
from sqlmodel import Session, select
from .database import engine
from .models import EconomicEvent, MacroNews
from .ai import AIRequest, build_ai_response
from .settings import settings

class MacroService:
    IMPACT_SCORES = {"high": 9, "medium": 6, "low": 3, "holiday": 1}

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join((value or "").split()).strip().lower()

    @staticmethod
    def _fetch_json(url: str, *, headers: dict  None = None, params: dict  None = None, timeout: int = 5):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    @staticmethod
    def fetch_keyless_macro() -> List[Dict]:
        """Fuentes alternativas sin necesidad de API Key"""
        results = []
        
        # 1. Reddit (WSB) - Social Sentiment
        try:
            headers = {'User-Agent': 'Black-Knight-Terminal/1.0'}
            data = MacroService._fetch_json('https://www.reddit.com/r/wallstreetbets/hot.json?limit=3', headers=headers, timeout=5)
            if data:
                for post in data['data']['children']:
                    p = post['data']
                    results.append({
                        "source": "Reddit (r/wallstreetbets)",
                        "title": p.get('title', ''),
                        "content": p.get('selftext', '')[:300] + "...",
                        "published_at": datetime.datetime.fromtimestamp(p.get('created_utc', 0)),
                        "url": f"https://reddit.com{p.get('permalink', '')}"
                    })
        except: pass

        # 2. GDELT (Global Macro)
        try:
            params = {
                "query": "theme:ECON_STOCKMARKET OR theme:ECON_INFLATION",
                "mode": "artlist",
                "format": "json",
                "timespan": "24h",
                "maxrecords": "3"
            }
            data = MacroService._fetch_json("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=5)
            if data:
                for art in data.get("articles", []):
                    results.append({
                        "source": f"GDELT ({art.get('domain', 'news')})",
                        "title": art.get('title', ''),
                        "content": "Análisis global de mercado detectado vía GDELT.",
                        "published_at": datetime.datetime.utcnow(),
                        "url": art.get('url', '')
                    })
        except: pass

        seen = set()
        deduped = []
        for item in results:
            fingerprint = (
                MacroService._normalize_text(item.get('title', '')),
                MacroService._normalize_text(item.get('source', '')),
                item.get('url', '').strip(),
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            deduped.append(item)

        deduped.sort(key=lambda item: item.get('published_at') or datetime.datetime.min, reverse=True)
        return deduped[:10]

    @staticmethod
    def _parse_calendar_time(value: str) -> datetime.datetime  None:
        try:
            parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError):
            return None

    @classmethod
    def fetch_economic_calendar(cls) -> List[Dict]:
        cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "_journal_data"))
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "calendar_cache.json")
        
        use_cache = False
        if os.path.exists(cache_path):
            try:
                mtime = os.path.getmtime(cache_path)
                age = time.time() - mtime
                if age < 600:  # 10 minutes cache TTL
                    use_cache = True
            except Exception as e:
                print(f"[CALENDAR] Error checking cache time: {e}")

        rows = None
        if use_cache:
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    rows = json.load(f)
                print("[CALENDAR] Loaded calendar from local disk cache.")
            except Exception as e:
                print(f"[CALENDAR] Failed to read from cache: {e}")
                rows = None

        if rows is None:
            # Fetch from URL with a browser-like User-Agent
            print("[CALENDAR] Fetching calendar from remote URL...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
            try:
                rows = cls._fetch_json(
                    settings.macro_calendar_url,
                    headers=headers,
                    timeout=10
                )
            except Exception as e:
                print(f"[CALENDAR] HTTP request failed: {e}")
                rows = None

            if isinstance(rows, list) and len(rows) > 0:
                # Cache the fresh rows
                try:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(rows, f, ensure_ascii=False, indent=2)
                    print("[CALENDAR] Saved calendar response to disk cache.")
                except Exception as e:
                    print(f"[CALENDAR] Failed to save calendar response to cache: {e}")
            else:
                # If HTTP request failed or returned empty/non-list, fallback to disk cache if it exists
                if os.path.exists(cache_path):
                    try:
                        with open(cache_path, "r", encoding="utf-8") as f:
                            rows = json.load(f)
                        print("[CALENDAR] Remote fetch failed (or rate-limited). Falling back to cached calendar from disk.")
                    except Exception as e:
                        print(f"[CALENDAR] Cache fallback failed: {e}")
                        rows = []
                else:
                    rows = []

        if not isinstance(rows, list):
            return []

        events: List[Dict] = []
        for row in rows:
            scheduled_at = cls._parse_calendar_time(row.get("date", ""))
            title = " ".join(str(row.get("title") or "").split()).strip()
            if scheduled_at is None or not title:
                continue
            impact = str(row.get("impact") or "Low").strip().lower()
            country = str(row.get("country") or "Global").strip().upper()
            raw_key = f"{scheduled_at.isoformat()}{country}{title.lower()}"
            events.append({
                "event_key": hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
                "title": title,
                "country": country,
                "currency": country,
                "scheduled_at": scheduled_at,
                "impact": impact.upper(),
                "impact_score": cls.IMPACT_SCORES.get(impact, 3),
                "forecast": str(row.get("forecast") or "").strip() or None,
                "previous": str(row.get("previous") or "").strip() or None,
                "actual": str(row.get("actual") or "").strip() or None,
            })
        return events

    @staticmethod
    def _event_interpretation(event: EconomicEvent) -> tuple[str, str]:
        values = []
        if event.actual:
            values.append(f"actual {event.actual}")
        if event.forecast:
            values.append(f"previsión {event.forecast}")
        if event.previous:
            values.append(f"previo {event.previous}")
        value_text = ", ".join(values) if values else "sin cifras publicadas todavía"
        severity = "alto" if event.impact_score >= 8 else "medio" if event.impact_score >= 6 else "bajo"
        interpretation = (
            f"Evento macro de impacto {severity} para {event.currency}: {value_text}. "
            "La lectura inicial prioriza volatilidad, desviación frente al consenso y reacción de tipos, divisas e índices."
        )
        suggestion = (
            "Reducir exposición durante la primera reacción y esperar confirmación de precio."
            if event.impact_score >= 6
            else "Monitorizar; no modificar riesgo salvo sorpresa material frente al consenso."
        )
        return interpretation, suggestion

    @staticmethod
    def _numeric_value(value: str  None) -> float  None:
        if not value:
            return None
        cleaned = value.strip().replace(",", "").replace("%", "")
        multiplier = 1.0
        if cleaned.lower().endswith("k"):
            multiplier, cleaned = 1_000.0, cleaned[:-1]
        elif cleaned.lower().endswith("m"):
            multiplier, cleaned = 1_000_000.0, cleaned[:-1]
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None

    @classmethod
    def _surprise_value(cls, actual: str  None, forecast: str  None) -> float  None:
        actual_value = cls._numeric_value(actual)
        forecast_value = cls._numeric_value(forecast)
        if actual_value is None or forecast_value is None:
            return None
        return round((actual_value - forecast_value) / max(abs(forecast_value), 1e-9), 6)

    @classmethod
    def sync_economic_calendar(cls, organization_id: int = 0) -> dict:
        incoming = cls.fetch_economic_calendar()
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        inserted = 0
        released = 0

        with Session(engine) as session:
            for item in incoming:
                event = session.exec(select(EconomicEvent).where(EconomicEvent.event_key == item["event_key"])).first()
                if event is None:
                    event = EconomicEvent(organization_id=organization_id, **item)
                    inserted += 1
                else:
                    previous_actual = event.actual
                    for key in ("forecast", "previous", "actual", "impact", "impact_score"):
                        setattr(event, key, item[key])
                    if previous_actual and item.get("actual") and previous_actual != item["actual"]:
                        event.revision_count += 1
                    event.updated_at = now
                event.status = "released" if event.scheduled_at <= now else "scheduled"
                if event.status == "released" and event.actual is None:
                    if event.forecast:
                        event.actual = event.forecast
                    elif event.previous:
                        event.actual = event.previous
                    else:
                        event.actual = "0.0"
                event.surprise_value = cls._surprise_value(event.actual, event.forecast)
                session.add(event)
            session.commit()

            due_events = session.exec(
                select(EconomicEvent).where(
                    EconomicEvent.organization_id == organization_id,
                    EconomicEvent.scheduled_at <= now,
                    EconomicEvent.scheduled_at >= now - datetime.timedelta(hours=36),
                    EconomicEvent.released_to_feed == False,
                ).order_by(EconomicEvent.scheduled_at.asc())
            ).all()

            for event in due_events:
                interpretation, suggestion = cls._event_interpretation(event)
                content = (
                    f"Evento programado {event.currency}. Actual: {event.actual or 'N/D'}; "
                    f"Previsión: {event.forecast or 'N/D'}; Previo: {event.previous or 'N/D'}."
                )
                session.add(MacroNews(
                    organization_id=organization_id,
                    title=event.title,
                    content=content,
                    published_at=event.scheduled_at,
                    source=event.source,
                    url=None,
                    impact_score=event.impact_score,
                    ai_interpretation=interpretation,
                    ai_suggestion=suggestion,
                    economic_event_key=event.event_key,
                ))
                event.released_to_feed = True
                event.updated_at = now
                session.add(event)
                released += 1
            session.commit()

            released_events = session.exec(
                select(EconomicEvent).where(
                    EconomicEvent.organization_id == organization_id,
                    EconomicEvent.released_to_feed == True,
                    EconomicEvent.scheduled_at >= now - datetime.timedelta(hours=36),
                )
            ).all()
            for event in released_events:
                news_item = session.exec(select(MacroNews).where(MacroNews.economic_event_key == event.event_key)).first()
                if news_item is None:
                    continue
                interpretation, suggestion = cls._event_interpretation(event)
                news_item.content = (
                    f"Evento programado {event.currency}. Actual: {event.actual or 'N/D'}; "
                    f"PrevisiÃ³n: {event.forecast or 'N/D'}; Previo: {event.previous or 'N/D'}; "
                    f"Sorpresa relativa: {event.surprise_value if event.surprise_value is not None else 'N/D'}."
                )
                news_item.ai_interpretation = interpretation
                news_item.ai_suggestion = suggestion
                news_item.impact_score = event.impact_score
                session.add(news_item)
            session.commit()

        return {"fetched": len(incoming), "inserted": inserted, "released": released}

    @staticmethod
    def interpret_with_ai(news_item: Dict) -> Optional[Dict]:
        """
        Utiliza el modelo NVIDIA Llama 3.1 405B para analizar noticias y generar interpretaciones macroeconómicas.
        """
        prompt = f"""Analiza la siguiente noticia económica.
Tu objetivo es determinar el impacto en los mercados financieros globales en una escala de 1 a 10.
Proporciona una interpretación profesional y una sugerencia para traders.

Noticia: {news_item['title']}
Contexto: {news_item['content']}

Responde ÚNICAMENTE con un objeto JSON válido (sin texto adicional) con esta estructura:
{{
  "impact_score": int,
  "ai_interpretation": "string breve y profesional",
  "ai_suggestion": "string con acción sugerida"
}}
"""
        try:
            payload = AIRequest(prompt=prompt, focus="Analista Macro NVIDIA")
            response = build_ai_response(payload, mode="chat")
            
            text = response.answer.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
                
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                if "impacto" in text.lower():
                     return {
                        "impact_score": 5,
                        "ai_interpretation": text[:200],
                        "ai_suggestion": "Vigilar volatilidad."
                     }
        except Exception as e:
            pass
        return None

    @classmethod
    def update_news_feed(cls):
        """Orquesta la recolección, filtrado e interpretación."""
        raw_news = cls.fetch_keyless_macro()

        with Session(engine) as session:
            for item in raw_news:
                # Verificar si ya existe
                normalized_title = cls._normalize_text(item['title'])
                existing = session.exec(
                    select(MacroNews).where(MacroNews.title == item['title'])
                ).first()

                if not existing:
                    for candidate in session.exec(select(MacroNews)).all():
                        if cls._normalize_text(candidate.title) == normalized_title:
                            existing = candidate
                            break
                
                if existing:
                    continue
                
                # Inteligencia Artificial: Interpretación obligatoria
                analysis = cls.interpret_with_ai(item)
                if not analysis:
                    analysis = {
                        "impact_score": 5,
                        "ai_interpretation": "Análisis automático pendiente.",
                        "ai_suggestion": "Vigilar volatilidad."
                    }
                
                new_item = MacroNews(
                    title=item['title'],
                    content=item['content'],
                    published_at=item['published_at'],
                    source=item['source'],
                    url=item.get('url'),
                    impact_score=analysis['impact_score'],
                    ai_interpretation=analysis['ai_interpretation'],
                    ai_suggestion=analysis['ai_suggestion']
                )
                session.add(new_item)
            
            session.commit()
            print(f"[{datetime.datetime.now()}] Macro Feed actualizado con éxito.")

if __name__ == "__main__":
    # Test manual
    MacroService.update_news_feed()
