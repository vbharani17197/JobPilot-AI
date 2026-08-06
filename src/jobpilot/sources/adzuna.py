"""Adzuna job search API source (primary, reliable).

Docs: https://developer.adzuna.com/
Endpoint: GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Auth: app_id + app_key as query params.
"""
from __future__ import annotations

import time

import requests

from ..logging_setup import logger
from ..models import Job
from .base import BaseSource

_BASE = "https://api.adzuna.com/v1/api/jobs"


class AdzunaSource(BaseSource):
    name = "adzuna"

    def _search(self, roles: list[str], keywords: list[str]) -> list[Job]:
        cfg = self.config["sources"]["adzuna"]
        app_id = self.config.adzuna_app_id
        app_key = self.config.adzuna_app_key

        if not app_id or not app_key:
            logger.warning(
                "[adzuna] ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env - skipping."
            )
            return []

        country = cfg.get("country", "in")
        per_query = int(cfg.get("results_per_query", 30))
        max_days = int(cfg.get("max_days_old", 30))
        prefs = self.config["candidate"]["preferred_locations"]

        jobs: list[Job] = []
        seen_ids: set[str] = set()

        # Query each role; bias toward preferred metros but don't exclude others.
        # We run one nationwide query per role (where='India') so remote and
        # other-city roles are still captured; location preference is handled
        # later in ranking, per the spec.
        for role in roles:
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "what": role,
                "where": "India",
                "results_per_page": per_query,
                "max_days_old": max_days,
                "sort_by": "date",
                "content-type": "application/json",
            }
            try:
                resp = requests.get(
                    f"{_BASE}/{country}/search/1", params=params, timeout=20
                )
                if resp.status_code == 429:
                    logger.warning("[adzuna] rate limited (429); stopping early.")
                    break
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                logger.warning("[adzuna] query '{}' failed: {}", role, exc)
                continue

            for item in data.get("results", []):
                jid = str(item.get("id", ""))
                if jid and jid in seen_ids:
                    continue
                seen_ids.add(jid)
                jobs.append(self._to_job(item, role))

            time.sleep(0.5)  # gentle pacing within free-tier limits

        return jobs

    # -----------------------------------------------------------------
    @staticmethod
    def _to_job(item: dict, role_query: str) -> Job:
        company = (item.get("company") or {}).get("display_name") or "Unknown"
        location = (item.get("location") or {}).get("display_name") or "India"
        title = item.get("title", role_query) or role_query

        salary = AdzunaSource._format_salary(
            item.get("salary_min"), item.get("salary_max")
        )
        posted = (item.get("created", "") or "")[:10]
        contract = item.get("contract_time") or item.get("contract_type") or ""
        category = (item.get("category") or {}).get("label", "")

        return Job(
            company=_clean(company),
            role=_clean(title),
            location=_clean(location),
            source="Adzuna",
            listing_url=item.get("redirect_url", ""),
            description=item.get("description", "") or "",
            salary=salary,
            experience_required="Not Specified",
            posted_date=posted,
            industry=category or "Unknown",
            company_type=contract.replace("_", " ").title() if contract else "Unknown",
        )

    @staticmethod
    def _format_salary(smin, smax) -> str:
        def lpa(v):
            try:
                return f"{float(v) / 100000:.1f} LPA"
            except (TypeError, ValueError):
                return None
        a, b = lpa(smin), lpa(smax)
        if a and b and a != b:
            return f"{a.split()[0]}-{b}"
        if a:
            return a
        if b:
            return b
        return "Not Specified"


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()
