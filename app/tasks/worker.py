import os
import httpx
from arq import Retry
from arq.connections import RedisSettings
from app.core.config import settings

async def failed_interaction_callback(ctx, phone_number: str, action: str, error_msg: str, timestamp: str):
    """
    Background job triggered when a webhook tool-call fails.
    This job polls the app's health endpoint until it is healthy,
    then triggers an outbound callback to the patient via Vapi's outbound calling API.
    """
    health_url = settings.APP_HEALTH_URL
    attempt = ctx.get('job_try', 1)
    max_attempts = 5
    
    print(f"[Worker] Running callback job for {phone_number} (Attempt {attempt}/{max_attempts}). Action: {action}, Error: {error_msg}", flush=True)
    
    # 1. Poll the health endpoint
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(health_url)
            if resp.status_code != 200:
                raise Exception(f"App returned status code {resp.status_code}")
            
            data = resp.json()
            if data.get("status") != "healthy":
                raise Exception("App reports status is not healthy")
    except Exception as e:
        # System is unhealthy, reschedule the job
        if attempt >= max_attempts:
            print(f"[Worker] Callback failed after {attempt} attempts for {phone_number}. Giving up.", flush=True)
            return f"Failed after {attempt} attempts"
        
        # Retry at: 5s, 10s, 20s, 30s, 60s
        delays = [5, 10, 20, 30, 60]
        delay = delays[min(attempt - 1, len(delays) - 1)]
        
        print(f"[Worker] App health check failed: {e}. Retrying in {delay} seconds...", flush=True)
        raise Retry(defer=delay)
    
    # 2. System is healthy! Trigger outbound call via Vapi
    if not settings.VAPI_API_KEY or not settings.VAPI_ASSISTANT_ID or not settings.VAPI_PHONE_NUMBER_ID:
        msg = "[Worker] System is healthy, but Vapi credentials are not configured. Outbound call skipped."
        print(msg, flush=True)
        return msg
        
    print(f"[Worker] System is healthy! Placing outbound callback to {phone_number}...", flush=True)
    
    vapi_url = "https://api.vapi.ai/call"
    headers = {
        "Authorization": f"Bearer {settings.VAPI_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "assistantId": settings.VAPI_ASSISTANT_ID,
        "phoneNumberId": settings.VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": phone_number
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(vapi_url, headers=headers, json=body)
            if resp.status_code not in (200, 201):
                raise Exception(f"Vapi API returned status code {resp.status_code}: {resp.text}")
                
            print(f"[Worker] Outbound callback successfully placed to {phone_number}. Response: {resp.json()}", flush=True)
            return "Callback placed successfully"
    except Exception as err:
        print(f"[Worker] Error placing outbound call to Vapi: {err}", flush=True)
        if attempt < max_attempts:
            raise Retry(defer=10)
        raise err

class WorkerSettings:
    functions = [failed_interaction_callback]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    poll_delay = 0.5
