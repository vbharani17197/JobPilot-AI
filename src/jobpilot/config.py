"""Configuration loading and validation."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class Config:
    """Parsed configuration plus resolved project paths and secrets."""

    raw: dict[str, Any]
    project_root: Path

    # Secrets pulled from environment
    adzuna_app_id: str | None = field(default=None)
    adzuna_app_key: str | None = field(default=None)
    jsearch_api_key: str | None = field(default=None)
    anthropic_api_key: str | None = field(default=None)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    # --- convenience resolved paths -------------------------------------
    def path(self, key: str) -> Path:
        """Resolve a configured relative path against the project root."""
        rel = self.raw["paths"][key]
        return (self.project_root / rel).resolve()

    @property
    def history_csv(self) -> Path:
        return self.path("history_csv")

    @property
    def output_dir(self) -> Path:
        return self.path("output_dir")

    @property
    def log_file(self) -> Path:
        return self.path("log_file")

    @property
    def resume_path(self) -> Path:
        return (self.project_root / self.raw["resume"]["path"]).resolve()


def load_config(config_path: str | Path | None = None) -> Config:
    """Load YAML config, environment secrets, and validate critical fields.

    The project root is inferred as the parent of the ``config`` directory,
    so the agent works regardless of the current working directory.
    """
    if config_path is None:
        # Default: <project_root>/config/settings.yaml
        config_path = Path(__file__).resolve().parents[2] / "config" / "settings.yaml"
    config_path = Path(config_path).resolve()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    project_root = config_path.parents[1]  # .../JobPilot-AI

    # Load .env from project root if present.
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()  # fall back to process environment

    with open(config_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    _validate(raw)

    return Config(
        raw=raw,
        project_root=project_root,
        adzuna_app_id=os.getenv("ADZUNA_APP_ID"),
        adzuna_app_key=os.getenv("ADZUNA_APP_KEY"),
        jsearch_api_key=os.getenv("JSEARCH_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


def _validate(raw: dict[str, Any]) -> None:
    """Fail fast on obviously broken configuration."""
    weights = raw.get("ranking", {}).get("weights", {})
    total = sum(weights.values())
    if round(total) != 100:
        raise ValueError(
            f"Ranking weights must sum to 100, got {total}. Check config/settings.yaml."
        )

    required_sections = ["candidate", "target_roles", "sources", "ranking", "paths"]
    missing = [s for s in required_sections if s not in raw]
    if missing:
        raise ValueError(f"Config missing required sections: {missing}")
