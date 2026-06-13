from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    # Reserved for future signing needs. No longer used for step idempotency,
    # which is a plain content fingerprint (no secret required).
    ONBOARDING_INTERNAL_SECRET: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
