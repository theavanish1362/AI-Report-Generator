# ai-report-generator/backend/app/config.py
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "4000"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    
    # Application Settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "generated_reports")
    CHARTS_DIR: str = os.getenv("CHARTS_DIR", "generated_charts")
    MAX_DESCRIPTION_LENGTH: int = 5000
    
    class Config:
        case_sensitive = True

settings = Settings()