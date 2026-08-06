"""JSearch (RapidAPI) source - optional second API.

JSearch aggregates listings from Indeed, Glassdoor, LinkedIn, ZipRecruiter
and others (via Google for Jobs) into one legal API, giving Indeed coverage
without scraping Indeed directly. Disabled by default; enable in settings.yaml
after adding a RapidAPI key (JSEARCH_API_KEY) to .env.

Uses the current /search-v2 endpoint (the older /search path returns 404).
Key differences from the legacy endpoint:
  - path is /search-v2
  - location goes via country + language params, not baked into the query
  - pagination is cursor-based (a 'cursor' value returned per response) rather
    than page/num_pages

Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
      https://www.openwebninja.com/api/jsearch/docs

Free tier note: 200 requests/month. This source fires one request per target
role per run, so keep an eye on the monthly budget if you run frequently.
"""
from __future__ import annotations

import time

import requests

from ..logging_setup import logger
from ..models import Job
from .base import BaseSource

_HOST = "jsearch.p.rapidapi.com"
_URL = f"https://{_HOST}/search-v2"


class JSearchSource(BaseSource):
    name = "jsearch"

    def _search(self, roles: list[str], keywords: list[str]) -> list[Job]:
        cfg = self.config["sources"]["jsearch"]
        api_key = self.config.jsearch_api_key
        if not api_key:
            logger.warning("[jsearch] JSEARCH_API_KEY not set - skipping.")
            return []

        country = cfg.get("country", "in")
        language = cfg.get("language", "en")
        date_posted = cfg.get("date_posted", "month")
        # How many extra cursor pages to pull per role (0 = first page only).
        # Each page is one request against the monthly quota, so default low.
        max_extra_pages = int(cfg.get("max_extra_pages", 0))

        headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": _HOST}

        jobs: list[Job] = []
        seen: set[str] = set()

        for role in roles:
            cursor: str | None = None
            pages_fetched = 0

            while True:
                params = {
                    "query": f"{role} in India",
                    "country": country,
                    "language": language,
                    "date_posted": date_posted,
                }
                if cursor:
                    params["cursor"] = cursor

                try:
                    resp = requests.get(_URL, headers=headers, params=params,
                                        timeout=45)
                    if resp.status_code == 429:
                        logger.warning("[jsearch] rate limited (429); stopping early.")
                        return jobs
                    if resp.status_code == 404:
                        logger.warning(
                            "[jsearch] 404 on /search-v2 for '{}'. Check the key is "
                            "subscribed to JSearch on RapidAPI.", role)
                        return jobs
                    resp.raise_for_status()
                    data = resp.json()
                except requests.RequestException as exc:
                    logger.warning("[jsearch] query '{}' failed: {}", role, exc)
                    break  # move to next role

                # v2 response shape can vary; locate the job list defensively.
                items = _extract_items(data)
                if items and not isinstance(items[0], dict):
                    logger.warning(
                        "[jsearch] '{}': unexpected item type {} - skipping. "
                        "Top-level keys: {}", role, type(items[0]).__name__,
                        list(data.keys()) if isinstance(data, dict) else type(data).__name__)
                    items = [it for it in items if isinstance(it, dict)]

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    jid = item.get("job_id", "")
                    if jid and jid in seen:
                        continue
                    if jid:
                        seen.add(jid)
                    jobs.append(self._to_job(item, role))

                cursor = None
                if isinstance(data, dict):
                    cursor = data.get("cursor") or data.get("next_cursor")
                pages_fetched += 1
                if not cursor or pages_fetched > max_extra_pages:
                    break
                time.sleep(0.6)

            time.sleep(0.4)

        return jobs

    @staticmethod
    def _to_job(item: dict, role_query: str) -> Job:
        loc_parts = [
            item.get("job_city"),
            item.get("job_state"),
            item.get("job_country"),
        ]
        location = ", ".join(p for p in loc_parts if p) or "India"

        salary = "Not Specified"
        smin, smax = item.get("job_min_salary"), item.get("job_max_salary")
        if smin or smax:
            def lpa(v):
                try:
                    return f"{float(v) / 100000:.1f}"
                except (TypeError, ValueError):
                    return None
            a, b = lpa(smin), lpa(smax)
            if a and b:
                salary = f"{a}-{b} LPA"
            elif a or b:
                salary = f"{a or b} LPA"

        # v2 returns richer fields; prefer a direct apply link when available.
        apply_link = item.get("job_apply_link", "") or ""
        if not apply_link:
            opts = item.get("apply_options") or []
            if opts and isinstance(opts, list):
                apply_link = opts[0].get("apply_link", "") or ""

        publisher = item.get("job_publisher", "")
        rating = "Unknown"
        reviews = "Unknown"
        # v2 includes employer_reviews; take the first with a score if present.
        for rev in item.get("employer_reviews", []) or []:
            if rev.get("score"):
                rating = str(rev["score"])
                if rev.get("review_count"):
                    reviews = str(rev["review_count"])
                break

        return Job(
            company=item.get("employer_name") or "Unknown",
            role=item.get("job_title") or role_query,
            location=location,
            source="JSearch",
            listing_url=apply_link,
            description=item.get("job_description", "") or "",
            salary=salary,
            experience_required=(
                f"{item.get('required_experience_years')}+ years"
                if item.get("required_experience_years") else "Not Specified"
            ),
            posted_date=(item.get("job_posted_at_datetime_utc", "") or "")[:10],
            industry=item.get("industry") or "Unknown",
            company_type=publisher or "Unknown",
            rating=rating,
            review_count=reviews,
        )
def _extract_items(data) -> list:
    """Find the list of job objects in a v2 response, defensively."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("data", "results", "jobs", "items"):
        val = data.get(key)
        if isinstance(val, list):
            return val
    for val in data.values():
        if isinstance(val, list):
            return val
    return []