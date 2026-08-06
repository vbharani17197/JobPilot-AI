"""Naukri best-effort scraper (BONUS source).

IMPORTANT EXPECTATIONS
----------------------
Naukri actively employs bot protection. This module is intentionally
best-effort: when Naukri blocks the request or changes its internal API,
this source logs a warning and contributes ZERO rows. The rest of the
daily run is unaffected (see BaseSource.search failure isolation).

It uses Naukri's internal JSON endpoint (the same one their website calls)
rather than HTML scraping, because that is far less brittle than parsing
markup. If that endpoint changes, update the URL/headers below. Claude Code
running on your machine can re-tune this against the live site.

This is the part of the system most likely to need occasional maintenance.
"""
from __future__ import annotations

import time
from urllib.parse import quote

import requests

from ..logging_setup import logger
from ..models import Job
from .base import BaseSource

# Naukri's internal search API used by their SPA frontend.
_API = "https://www.naukri.com/jobapi/v3/search"

# Headers that mimic a real browser session. The appid/systemid values are
# the public constants Naukri's own frontend sends.
_HEADERS = {
    "accept": "application/json",
    "appid": "109",
    "systemid": "Naukri",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "referer": "https://www.naukri.com/",
}


class NaukriSource(BaseSource):
    name = "naukri"

    def _search(self, roles: list[str], keywords: list[str]) -> list[Job]:
        cfg = self.config["sources"]["naukri"]
        max_pages = int(cfg.get("max_pages", 2))
        delay = float(cfg.get("request_delay_seconds", 3))

        # Use a focused subset of keywords to limit request volume and reduce
        # the chance of being throttled. These map well to the target roles.
        queries = ["site reliability engineer", "production support",
                   "application support", "devops support engineer"]

        jobs: list[Job] = []
        seen: set[str] = set()

        session = requests.Session()
        session.headers.update(_HEADERS)

        for q in queries:
            for page in range(1, max_pages + 1):
                params = {
                    "noOfResults": 20,
                    "urlType": "search_by_keyword",
                    "searchType": "adv",
                    "keyword": q,
                    "pageNo": page,
                    "k": q,
                    "seoKey": quote(q.replace(" ", "-")) + "-jobs",
                    "src": "jobsearchDesk",
                    "latLong": "",
                }
                try:
                    resp = session.get(_API, params=params, timeout=15)
                    if resp.status_code in (401, 403, 429):
                        logger.warning(
                            "[naukri] blocked (HTTP {}) on '{}' - skipping source. "
                            "This is expected periodically.", resp.status_code, q
                        )
                        return jobs  # bail politely; keep whatever we have
                    resp.raise_for_status()
                    data = resp.json()
                except (requests.RequestException, ValueError) as exc:
                    logger.warning("[naukri] '{}' page {} failed: {}", q, page, exc)
                    break  # move to next query

                details = data.get("jobDetails") or data.get("jobs") or []
                if not details:
                    break

                for item in details:
                    job = self._to_job(item)
                    if job is None:
                        continue
                    key = job.listing_url or job.identity_raw
                    if key in seen:
                        continue
                    seen.add(key)
                    jobs.append(job)

                time.sleep(delay)

        return jobs

    # -----------------------------------------------------------------
    @staticmethod
    def _to_job(item: dict) -> Job | None:
        try:
            title = item.get("title") or item.get("jobTitle") or ""
            company = item.get("companyName") or item.get("company") or "Unknown"
            if not title:
                return None

            # Location & experience live in placeholders on Naukri's payload.
            location = "India"
            experience = "Not Specified"
            salary = "Not Specified"
            for ph in item.get("placeholders", []) or []:
                ptype = ph.get("type")
                label = ph.get("label", "")
                if ptype == "location":
                    location = label or location
                elif ptype == "experience":
                    experience = label or experience
                elif ptype == "salary":
                    salary = label or salary

            jdurl = item.get("jdURL") or item.get("jobUrl") or ""
            if jdurl and jdurl.startswith("/"):
                jdurl = "https://www.naukri.com" + jdurl

            rating = "Unknown"
            reviews = "Unknown"
            amb = item.get("ambitionBoxData") or {}
            if amb.get("AggregateRating"):
                rating = str(amb["AggregateRating"])
            if amb.get("ReviewsCount"):
                reviews = str(amb["ReviewsCount"])

            return Job(
                company=_clean(company),
                role=_clean(title),
                location=_clean(location),
                source="Naukri",
                listing_url=jdurl,
                description=item.get("jobDescription", "") or "",
                salary=salary,
                experience_required=experience,
                rating=rating,
                review_count=reviews,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[naukri] could not parse an item: {}", exc)
            return None


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()
