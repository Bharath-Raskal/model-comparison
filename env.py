"""Loads .env (KEY=value lines) into the environment. Values already set in the shell win."""
import os
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"


def load_env():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
