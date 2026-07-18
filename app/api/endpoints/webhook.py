import time
import json
import sys
import datetime
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge
import redis.asyncio as aioredis
from arq import create_pool
from arq.connections import RedisSettings
import google.generativeai as genai

from app.core.config import settings
from app.core.database import get_db, check_db_health
from app.models.call import Call, CallEvent
from app.schemas.webhook import WebhookPayload

router = APIRouter()

# Prometheus custom gauge for arq queue depth
ARQ_QUEUE_DEPTH = Gauge("arq_queue_depth", "Current number of jobs in the arq callback queue")

# Global arq pool variable (will be initialized on app startup)
arq_pool = None

async def get_arq_pool():
    global arq_pool
    if arq_pool is None:
        try:
            redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
            arq_pool = await create_pool(redis_settings)
        except Exception as e:
            print(f"Failed to connect to Redis/arq pool: {e}", file=sys.stderr)
    return arq_pool

def log_structured_event(call_id: str, event_type: str, latency_ms: int, http_status: int, error_msg: str = None):
    """Helper to log event as one JSON line to stdout."""
    log_record = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "call_id": call_id,
        "event_type": event_type,
        "latency_ms": latency_ms,
        "status": http_status,
        "error": error_msg
    }
    print(json.dumps(log_record), file=sys.stdout, flush=True)

@router.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)):
    db_healthy = await check_db_health()
    if not db_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected"}
        )
    
    try:
        stmt = select(CallEvent.created_at).order_by(desc(CallEvent.created_at)).limit(1)
        result = await db.execute(stmt)
        last_event_time = result.scalar_one_or_none()
        
        return {
            "status": "healthy",
            "database": "connected",
            "last_event_timestamp": last_event_time.isoformat() + "Z" if last_event_time else None
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "unhealthy", "error": str(e)}
        )

@router.get("/metrics")
async def metrics_endpoint():
    """Serves Prometheus metrics and updates the arq queue depth gauge."""
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        queue_depth = await r.zcard("arq:queue")
        ARQ_QUEUE_DEPTH.set(queue_depth)
        await r.aclose()
    except Exception as e:
        print(f"Error updating arq queue metrics: {e}", file=sys.stderr)
        
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@router.post("/webhook")
async def handle_webhook(payload: WebhookPayload, db: AsyncSession = Depends(get_db), pool=Depends(get_arq_pool)):
    start_time = time.time()
    msg = payload.message
    call_id = msg.call.id
    event_type = msg.type
    customer_number = msg.call.customer.number if msg.call.customer else None
    
    error_msg = None
    http_status = status.HTTP_200_OK
    response_body = {"status": "ok"}
    
    try:
        # Check database health first before handling transactions
        db_ok = await check_db_health()
        if not db_ok:
            raise Exception("Database connectivity check failed")
            
        # Get or create the call record
        stmt = select(Call).where(Call.call_id == call_id)
        result = await db.execute(stmt)
        call_rec = result.scalar_one_or_none()
        
        if not call_rec:
            call_rec = Call(
                call_id=call_id,
                phone_number=customer_number,
                status="started"
            )
            db.add(call_rec)
            await db.flush()
        
        if event_type == "call-ended":
            call_rec.status = "ended"
            call_rec.ended_at = datetime.datetime.utcnow()
            if msg.endedReason:
                call_rec.status = f"ended: {msg.endedReason}"
        
        if event_type == "transcript" and msg.transcript:
            call_rec.transcript = msg.transcript
            
        if event_type in ("tool-calls", "function-call") or msg.toolCalls:
            tool_calls = msg.toolCalls or []
            results = []
            
            for tc in tool_calls:
                func_name = tc.function.name
                func_args = tc.function.arguments
                
                if isinstance(func_args, str):
                    try:
                        args = json.loads(func_args)
                    except Exception:
                        args = {}
                else:
                    args = func_args or {}
                
                if func_name == "log_call_intent":
                    name = args.get("name", "Unknown")
                    dob = args.get("dob", "Unknown")
                    reason = args.get("reason", "Unknown")
                    
                    if name == "force_fail":
                        raise Exception("Simulated DB/LLM Failure for demonstration purposes")
                    
                    summary = f"Patient {name} (DOB: {dob}) called for: {reason}."
                    if settings.GEMINI_API_KEY:
                        try:
                            model = genai.GenerativeModel("gemini-1.5-flash")
                            prompt = f"Summarize this patient appointment/refill request in 10 words or less: Name: {name}, DOB: {dob}, Reason: {reason}."
                            gemini_resp = await model.generate_content_async(prompt)
                            summary = gemini_resp.text.strip()
                        except Exception as gemini_err:
                            raise Exception(f"Gemini API failure: {gemini_err}")
                    
                    call_rec.status = f"intent_logged: {summary[:100]}"
                    
                    results.append({
                        "toolCallId": tc.id,
                        "result": f"Call intent logged: {summary}"
                    })
            
            response_body = {"results": results}
            
        try:
            latency_ms = int((time.time() - start_time) * 1000)
            event_rec = CallEvent(
                call_id=call_id,
                event_type=event_type,
                payload=payload.model_dump(),
                latency_ms=latency_ms
            )
            db.add(event_rec)
            await db.commit()
        except Exception as db_err:
            await db.rollback()
            if "uq_call_event_type" in str(db_err) or "unique" in str(db_err).lower():
                print(f"Ignored duplicate call event: {call_id} / {event_type}", file=sys.stdout)
                db.expunge_all()
            else:
                raise db_err
                
    except Exception as e:
        error_msg = str(e)
        http_status = status.HTTP_200_OK
        
        if pool:
            try:
                action_info = "Tool call log_call_intent"
                if msg.toolCalls:
                    action_info = f"Tools: {', '.join(tc.function.name for tc in msg.toolCalls)}"
                
                await pool.enqueue_job(
                    "failed_interaction_callback",
                    phone_number=customer_number or "unknown",
                    action=action_info,
                    error_msg=error_msg,
                    timestamp=datetime.datetime.utcnow().isoformat()
                )
            except Exception as arq_err:
                print(f"Failed to enqueue arq job: {arq_err}", file=sys.stderr)
        
        if event_type in ("tool-calls", "function-call") or msg.toolCalls:
            fallback_results = []
            tool_calls = msg.toolCalls or []
            for tc in tool_calls:
                fallback_results.append({
                    "toolCallId": tc.id,
                    "result": "having trouble pulling that up, I'll have someone call you back"
                })
            response_body = {"results": fallback_results}
        else:
            response_body = {"status": "error", "message": "Graceful fallback activated"}
            
    latency_ms = int((time.time() - start_time) * 1000)
    log_structured_event(call_id, event_type, latency_ms, http_status, error_msg)
    
    return JSONResponse(status_code=http_status, content=response_body)
