from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Control Plane application configuration."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_PORT: int = 8080
    API_HOST: str = "0.0.0.0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql://postgres:postgres_placeholder_password@ledger:5432/celesto_ledger"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_placeholder_password"
    POSTGRES_DB: str = "celesto_ledger"
    LEDGER_PORT: int = 5432

    CELESTO_PROVIDER: str = "mock"
    CELESTO_API_KEY: str = "celesto_api_key_placeholder"


settings = Settings()
