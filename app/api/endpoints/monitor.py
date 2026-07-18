import os
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.models.call import Call, CallEvent

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

STATIC_DIR = Path(__file__).parent.parent.parent / "static"


# ── HTML page ────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def monitor_page():
    """Serve the monitoring dashboard HTML."""
    html_path = STATIC_DIR / "monitor.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@router.get("/architecture", response_class=HTMLResponse, include_in_schema=False)
async def architecture_page():
    """Serve the system architecture diagram HTML."""
    html_path = STATIC_DIR / "architecture.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Stats API ─────────────────────────────────────────────────────────────────

@router.get("/stats")
async def monitor_stats(db: AsyncSession = Depends(get_db)):
    """
    Aggregated stats consumed by the monitoring dashboard:
    - summary:       counts and averages
    - recent_calls:  10 most recent calls
    - all_calls:     all calls (capped at 200)
    - recent_events: 50 most recent webhook events
    - health:        live service status checks
    """

    # ── Summary ──────────────────────────────────────────────────────────────
    total_calls_result = await db.execute(select(func.count()).select_from(Call))
    total_calls = total_calls_result.scalar_one_or_none() or 0

    total_events_result = await db.execute(select(func.count()).select_from(CallEvent))
    total_events = total_events_result.scalar_one_or_none() or 0

    avg_lat_result = await db.execute(select(func.avg(CallEvent.latency_ms)))
    avg_latency = avg_lat_result.scalar_one_or_none()

    ended_result = await db.execute(
        select(func.count()).select_from(Call).where(Call.status.like("ended%"))
    )
    ended_calls = ended_result.scalar_one_or_none() or 0

    summary = {
        "total_calls": total_calls,
        "total_events": total_events,
        "avg_latency_ms": float(avg_latency) if avg_latency is not None else None,
        "ended_calls": ended_calls,
    }

    # ── Recent calls (10) ────────────────────────────────────────────────────
    recent_q = await db.execute(
        select(Call).order_by(Call.created_at.desc()).limit(10)
    )
    recent_calls = [
        {
            "call_id": c.call_id,
            "phone_number": c.phone_number,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "ended_at": c.ended_at.isoformat() if c.ended_at else None,
        }
        for c in recent_q.scalars().all()
    ]

    # ── All calls (capped at 200) ─────────────────────────────────────────────
    all_q = await db.execute(
        select(Call).order_by(Call.created_at.desc()).limit(200)
    )
    all_calls = [
        {
            "call_id": c.call_id,
            "phone_number": c.phone_number,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "ended_at": c.ended_at.isoformat() if c.ended_at else None,
            "transcript": c.transcript,
        }
        for c in all_q.scalars().all()
    ]

    # ── Recent events (50) ───────────────────────────────────────────────────
    events_q = await db.execute(
        select(CallEvent).order_by(CallEvent.created_at.desc()).limit(50)
    )
    recent_events = [
        {
            "id": e.id,
            "call_id": e.call_id,
            "event_type": e.event_type,
            "latency_ms": e.latency_ms,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "error": e.error,
        }
        for e in events_q.scalars().all()
    ]

    # ── Health checks ────────────────────────────────────────────────────────
    # Database
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Redis
    redis_ok = False
    arq_depth = None
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        redis_ok = True
        arq_depth = await r.zcard("arq:queue")
        await r.aclose()
    except Exception:
        pass

    health = {
        "database": "connected" if db_ok else "disconnected",
        "redis": redis_ok,
        "arq_queue_depth": arq_depth,
    }

    services = {
        "grafana": {
            "url": settings.GRAFANA_URL,
            "user": settings.GRAFANA_ADMIN_USER,
            "password": settings.GRAFANA_ADMIN_PASSWORD,
        },
        "prometheus": {"url": "http://localhost:9090"},
    }

    return {
        "summary": summary,
        "recent_calls": recent_calls,
        "all_calls": all_calls,
        "recent_events": recent_events,
        "health": health,
        "services": services,
    }
