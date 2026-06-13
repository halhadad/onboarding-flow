from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    # Reserved for future signing; not used for idempotency.
    ONBOARDING_INTERNAL_SECRET: str | None = None

    # One lifetime for the token DB expiry and the cookie max age.
    RESUME_COOKIE_NAME: str = "bank_onboarding_resume"
    RESUME_TOKEN_TTL_SECONDS: int = 7 * 24 * 60 * 60
    RESUME_TOKEN_BYTES: int = 32

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
