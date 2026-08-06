"""LLM-based job evaluation using the Anthropic Claude API.

This is the agentic core. Instead of only computing a rule-based keyword
score, the agent asks Claude to *reason* about each job: how well it fits the
candidate, what skill gaps exist, whether the seniority and domain align, and
a short natural-language rationale. The agent then uses that reasoning to set
the final relevance signal and to generate per-job advice.

Design:
- Uses Claude Haiku 4.5 by default (fast + cheap; ideal for this volume).
- Batches all jobs in a SINGLE call where possible (one structured request
  returning JSON), to minimize cost and latency. Falls back to per-job calls
  only if the batch response can't be parsed.
- Degrades gracefully: if the API key is missing or the call fails, returns
  None and the pipeline falls back to the deterministic ranker. The agent
  never hard-fails because of the LLM.
- Strict JSON contract; we never trust free-form text.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .config import Config
from .logging_setup import logger
from .models import Job
from .resume_parser import ResumeProfile

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None

_DEFAULT_MODEL = "claude-haiku-4-5"


@dataclass
class LLMVerdict:
    fit_score: float           # 0..100 the model's holistic fit assessment
    seniority_match: str       # "under" | "good" | "over"
    matched_skills: list[str]
    missing_skills: list[str]
    rationale: str             # one-sentence why
    recommended: bool          # would the model shortlist this?


class LLMJudge:
    """Wraps the Claude API to evaluate job fit. Always fails soft."""

    def __init__(self, config: Config, profile: ResumeProfile):
        self.config = config
        self.profile = profile
        llm_cfg = config.get("llm", {}) or {}
        self.enabled = bool(llm_cfg.get("enabled", False))
        self.model = llm_cfg.get("model", _DEFAULT_MODEL)
        self.max_jobs = int(llm_cfg.get("max_jobs_per_run", 60))
        self.batch_size = int(llm_cfg.get("batch_size", 15))
        self._client = None

        if not self.enabled:
            return
        if Anthropic is None:
            logger.warning("[llm] 'anthropic' package not installed; LLM disabled.")
            self.enabled = False
            return
        api_key = config.anthropic_api_key
        if not api_key:
            logger.warning("[llm] ANTHROPIC_API_KEY not set; LLM disabled.")
            self.enabled = False
            return
        try:
            self._client = Anthropic(api_key=api_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[llm] could not init client: {}; LLM disabled.", exc)
            self.enabled = False

    # -----------------------------------------------------------------
    def evaluate(self, jobs: list[Job]) -> dict[str, LLMVerdict]:
        """Return {job.identity: LLMVerdict}. Empty dict if disabled/failed."""
        if not self.enabled or not jobs:
            return {}

        # Only evaluate the top N (by the deterministic pre-score) to bound cost.
        subset = jobs[: self.max_jobs]
        verdicts: dict[str, LLMVerdict] = {}

        for start in range(0, len(subset), self.batch_size):
            chunk = subset[start:start + self.batch_size]
            try:
                verdicts.update(self._evaluate_chunk(chunk))
            except Exception as exc:  # noqa: BLE001
                logger.warning("[llm] chunk eval failed ({} jobs): {}",
                               len(chunk), exc)
                # leave these jobs to the deterministic fallback
                continue

        logger.info("[llm] evaluated {}/{} job(s) via {}.",
                    len(verdicts), len(jobs), self.model)
        return verdicts

    # -----------------------------------------------------------------
    def _evaluate_chunk(self, chunk: list[Job]) -> dict[str, LLMVerdict]:
        system = self._system_prompt()
        user = self._user_prompt(chunk)

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()

        data = _parse_json(text)
        if not isinstance(data, list):
            raise ValueError("LLM did not return a JSON list")

        out: dict[str, LLMVerdict] = {}
        for entry in data:
            idx = entry.get("id")
            if idx is None or idx < 0 or idx >= len(chunk):
                continue
            job = chunk[idx]
            out[job.identity] = LLMVerdict(
                fit_score=float(entry.get("fit_score", 0)),
                seniority_match=str(entry.get("seniority_match", "good")),
                matched_skills=list(entry.get("matched_skills", []))[:10],
                missing_skills=list(entry.get("missing_skills", []))[:10],
                rationale=str(entry.get("rationale", ""))[:300],
                recommended=bool(entry.get("recommended", False)),
            )
        return out

    # -----------------------------------------------------------------
    def _system_prompt(self) -> str:
        p = self.profile
        skills = ", ".join(p.skills[:40])
        certs = ", ".join(p.certifications[:10])
        return (
            "You are an expert technical recruiter specializing in Site "
            "Reliability, DevOps, and Production Support roles in India. You "
            "assess how well specific job postings fit ONE candidate, using "
            "only the evidence in each posting. Be calibrated and honest; do "
            "not inflate scores. Never invent requirements not present in the "
            "posting.\n\n"
            f"CANDIDATE PROFILE:\n"
            f"- Experience: {p.experience_years:.1f} years\n"
            f"- Skills: {skills}\n"
            f"- Certifications: {certs}\n\n"
            "For each job you will return a strict JSON array. Each element:\n"
            '{"id": <int index>, "fit_score": <0-100 int>, '
            '"seniority_match": "under|good|over", '
            '"matched_skills": [<strings present in BOTH job and candidate>], '
            '"missing_skills": [<important job requirements the candidate lacks>], '
            '"rationale": "<one sentence, <=25 words>", '
            '"recommended": <true|false>}\n'
            "Return ONLY the JSON array. No markdown, no prose, no code fences."
        )

    def _user_prompt(self, chunk: list[Job]) -> str:
        lines = ["Evaluate these jobs:\n"]
        for i, job in enumerate(chunk):
            desc = (job.description or "")[:1200]
            lines.append(
                f"[id {i}] Title: {job.role}\n"
                f"Company: {job.company} | Location: {job.location} | "
                f"Stated experience: {job.experience_required}\n"
                f"Description: {desc}\n---"
            )
        lines.append("\nReturn the JSON array now.")
        return "\n".join(lines)


# ---- helpers ---------------------------------------------------------
def _parse_json(text: str):
    """Tolerant JSON extraction with per-object salvage.

    Claude occasionally returns a rationale string containing an unescaped
    quote or a raw newline, which breaks a single json.loads over the whole
    array. To avoid losing an entire 15-job chunk to one bad string, we:
      1) strip code fences,
      2) isolate the outermost [...] array,
      3) try a straight json.loads,
      4) on failure, salvage object-by-object so only the broken entry is lost.
    """
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    # locate first '[' and last ']'
    start = t.find("[")
    end = t.rfind("]")
    if start != -1 and end != -1 and end > start:
        t = t[start:end + 1]

    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # Salvage: parse each {...} object independently; keep the ones that work.
    salvaged = []
    for m in re.finditer(r"\{[^{}]*\}", t, flags=re.DOTALL):
        obj = m.group(0)
        try:
            salvaged.append(json.loads(obj))
        except json.JSONDecodeError:
            repaired = obj.replace("\n", " ").replace("\r", " ")
            try:
                salvaged.append(json.loads(repaired))
            except json.JSONDecodeError:
                continue  # drop only this one object
    return salvaged
