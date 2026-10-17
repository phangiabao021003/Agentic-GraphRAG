from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str
    redis_url: str
    jwt_secret: str
    google_token_encryption_key: str
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    llm_provider: str = "gemini"  # gemini | openai_compat
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.6-flash"
    llm_server_url: str = ""  # self-hosted OpenAI-compatible server, later
    mcp_server_url: str = "http://localhost:8080"
    frontend_url: str = "http://localhost:5173"


settings = Settings()
