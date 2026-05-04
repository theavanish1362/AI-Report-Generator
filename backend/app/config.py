# ai-report-generator/backend/app/config.py
import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "4000"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    DEEPSEEK_THINKING: bool = os.getenv("DEEPSEEK_THINKING", "False").lower() == "true"

    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "generated_reports")
    CHARTS_DIR: str = os.getenv("CHARTS_DIR", "generated_charts")
    MAX_DESCRIPTION_LENGTH: int = 5000

    class Config:
        case_sensitive = True


settings = Settings()
