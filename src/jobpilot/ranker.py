"""Ranking engine: Match Score out of 100.

Weights (from config):
  Skill Match        40
  Experience Match   20
  ATS Compatibility  15
  Job Relevance      10
  Company Assessment 10
  Location Pref       5

Each component returns 0..1 and is multiplied by its weight; the sum is the
Match Score. Missing data is handled neutrally so it never unfairly sinks a
job (e.g. Unknown rating -> neutral company score).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from .config import Config
from .models import Job
from .resume_parser import ResumeProfile


class Ranker:
    def __init__(self, config: Config, profile: ResumeProfile):
        self.config = config
        self.profile = profile
        self.weights = config["ranking"]["weights"]
        self.taxonomy = config.get("skills_taxonomy", {})
        self.high_relevance = [t.lower() for t in
                               config.get("high_relevance_titles", [])]
        self.pref_locations = [l.lower() for l in
                               config["candidate"]["preferred_locations"]]
        self.cand_exp = float(config["candidate"]["experience_years"])
        self.recency_tiers = config["ranking"].get("recency_tiers_days",
                                                   [1, 3, 7, 14])
        self.llm_blend = float(config.get("llm", {}).get("blend_weight", 0.0))

        # Precompute alias -> canonical lookup for skill matching.
        self._alias_map: dict[str, str] = {}
        for canon, aliases in self.taxonomy.items():
            self._alias_map[canon.lower()] = canon
            for a in aliases:
                self._alias_map[a.lower()] = canon

    def score(self, job: Job) -> Job:
        text = f"{job.role} {job.description}".lower()

        skill, matched = self._skill_match(text)
        experience = self._experience_match(job)
        ats = self._ats_match(text)
        relevance = self._relevance(job)
        company = self._company(job)
        location = self._location(job)

        w = self.weights
        breakdown = {
            "skill_match": round(skill * w["skill_match"], 1),
            "experience_match": round(experience * w["experience_match"], 1),
            "ats_compatibility": round(ats * w["ats_compatibility"], 1),
            "job_relevance": round(relevance * w["job_relevance"], 1),
            "company_assessment": round(company * w["company_assessment"], 1),
            "location_preference": round(location * w["location_preference"], 1),
        }
        job.match_score = round(sum(breakdown.values()), 1)
        job.score_breakdown = breakdown
        job.matched_skills = matched
        return job

    # ---- components --------------------------------------------------
    def _skill_match(self, text: str) -> tuple[float, list[str]]:
        """Fraction of the candidate's skills present in the job text."""
        skills = self.profile.skills or []
        if not skills:
            return 0.0, []
        matched: list[str] = []
        for s in skills:
            canon = s.lower()
            aliases = [canon]
            # include taxonomy aliases for this skill if known
            if s in self.taxonomy:
                aliases += [a.lower() for a in self.taxonomy[s]]
            if any(re.search(rf"\b{re.escape(a)}\b", text) for a in aliases):
                matched.append(s)
        # Normalize against a reasonable expectation (a job won't list all
        # 25+ skills). Cap denominator so strong overlap reaches ~1.0.
        denom = min(len(skills), 12)
        frac = min(len(matched) / denom, 1.0) if denom else 0.0
        return frac, matched

    def _experience_match(self, job: Job) -> float:
        req = _parse_required_years(job.experience_required) or \
              _parse_required_years(job.description)
        if req is None:
            return 0.8  # neutral-positive when unstated
        lo, hi = req
        if lo <= self.cand_exp <= hi:
            return 1.0
        # Graceful falloff outside the band.
        if self.cand_exp < lo:
            gap = lo - self.cand_exp
            return max(0.0, 1.0 - gap * 0.25)
        gap = self.cand_exp - hi
        return max(0.3, 1.0 - gap * 0.15)  # overqualified penalized mildly

    def _ats_match(self, text: str) -> float:
        kws = self.profile.ats_keywords or []
        if not kws:
            return 0.5
        hits = sum(1 for k in kws if k.lower() in text)
        denom = min(len(kws), 10)
        return min(hits / denom, 1.0) if denom else 0.5

    def _relevance(self, job: Job) -> float:
        role = job.role.lower()
        base = 0.4
        if any(h in role for h in self.high_relevance):
            base = 1.0
        elif any(w in role for w in ("support", "operations", "reliability",
                                     "devops", "infrastructure", "monitoring")):
            base = 0.7
        rule_relevance = base * self._recency_factor(job)

        # Blend in the LLM's holistic fit assessment when present. This is what
        # makes the agent's ranking reflect genuine reasoning about each role
        # rather than keyword presence alone.
        if job.llm_fit_score is not None and self.llm_blend > 0:
            llm_relevance = max(0.0, min(job.llm_fit_score / 100.0, 1.0))
            return (1 - self.llm_blend) * rule_relevance + \
                   self.llm_blend * llm_relevance * self._recency_factor(job)
        return rule_relevance

    def _recency_factor(self, job: Job) -> float:
        days = _days_since(job.posted_date)
        if days is None:
            return 0.9
        tiers = self.recency_tiers
        if days <= tiers[0]:
            return 1.0
        if days <= tiers[1]:
            return 0.95
        if days <= tiers[2]:
            return 0.9
        if days <= tiers[3]:
            return 0.85
        return 0.75

    def _company(self, job: Job) -> float:
        """Neutral 0.5 when rating Unknown; scale 0..1 from a 1-5 rating."""
        if job.rating in ("", "Unknown", None):
            return 0.5
        try:
            r = float(job.rating)
            return max(0.0, min(r / 5.0, 1.0))
        except ValueError:
            return 0.5

    def _location(self, job: Job) -> float:
        loc = job.location.lower()
        if "remote" in loc or "remote" in job.description.lower()[:400]:
            return 1.0
        if any(p in loc for p in self.pref_locations):
            return 1.0
        return 0.3  # other locations still allowed, just lower preference


# ---- helpers ---------------------------------------------------------
def _parse_required_years(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None
    t = text.lower()
    m = re.search(r"(\d+)\s*[-to]+\s*(\d+)\s*(?:years|yrs)", t)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)\s*\+\s*(?:years|yrs)", t)
    if m:
        return float(m.group(1)), float(m.group(1)) + 5
    m = re.search(r"(\d+)\s*(?:years|yrs)", t)
    if m:
        v = float(m.group(1))
        return v, v + 2
    return None


def _days_since(iso_date: str) -> int | None:
    if not iso_date:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            d = datetime.strptime(iso_date[:len(fmt)], fmt).date()
            return (date.today() - d).days
        except ValueError:
            continue
    return None
