"""The canonical Job record shared across all modules."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any


def _norm(text: str | None) -> str:
    """Normalize a string for stable identity comparison."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class Job:
    """A single discovered job posting.

    Fields are populated progressively: sources fill the raw discovery
    fields, the URL resolver fills apply_type/final_apply_url, and the
    ranker fills the score breakdown.
    """

    company: str
    role: str
    location: str
    source: str                      # "Adzuna" | "JSearch" | "Naukri"
    listing_url: str = ""            # original URL from the source
    description: str = ""
    salary: str = "Not Specified"
    experience_required: str = "Not Specified"
    posted_date: str = ""            # ISO date if known

    # Filled by URL resolver
    final_apply_url: str = ""
    apply_type: str = ""             # Naukri Apply | Indeed Apply |
                                     # Company Career Site | External Application Site

    # Company evaluation (never fabricated)
    industry: str = "Unknown"
    company_type: str = "Unknown"
    rating: str = "Unknown"
    review_count: str = "Unknown"
    sentiment: str = "Unknown"

    # Scoring
    match_score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    matched_skills: list[str] = field(default_factory=list)

    # LLM evaluation (the agentic layer; empty when LLM disabled)
    llm_fit_score: float | None = None
    llm_seniority: str = ""
    llm_missing_skills: list[str] = field(default_factory=list)
    llm_rationale: str = ""
    llm_recommended: bool = False

    # History flags (set during reconciliation)
    is_new: bool = False
    first_seen: str = ""
    last_seen: str = ""

    # ---------------------------------------------------------------
    @property
    def identity_raw(self) -> str:
        """Human-readable identity string: company + role + location + url."""
        url = self.final_apply_url or self.listing_url
        return f"{_norm(self.company)}|{_norm(self.role)}|{_norm(self.location)}|{_norm(url)}"

    @property
    def identity(self) -> str:
        """Stable hash used as the unique key in history CSV."""
        return hashlib.sha256(self.identity_raw.encode("utf-8")).hexdigest()[:16]

    @property
    def best_url(self) -> str:
        return self.final_apply_url or self.listing_url

    def to_history_row(self) -> dict[str, Any]:
        """Project to the exact CSV schema required by the spec."""
        return {
            "identity": self.identity,
            "company": self.company,
            "role": self.role,
            "location": self.location,
            "final_apply_url": self.best_url,
            "source": self.source,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "latest_match_score": round(self.match_score, 1),
        }

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
