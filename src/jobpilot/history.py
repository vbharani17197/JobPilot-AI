"""CSV-based history: persistence, deduplication, new-job detection.

No database. The history file uses the spec's 8 columns plus an internal
'identity' hash column for stable matching. Identity =
company + role + location + final_apply_url (normalized & hashed).
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from .logging_setup import logger
from .models import Job

_FIELDS = [
    "identity",          # internal stable key (hash)
    "company",
    "role",
    "location",
    "final_apply_url",
    "source",
    "first_seen",
    "last_seen",
    "latest_match_score",
]


class HistoryManager:
    def __init__(self, csv_path: Path, retention_days: int = 0):
        self.csv_path = csv_path
        # retention_days = 0 means keep everything (no pruning).
        self.retention_days = int(retention_days or 0)
        self.records: dict[str, dict] = {}
        self._load()

    # -----------------------------------------------------------------
    def _load(self) -> None:
        if not self.csv_path.exists():
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=_FIELDS).writeheader()
            logger.info("Created new history file at {}.", self.csv_path)
            return

        with open(self.csv_path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                key = row.get("identity") or row.get("final_apply_url", "")
                if key:
                    self.records[key] = row
        logger.info("Loaded {} historical job(s).", len(self.records))

    # -----------------------------------------------------------------
    def reconcile(self, jobs: list[Job]) -> list[Job]:
        """Dedupe today's jobs, flag new ones, update first/last seen.

        Returns the deduplicated job list with is_new / first_seen / last_seen
        populated. Mutates internal records so save() persists the update.
        """
        today = date.today().isoformat()
        deduped: dict[str, Job] = {}

        # Deduplicate within today's batch first (keep highest score).
        for job in jobs:
            key = job.identity
            if key in deduped:
                if job.match_score > deduped[key].match_score:
                    deduped[key] = job
            else:
                deduped[key] = job

        result: list[Job] = []
        for key, job in deduped.items():
            existing = self.records.get(key)
            if existing:
                job.is_new = False
                job.first_seen = existing.get("first_seen", today)
                job.last_seen = today
            else:
                job.is_new = True
                job.first_seen = today
                job.last_seen = today

            # Update in-memory record store.
            self.records[key] = job.to_history_row()
            result.append(job)

        new_count = sum(1 for j in result if j.is_new)
        logger.info("Reconciled: {} unique job(s), {} new since last run.",
                    len(result), new_count)
        return result

    # -----------------------------------------------------------------
    def _prune(self) -> int:
        """Drop records whose last_seen is older than retention_days.

        Returns the number of records removed. No-op when retention_days<=0.
        """
        if self.retention_days <= 0:
            return 0
        cutoff = date.today() - timedelta(days=self.retention_days)
        removed = 0
        for key in list(self.records.keys()):
            last_seen = self.records[key].get("last_seen", "")
            try:
                seen = datetime.strptime(last_seen[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                # Unparseable date -> keep it rather than risk data loss.
                continue
            if seen < cutoff:
                del self.records[key]
                removed += 1
        if removed:
            logger.info("Pruned {} job(s) older than {} days.",
                        removed, self.retention_days)
        return removed

#    def save(self) -> None:
#        self._prune()
#        tmp = self.csv_path.with_suffix(".tmp")
#        with open(tmp, "w", newline="", encoding="utf-8") as fh:
#            writer = csv.DictWriter(fh, fieldnames=_FIELDS)
#            writer.writeheader()
#            for rec in self.records.values():
#                writer.writerow({k: rec.get(k, "") for k in _FIELDS})
#        tmp.replace(self.csv_path)
#        logger.info("Saved history: {} total record(s).", len(self.records))
    def _prune(self) -> int:
        """Drop records whose last_seen is older than retention_days."""
        if self.retention_days <= 0:
            return 0
        cutoff = date.today() - timedelta(days=self.retention_days)
        removed = 0
        for key in list(self.records.keys()):
            last_seen = self.records[key].get("last_seen", "")
            try:
                seen = datetime.strptime(last_seen[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue
            if seen < cutoff:
                del self.records[key]
                removed += 1
        if removed:
            logger.info("Pruned {} job(s) older than {} days.",
                        removed, self.retention_days)
        return removed

    def save(self) -> None:
        self._prune()
        tmp = self.csv_path.with_suffix(".tmp")