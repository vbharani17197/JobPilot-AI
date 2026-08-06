"""Resume parsing: extract skills, certifications, experience, ATS keywords.

Resume-derived information always takes precedence over the configured
fallback skills. If the PDF cannot be read, we degrade gracefully to the
fallback list so the agent still runs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .logging_setup import logger

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None


@dataclass
class ResumeProfile:
    skills: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    ats_keywords: list[str] = field(default_factory=list)
    experience_years: float = 0.0
    raw_text: str = ""
    source: str = "fallback"   # "resume" if PDF parsed, else "fallback"


# Common cert phrasing patterns to pull out of resume text.
_CERT_PATTERNS = [
    r"AWS Certified[^\n.]*",
    r"Site Reliability Engineering[^\n.]*",
    r"(?:Lean )?Six Sigma[^\n.]*",
    r"Certified Kubernetes[^\n.]*",
    r"Azure[^\n.]*Certif[^\n.]*",
    r"Google Cloud[^\n.]*Certif[^\n.]*",
    r"ITIL[^\n.]*Certif[^\n.]*",
]


def parse_resume(config: Config) -> ResumeProfile:
    """Parse the resume PDF; fall back to config seed skills on any failure."""
    path = config.resume_path
    taxonomy: dict[str, list[str]] = config.get("skills_taxonomy", {})

    text = _extract_text(path)
    if not text:
        logger.warning(
            "Resume not parsed from {} - using fallback skills from config.", path
        )
        return _fallback_profile(config)

    skills = _match_taxonomy(text, taxonomy)
    certs = _extract_certs(text)
    exp = _extract_experience_years(text) or float(
        config["candidate"]["experience_years"]
    )
    ats = _build_ats_keywords(text, skills, taxonomy)

    # Merge fallback skills the resume text might phrase differently, but
    # resume-found skills lead the list (precedence).
    fallback = config["resume"].get("fallback_skills", [])
    merged_skills = _dedupe_preserve(skills + [s for s in fallback if s not in skills])

    logger.info(
        "Resume parsed: {} skills, {} certifications, {:.1f} yrs experience.",
        len(merged_skills), len(certs), exp,
    )
    return ResumeProfile(
        skills=merged_skills,
        certifications=certs or config["resume"].get("fallback_certifications", []),
        technologies=skills,
        ats_keywords=ats,
        experience_years=exp,
        raw_text=text,
        source="resume",
    )


# ---------------------------------------------------------------------------
def _extract_text(path: Path) -> str:
    if pdfplumber is None:
        logger.error("pdfplumber not installed; cannot read resume.")
        return ""
    if not path.exists():
        logger.warning("Resume file does not exist at {}.", path)
        return ""
    try:
        parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        logger.error("Failed to read resume PDF: {}", exc)
        return ""


def _match_taxonomy(text: str, taxonomy: dict[str, list[str]]) -> list[str]:
    low = text.lower()
    found: list[str] = []
    for canonical, aliases in taxonomy.items():
        needles = [canonical.lower()] + [a.lower() for a in aliases]
        if any(re.search(rf"\b{re.escape(n)}\b", low) for n in needles):
            found.append(canonical)
    return found


def _extract_certs(text: str) -> list[str]:
    certs: list[str] = []
    for pat in _CERT_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            cleaned = m.group(0).strip(" -•\t")
            if cleaned and cleaned not in certs:
                certs.append(cleaned)
    return certs


def _extract_experience_years(text: str) -> float | None:
    """Look for patterns like '6+ years' or '6 years 5 months'."""
    m = re.search(r"(\d+)\s*(?:years|yrs)\s*(?:and\s*)?(\d+)\s*months?", text, re.I)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 12.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", text, re.I)
    if m:
        return float(m.group(1))
    return None


def _build_ats_keywords(text: str, skills: list[str],
                        taxonomy: dict[str, list[str]]) -> list[str]:
    """ATS keywords = matched canonical skills plus salient domain nouns."""
    domain_terms = [
        "SLA", "MTTR", "RCA", "24x7", "high availability", "observability",
        "incident", "monitoring", "deployment", "rollback", "runbook",
        "production support", "reliability", "automation", "cloud",
    ]
    low = text.lower()
    extra = [t for t in domain_terms if t.lower() in low]
    return _dedupe_preserve(skills + extra)


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _fallback_profile(config: Config) -> ResumeProfile:
    skills = config["resume"].get("fallback_skills", [])
    return ResumeProfile(
        skills=skills,
        certifications=config["resume"].get("fallback_certifications", []),
        technologies=skills,
        ats_keywords=skills,
        experience_years=float(config["candidate"]["experience_years"]),
        raw_text="",
        source="fallback",
    )
