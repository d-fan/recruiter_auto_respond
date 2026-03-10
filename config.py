from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Configuration for the application."""
    LLM_API_URL: str = "http://localhost:8080/v1"
    LLM_API_KEY: str = "sk-no-key-required"
    GOOGLE_SHEET_ID: str = ""
    GMAIL_LABEL_NAME: str = "recruiter"
    PARALLEL_LIMIT: int = 10

    class Config:
        env_file = ".env"

settings = Settings()
