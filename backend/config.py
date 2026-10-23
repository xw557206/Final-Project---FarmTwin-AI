from pathlib import Path
import os

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent


def load_config() -> dict[str, str]:
    """Load parent .env first, then root .env so root values win."""
    values: dict[str, str] = {}
    for path in (PARENT / ".env", ROOT / ".env"):
        if path.exists():
            values.update({k: v for k, v in dotenv_values(path).items() if v is not None})
    values.update({k: v for k, v in os.environ.items() if k in {"DATABASE_URL", "PORT", "PORTKEY_API_KEY", "PORTKEY_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"}})
    return values


CONFIG = load_config()
DATABASE_PATH = ROOT / "data" / "farmtwin.db"

