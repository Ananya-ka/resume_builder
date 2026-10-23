import os
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict

backend_dir = Path(__file__).resolve().parent.parent.parent

# Explicitly load backend/.env with override=True so stale shell environment variables
# (such as an old revoked OPENAI_API_KEY exported in ~/.zshrc) do not shadow project config.
active_env = backend_dir / ".env" if (backend_dir / ".env").exists() else (backend_dir.parent / ".env")
if active_env.exists():
    load_dotenv(active_env, override=True)
    vals = dotenv_values(active_env)
    if "OPENAI_API_KEY" in vals and not vals["OPENAI_API_KEY"]:
        os.environ["OPENAI_API_KEY"] = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(backend_dir / ".env", backend_dir.parent / ".env"),
        extra="ignore",
    )
    DATABASE_URL: str = "postgresql://localhost:5433/resume_copilot"
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-2025-04-14"
    ENVIRONMENT: str = "development"


settings = Settings()
