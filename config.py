from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.enums import Sector

class Settings(BaseSettings):
    DATABASE_URL: str
    # Reserved for future signing; not used for idempotency.
    ONBOARDING_INTERNAL_SECRET: str | None = None

    # One lifetime for the token DB expiry and the cookie max age.
    RESUME_COOKIE_NAME: str = "bank_onboarding_resume"
    RESUME_TOKEN_TTL_SECONDS: int = 7 * 24 * 60 * 60
    RESUME_TOKEN_BYTES: int = 32

    # Decisioning thresholds; injected into the engine at the composition root.
    DTI_THRESHOLD: float = 0.60
    OWNERSHIP_CONCENTRATION_THRESHOLD: float = 75.0
    HIGH_RISK_SECTORS: frozenset[str] = frozenset({Sector.FINANCIAL_SERVICES.value})
    # Tax residencies the screening provider treats as a confirmed sanctions hit.
    SANCTIONED_RESIDENCIES: frozenset[str] = frozenset({"IR", "KP", "SY"})

    # Integration execution: per attempt timeout, attempts, and a demo latency.
    INTEGRATION_TIMEOUT_SECONDS: float = 2.0
    INTEGRATION_MAX_ATTEMPTS: int = 2
    INTEGRATION_DEMO_DELAY_SECONDS: float = 0.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
