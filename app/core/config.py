from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/vapi_platform"
    
    # Redis for arq
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Vapi configurations
    VAPI_API_KEY: str = ""
    VAPI_ASSISTANT_ID: str = ""
    VAPI_PHONE_NUMBER_ID: str = ""
    
    # App Health endpoint URL (used by arq worker)
    APP_HEALTH_URL: str = "http://app:8000/healthz"
    
    # Gemini API Key (for LLM reasoning in tool executions if required)
    GEMINI_API_KEY: str = ""

    # Grafana. The monitor page shows these so a visitor can open the
    # dashboards and look around, which is the point of the page.
    GRAFANA_ADMIN_USER: str = "admin"
    GRAFANA_ADMIN_PASSWORD: str = "admin"
    GRAFANA_URL: str = "http://localhost:3000"
    # Where a person can reach Prometheus. Blank on purpose: Prometheus has no
    # authentication at all, so there is no address that is safe to assume.
    PROMETHEUS_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
