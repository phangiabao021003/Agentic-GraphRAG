from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    qdrant_url: str
    serpapi_api_key: str = ""


settings = Settings()
