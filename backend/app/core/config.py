import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    DB_URL: str = os.getenv("DB_URL", "sqlite:///./data.db")
    MOCK_EXTERNALS: bool = os.getenv("MOCK_EXTERNALS", "true").lower() == "true"
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    CAL_API_KEY: str | None = os.getenv("CAL_API_KEY")
    CAL_CALENDAR_ID: str | None = os.getenv("CAL_CALENDAR_ID")
    PIPEFY_API_TOKEN: str | None = os.getenv("PIPEFY_API_TOKEN")
    PIPEFY_PIPE_ID: str | None = os.getenv("PIPEFY_PIPE_ID")
    PIPEFY_STAGE_ID_PREVENDAS: str | None = os.getenv("PIPEFY_STAGE_ID_PREVENDAS")

settings = Settings()
