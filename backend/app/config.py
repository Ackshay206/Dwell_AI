"""
Configuration Settings

Environment variables and application configuration.
Includes LangSmith tracing setup for agent observability.
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App settings
    app_name: str = "Pocket Planner API"
    app_version: str = "2.0.0"
    debug: bool = True
    
    # API settings
    api_prefix: str = "/api/v1"
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Optimization defaults
    default_max_iterations: int = 5
    default_door_clearance: float = 60.0
    default_walking_path_width: float = 45.0
    
    # Google AI
    google_api_key: str = ""
    model_name: str = "gemini-2.5-pro"
    image_model_name: str = "gemini-2.5-flash-preview-05-20"
    
    # LangSmith Tracing
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "pocket-planner"
    langchain_endpoint: str = "https://api.smith.langchain.com"
    
    class Config:
        # Search both current dir and parent dir for .env
        env_file = (".env", "../.env", "../../.env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def setup_langsmith():
    """
    Setup LangSmith tracing environment variables.
    
    Call this at application startup to enable tracing.
    """
    settings = get_settings()
    
    if settings.langchain_api_key and settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
        print(f"✅ LangSmith tracing enabled for project: {settings.langchain_project}")
        return True
    else:
        print("⚠️ LangSmith tracing not configured (set LANGCHAIN_API_KEY)")
        return False
