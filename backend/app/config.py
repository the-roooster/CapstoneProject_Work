from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str = ""
    JWT_EXPIRE_MINUTES: int = 60
    TESTING: bool = False
    APP_TZ: str = "Asia/Kolkata"
    CORS_ORIGINS: str = ""
    MEDIUM_PCT: float = 97
    HIGH_PCT: float = 99.5
    USB_LOOKBACK_DAYS: int = 90
    DEMO_EMAIL: str = ""
    DEMO_PASSWORD: str = ""

    @model_validator(mode="after")
    def validate_jwt_secret(self):
        if not self.TESTING and len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters outside tests")
        return self


settings = Settings()
