from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str = ""
    JWT_EXPIRE_MINUTES: int = 60
    APP_TZ: str = "Asia/Kolkata"
    CORS_ORIGINS: str = ""
    MEDIUM_PCT: float = 97
    HIGH_PCT: float = 99.5
    USB_LOOKBACK_DAYS: int = 90


settings = Settings()
