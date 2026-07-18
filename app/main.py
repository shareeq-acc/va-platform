from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from prometheus_fastapi_instrumentator import Instrumentator
import google.generativeai as genai

from app.core.config import settings
from app.core.database import init_db
from app.api.endpoints.webhook import router
from app.api.endpoints.monitor import router as monitor_router

# Initialize FastAPI application
app = FastAPI(title="Vapi Webhook Portal")

# Configure Google Gemini API
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

# Instrument application HTTP metrics (without exposing automatically, we handle exposure manually)
instrumentator = Instrumentator()
instrumentator.instrument(app)

@app.on_event("startup")
async def startup_event():
    # Automatically initialize tables in the database
    await init_db()

# Include endpoints routers
app.include_router(router)
app.include_router(monitor_router)

_STATIC = Path(__file__).parent / "static"

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home():
    """Platform overview homepage."""
    return HTMLResponse(content=(_STATIC / "index.html").read_text(encoding="utf-8"))

@app.get("/monitor", include_in_schema=False)
async def monitor_redirect():
    """Convenience redirect to the monitoring dashboard."""
    return RedirectResponse(url="/api/monitor/")

@app.get("/architecture", include_in_schema=False)
async def architecture_redirect():
    """Convenience redirect to the architecture diagram."""
    return RedirectResponse(url="/api/monitor/architecture")
