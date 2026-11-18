from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vlm_provider: str = "ollama"  # ollama | gemini (also used for text models)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5vl:7b"
    ollama_chat_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_fallback_model: str = ""

    chat_framework: str = "agno"  # langchain | agno
    use_ai_itinerary: bool = True

    database_url: str = "postgresql+psycopg://trip:trip@localhost:5432/tripdb"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "uploads"
    frontend_origin: str = "http://localhost:3000"
    confidence_threshold: float = 0.6

    @property
    def ollama_text_model(self) -> str:
        return self.ollama_chat_model or self.ollama_model


settings = Settings()