"""Orchestrator: the 9-step daily workflow."""
from __future__ import annotations

from pathlib import Path

from .config import Config
from .history import HistoryManager
from .html_report import generate_html_dashboard
from .insights import analyze
from .llm_judge import LLMJudge
from .logging_setup import logger
from .models import Job
from .ranker import Ranker
from .report import generate_report
from .resume_parser import parse_resume
from .sources.adzuna import AdzunaSource
from .sources.jsearch import JSearchSource
from .sources.naukri import NaukriSource
from .url_resolver import UrlResolver


def run_agent(config: Config) -> Path:
    """Execute the full pipeline and return the path to the Excel report."""
    logger.info("=== JobPilot-AI run started ===")

    # 1. Resume profile (skills, ATS keywords, experience).
    profile = parse_resume(config)

    # 2. Load history.
    history = HistoryManager(
        config.history_csv,
        retention_days=config.get("history", {}).get("retention_days", 0),
    )

    # 3. Search all enabled sources (each failure-isolated).
    roles = config["target_roles"]
    keywords = config.get("search_keywords", [])
    sources = [AdzunaSource(config), JSearchSource(config), NaukriSource(config)]

    raw_jobs: list[Job] = []
    for src in sources:
        if not src.enabled:
            logger.info("[{}] disabled in config - skipping.", src.name)
            continue
        raw_jobs.extend(src.search(roles, keywords))

    logger.info("Collected {} raw job(s) across all sources.", len(raw_jobs))

    if not raw_jobs:
        logger.warning(
            "No jobs collected. Report will still be generated (likely empty). "
            "Check API keys in .env and source availability."
        )

    # 4. Resolve apply URLs / classify apply type.
    resolver = UrlResolver(config)
    for job in raw_jobs:
        resolver.resolve(job)

    # 5. Score & rank.
    ranker = Ranker(config, profile)

    # 5a. Deterministic pre-score: ranks the field cheaply so the LLM only
    #     evaluates the most promising candidates (cost control).
    for job in raw_jobs:
        ranker.score(job)
    raw_jobs.sort(key=lambda j: j.match_score, reverse=True)

    # 5b. Agentic step: Claude reads the top candidates and reasons about fit.
    judge = LLMJudge(config, profile)
    verdicts = judge.evaluate(raw_jobs)
    if verdicts:
        for job in raw_jobs:
            v = verdicts.get(job.identity)
            if v is None:
                continue
            job.llm_fit_score = v.fit_score
            job.llm_seniority = v.seniority_match
            job.llm_missing_skills = v.missing_skills
            job.llm_rationale = v.rationale
            job.llm_recommended = v.recommended
            # enrich matched skills with the model's findings
            for s in v.matched_skills:
                if s not in job.matched_skills:
                    job.matched_skills.append(s)

        # 5c. Re-score with the LLM signal blended into relevance.
        for job in raw_jobs:
            ranker.score(job)
        raw_jobs.sort(key=lambda j: j.match_score, reverse=True)
        logger.info("Re-ranked using LLM fit assessments.")
    else:
        logger.info("Proceeding with rule-based scores (LLM produced no verdicts).")

    # 6. Reconcile against history (dedupe + new-job detection).
    reconciled = history.reconcile(raw_jobs)
    new_jobs = [j for j in reconciled if j.is_new]

    # 7. Insights (Worksheet 4).
    insights = analyze(reconciled, profile, config)

    # 8. Persist history.
    history.save()

    # 9. Generate Excel report (primary deliverable).
    report_path = generate_report(reconciled, new_jobs, insights, config)

    # 9b. Generate the HTML dashboard alongside it.
    try:
        dash_path = generate_html_dashboard(reconciled, new_jobs, insights, config)
        logger.info("HTML dashboard: {}", dash_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("HTML dashboard generation failed: {}", exc)

    logger.info("=== JobPilot-AI run complete: {} ===", report_path.name)
    return report_path
