"""Base class for all job sources.

Contract: ``search()`` must NEVER raise. On any failure it logs and returns
an empty list, so one broken source never aborts the daily run.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..logging_setup import logger
from ..models import Job


class BaseSource(ABC):
    name: str = "base"

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    def _search(self, roles: list[str], keywords: list[str]) -> list[Job]:
        """Implement the actual search. May raise; the wrapper handles it."""

    def search(self, roles: list[str], keywords: list[str]) -> list[Job]:
        """Failure-isolated entry point used by the orchestrator."""
        try:
            jobs = self._search(roles, keywords)
            logger.info("[{}] returned {} job(s).", self.name, len(jobs))
            return jobs
        except Exception as exc:  # noqa: BLE001
            logger.error("[{}] failed: {} - continuing with other sources.",
                         self.name, exc)
            return []

    @property
    def enabled(self) -> bool:
        return bool(self.config["sources"].get(self.name, {}).get("enabled", False))
