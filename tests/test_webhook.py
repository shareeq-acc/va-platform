import pytest
import asyncio
import uuid
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.main import app
from app.core.database import get_db, init_db, engine
from app.models.call import Call, CallEvent

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    await init_db()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(CallEvent.metadata.drop_all)

@pytest_asyncio.fixture(autouse=True)
async def cleanup_tables():
    async with engine.begin() as conn:
        await conn.execute(delete(CallEvent))
        await conn.execute(delete(Call))
    yield

@pytest.mark.asyncio
async def test_healthz():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

@pytest.mark.asyncio
async def test_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/metrics")
        assert response.status_code == 200
        assert "arq_queue_depth" in response.text

@pytest.mark.asyncio
async def test_webhook_call_started():
    call_id = str(uuid.uuid4())
    payload = {
        "message": {
            "type": "call-started",
            "call": {
                "id": call_id,
                "customer": {
                    "number": "+15551234567"
                }
            }
        }
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/webhook", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        async with AsyncSession(engine) as session:
            stmt = select(Call).where(Call.call_id == call_id)
            res = await session.execute(stmt)
            call_rec = res.scalar_one_or_none()
            assert call_rec is not None
            assert call_rec.phone_number == "+15551234567"
            assert call_rec.status == "started"

@pytest.mark.asyncio
async def test_webhook_duplicate_event_idempotency():
    call_id = str(uuid.uuid4())
    payload = {
        "message": {
            "type": "call-started",
            "call": {
                "id": call_id,
                "customer": {
                    "number": "+15551234567"
                }
            }
        }
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response1 = await ac.post("/webhook", json=payload)
        assert response1.status_code == 200
        
        response2 = await ac.post("/webhook", json=payload)
        assert response2.status_code == 200
        
        async with AsyncSession(engine) as session:
            stmt = select(CallEvent).where(CallEvent.call_id == call_id)
            res = await session.execute(stmt)
            events = res.scalars().all()
            assert len(events) == 1

@pytest.mark.asyncio
async def test_webhook_tool_call_success():
    call_id = str(uuid.uuid4())
    payload = {
        "message": {
            "type": "tool-calls",
            "call": {
                "id": call_id,
                "customer": {
                    "number": "+15551234567"
                }
            },
            "toolCalls": [
                {
                    "id": "tc-123",
                    "type": "function",
                    "function": {
                        "name": "log_call_intent",
                        "arguments": {
                            "name": "John Doe",
                            "dob": "1990-01-01",
                            "reason": "annual physical checkup"
                        }
                    }
                }
            ]
        }
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["toolCallId"] == "tc-123"
        assert "John Doe" in data["results"][0]["result"]

@pytest.mark.asyncio
async def test_webhook_tool_call_failure_fallback_and_enqueueing():
    call_id = str(uuid.uuid4())
    payload = {
        "message": {
            "type": "tool-calls",
            "call": {
                "id": call_id,
                "customer": {
                    "number": "+15559999999"
                }
            },
            "toolCalls": [
                {
                    "id": "tc-fail",
                    "type": "function",
                    "function": {
                        "name": "log_call_intent",
                        "arguments": {
                            "name": "force_fail",
                            "dob": "1990-01-01",
                            "reason": "simulated error"
                        }
                    }
                }
            ]
        }
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["toolCallId"] == "tc-fail"
        assert data["results"][0]["result"] == "having trouble pulling that up, I'll have someone call you back"
