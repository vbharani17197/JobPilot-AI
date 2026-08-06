"""Resolve the most useful application URL and classify Apply Type.

Implements the spec's 4-scenario priority:
  1. Final company application URL (Workday/Greenhouse/Lever/...)
  2. Final third-party ATS URL
  3. Naukri job URL
  4. Indeed/aggregator job URL

We follow redirects (capped) to discover whether a listing ultimately points
at a known ATS or a company career domain. We never fabricate a URL; if we
cannot resolve, we keep the original listing URL.
"""
from __future__ import annotations

from urllib.parse import urlparse

import requests

from .config import Config
from .logging_setup import logger
from .models import Job

# Known ATS host fragments -> friendly platform name.
_ATS_HOSTS = {
    "myworkdayjobs.com": "Workday",
    "workday.com": "Workday",
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "taleo.net": "Taleo",
    "smartrecruiters.com": "SmartRecruiters",
    "successfactors.com": "SuccessFactors",
    "successfactors.eu": "SuccessFactors",
    "icims.com": "iCIMS",
    "jobvite.com": "Jobvite",
    "ashbyhq.com": "Ashby",
    "workable.com": "Workable",
    "bamboohr.com": "BambooHR",
    "oraclecloud.com": "Oracle Recruiting",
    "zohorecruit.com": "Zoho Recruit",
    "darwinbox.com": "Darwinbox",
}

_AGG_HOSTS = ("naukri.com", "indeed.", "adzuna.", "glassdoor.",
              "linkedin.com", "ziprecruiter.")

# Career-page URL hints that indicate a *specific* posting (good) vs a
# generic landing page (bad, per spec).
_GENERIC_PATH_HINTS = ("/careers", "/jobs", "/career", "/job-search")


class UrlResolver:
    def __init__(self, config: Config):
        self.cfg = config.get("url_resolution", {})
        self.enabled = bool(self.cfg.get("enabled", True))
        self.max_redirects = int(self.cfg.get("max_redirects", 5))
        self.timeout = int(self.cfg.get("timeout_seconds", 10))

    def resolve(self, job: Job) -> Job:
        """Populate job.final_apply_url and job.apply_type."""
        listing = job.listing_url or ""

        # Default classification by source before any resolution.
        default_type = self._default_apply_type(job.source, listing)

        if not self.enabled or not listing:
            job.final_apply_url = listing
            job.apply_type = default_type
            return job

        final_url = self._follow(listing)
        host = _host(final_url)

        ats_name = self._match_ats(host)
        if ats_name:
            job.final_apply_url = final_url
            # Workday/Greenhouse/Lever/etc. hosted on a company subdomain are
            # effectively the company's career site application.
            job.apply_type = "Company Career Site"
            return job

        if host and not self._is_aggregator(host):
            # Redirected off the aggregator to some other domain. If it looks
            # like a specific posting (has a path beyond a generic landing),
            # treat it as a company career site; else keep the aggregator URL.
            if self._looks_specific(final_url):
                job.final_apply_url = final_url
                job.apply_type = "Company Career Site"
                return job

        # Could not improve on the listing URL.
        job.final_apply_url = listing
        job.apply_type = default_type
        return job

    # -----------------------------------------------------------------
    def _follow(self, url: str) -> str:
        try:
            resp = requests.head(
                url, allow_redirects=True, timeout=self.timeout,
                headers={"user-agent": "Mozilla/5.0 (JobPilot-AI)"},
            )
            # Some servers don't support HEAD; fall back to GET.
            if resp.status_code >= 400 or not resp.url:
                resp = requests.get(
                    url, allow_redirects=True, timeout=self.timeout, stream=True,
                    headers={"user-agent": "Mozilla/5.0 (JobPilot-AI)"},
                )
            return resp.url or url
        except requests.RequestException as exc:
            logger.debug("URL resolve failed for {}: {}", url, exc)
            return url

    @staticmethod
    def _match_ats(host: str) -> str | None:
        for frag, name in _ATS_HOSTS.items():
            if frag in host:
                return name
        return None

    @staticmethod
    def _is_aggregator(host: str) -> bool:
        return any(a in host for a in _AGG_HOSTS)

    @staticmethod
    def _looks_specific(url: str) -> bool:
        path = urlparse(url).path.rstrip("/")
        if not path or path in _GENERIC_PATH_HINTS:
            return False
        # Specific postings usually carry an id/slug segment.
        segments = [s for s in path.split("/") if s]
        return len(segments) >= 2

    @staticmethod
    def _default_apply_type(source: str, listing: str) -> str:
        host = _host(listing)
        if "naukri.com" in host or source == "Naukri":
            return "Naukri Apply"
        if "indeed." in host:
            return "Indeed Apply"
        if source in ("Adzuna", "JSearch"):
            return "External Application Site"
        return "External Application Site"


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001
        return ""
