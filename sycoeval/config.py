"""Load config.yaml and the .env file, and locate the project root."""

from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path | None = None) -> dict:
    """Read config.yaml and load OPENROUTER_API_KEY from .env into the environment."""
    load_dotenv(ROOT / ".env")
    with open(path or ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_path(relative: str) -> Path:
    """Turn a path from config.yaml (relative to the project root) into an absolute path."""
    return ROOT / relative
