from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for the application."""

    LLM_API_URL: str = "http://localhost:8080/v1"
    LLM_API_KEY: str = "sk-no-key-required"
    LLM_MODEL_NAME: str = "gpt-oss-120b"
    LLM_USER: str | None = None
    LLM_PASS: str | None = None
    LLM_MAX_CONTEXT: int = 70000
    GOOGLE_SHEET_ID: str = ""
    GMAIL_LABEL_NAME: str = "recruiter"
    GOOGLE_APPLICATION_CREDENTIALS: str = "credentials.json"
    PARALLEL_LIMIT: int = 10
    STATE_FILE: str = "state.json"
    DEFAULT_LOOKBACK_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
