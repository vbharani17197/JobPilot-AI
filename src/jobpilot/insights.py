"""Aggregate skill/ATS insights across the day's jobs (Worksheet 4).

Produces:
  - Most Requested Skills      (skills you HAVE, by demand frequency)
  - Trending Technologies      (taxonomy terms appearing across postings)
  - Missing Skills             (in-demand terms NOT on your resume)
  - Frequently Requested Certifications
  - ATS Keyword Recommendations

Nothing here is fabricated; everything is counted from real job descriptions.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .config import Config
from .models import Job
from .resume_parser import ResumeProfile


@dataclass
class Insights:
    most_requested_skills: list[tuple[str, int]] = field(default_factory=list)
    trending_technologies: list[tuple[str, int]] = field(default_factory=list)
    missing_skills: list[tuple[str, int]] = field(default_factory=list)
    certifications: list[tuple[str, int]] = field(default_factory=list)
    ats_recommendations: list[str] = field(default_factory=list)


# Common cert keywords to count across descriptions.
_CERT_TERMS = [
    "AWS Certified", "Azure", "GCP", "CKA", "CKAD", "Kubernetes",
    "RHCSA", "RHCE", "ITIL", "Six Sigma", "Terraform Associate",
    "CompTIA", "PMP",
]

# Broad tech vocabulary to detect "trending" tools even if not on the resume.
_TECH_VOCAB = [
    "kubernetes", "docker", "terraform", "ansible", "prometheus", "grafana",
    "splunk", "datadog", "new relic", "elk", "elasticsearch", "kafka",
    "jenkins", "gitlab", "github actions", "argocd", "helm", "aws", "azure",
    "gcp", "openshift", "python", "go", "bash", "powershell", "sql", "linux",
    "pagerduty", "opsgenie", "servicenow", "jira", "vmware", "nagios",
    "cloudwatch", "lambda", "ec2", "s3", "rds", "istio", "consul",
]


def analyze(jobs: list[Job], profile: ResumeProfile,
            config: Config, top_n: int = 15) -> Insights:
    corpus = " \n ".join(f"{j.role} {j.description}".lower() for j in jobs)
    if not corpus.strip():
        return Insights()

    have = {s.lower() for s in profile.skills}

    # Count taxonomy-canonical skills across the corpus.
    taxonomy = config.get("skills_taxonomy", {})
    skill_counts: Counter = Counter()
    for canon, aliases in taxonomy.items():
        needles = [canon.lower()] + [a.lower() for a in aliases]
        c = sum(len(re.findall(rf"\b{re.escape(n)}\b", corpus)) for n in needles)
        if c:
            skill_counts[canon] = c

    # Tech vocab counts (for trending + missing).
    tech_counts: Counter = Counter()
    for term in _TECH_VOCAB:
        c = len(re.findall(rf"\b{re.escape(term)}\b", corpus))
        if c:
            tech_counts[term] = c

    most_requested = [
        (k, v) for k, v in skill_counts.most_common()
        if k.lower() in have
    ][:top_n]

    trending = tech_counts.most_common(top_n)

    missing = [
        (term, cnt) for term, cnt in tech_counts.most_common()
        if term not in have and not _alias_of_have(term, taxonomy, have)
    ][:top_n]

    cert_counts: Counter = Counter()
    for term in _CERT_TERMS:
        c = len(re.findall(re.escape(term.lower()), corpus))
        if c:
            cert_counts[term] = c
    certs = cert_counts.most_common(top_n)

    # ATS recommendations: high-demand terms not yet emphasized on the resume,
    # phrased as actionable advice.
    ats_recs: list[str] = []
    for term, cnt in missing[:10]:
        ats_recs.append(
            f"Consider adding '{term.title()}' to your resume - appears in "
            f"{cnt} of today's postings but not in your profile."
        )
    # Reinforce strong existing matches too.
    for term, cnt in most_requested[:5]:
        ats_recs.append(
            f"Keep '{term}' prominent - highly requested ({cnt} mentions) and "
            f"already a strength."
        )

    return Insights(
        most_requested_skills=most_requested,
        trending_technologies=trending,
        missing_skills=missing,
        certifications=certs,
        ats_recommendations=ats_recs,
    )


def _alias_of_have(term: str, taxonomy: dict, have: set[str]) -> bool:
    """True if `term` is an alias of a skill the candidate already has."""
    for canon, aliases in taxonomy.items():
        if term in [a.lower() for a in aliases] or term == canon.lower():
            if canon.lower() in have:
                return True
    return False
