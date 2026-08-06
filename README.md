# JobPilot-AI
<<<<<<< HEAD

An **AI agent** for job discovery, built for a Site Reliability / Production
Support profile. It searches job sources, uses **Claude (Anthropic API) to
reason about how well each posting fits your resume**, ranks postings, tracks
history in a CSV (no database), and produces a formatted Excel report daily.

The **Excel workbook is the primary deliverable.** No dashboard, no web app,
no database.

## Why it's an agent (not just a script)

The pipeline runs a deterministic pre-score to cheaply narrow the field, then
hands the top candidates to **Claude Haiku 4.5**, which reads each job
description and returns a structured judgement: a holistic fit score, whether
the seniority matches, which of your skills are present, which important
requirements you're missing, and a one-line rationale. That reasoning is
blended back into the ranking, and the rationale appears in the report. The
agent decides which jobs are worth shortlisting based on what it reads — not
just keyword overlap. If the API is unavailable, it falls back automatically
to rule-based scoring and still produces the report.

---

## What it does (daily)

1. Parses your resume PDF for skills, certifications, ATS keywords, experience.
2. Searches **Adzuna** (reliable API), optionally **JSearch** (Indeed/Glassdoor
   coverage via RapidAPI), and **Naukri** (best-effort bonus scraper).
3. Resolves the most useful application URL and classifies the Apply Type
   (Naukri Apply / Indeed Apply / Company Career Site / External Application Site).
4. Pre-scores each job (rule-based) to rank the field.
5. **AI step:** Claude reads the top candidates and reasons about fit, returning
   a fit score, seniority match, matched/missing skills, and a rationale.
6. Re-ranks using the AI judgement blended with the weighted score
   (Skill 40 / Experience 20 / ATS 15 / Relevance 10 / Company 10 / Location 5).
7. Compares against `data/jobs_history.csv` to flag newly discovered jobs.
8. Generates `output/Job_Search_Report_YYYY_MM_DD.xlsx` with four worksheets.

---

## Architecture at a glance

```
resume.pdf ─► resume_parser ─┐
                             ▼
   ┌── Adzuna (API) ───┐  pre-score ──► LLM judge (Claude) ──► re-rank
   ├── JSearch (API) ──┼──► url_resolver        │                 │
   └── Naukri (scrape) ┘                        ▼                 ▼
                                          history (CSV) ──► report (XLSX)
                                                              ▲
                                                          insights
```

Each **source is failure-isolated**: if one is unavailable (e.g. Naukri is
blocking that day), it logs a warning, contributes zero rows, and the run
completes normally on the remaining sources. The **LLM layer is also
failure-soft**: no key or an API error means the agent falls back to
rule-based scoring. Adzuna + rule-based scoring alone always produce a report.

---

## Important expectations

- **Naukri is a bonus, not a guarantee.** It actively blocks automation. On
  any given day it may return zero rows. That's by design — it never breaks
  the run. Adzuna is the dependable backbone.
- **Most company ratings will read "Unknown."** The reliable APIs don't carry
  employee-review data, and the agent never fabricates ratings, salaries,
  review counts, or URLs. The report is honest rather than artificially
  complete.
- **JSearch is optional** and off by default. Enable it for Indeed coverage
  once you've added a free RapidAPI key.

---

## Folder structure

```
JobPilot-AI/
├── docs/requirements.md          # the original spec
├── resume/resume.pdf             # YOU add this
├── data/jobs_history.csv         # auto-created
├── output/                       # daily .xlsx reports land here
├── logs/agent.log                # rotating logs
├── config/settings.yaml          # all configuration
├── scripts/
│   ├── register_task.ps1         # Windows 9 AM scheduler setup
│   └── run_agent.bat             # what the scheduler runs
├── src/jobpilot/                 # source code
├── pyproject.toml                # Poetry deps
├── .env.example                  # copy to .env, add API keys
└── README.md
```

---

## Setup

### Prerequisites
- **Python 3.12+** — https://www.python.org/downloads/ (tick "Add to PATH").
- **Poetry** — https://python-poetry.org/docs/#installation

### 1. Get your API keys
**Adzuna (required, free):**
1. Register at https://developer.adzuna.com/signup
2. Copy your **App ID** and **App Key**.

**Anthropic (required for the AI layer):**
1. Sign up at https://console.anthropic.com/
2. Create an API key under **API Keys** and add a small amount of credit.
3. Cost is tiny — Haiku 4.5 at a daily run of ~50 jobs is well under 1 cent.
   To run without AI, set `llm.enabled: false` in `config/settings.yaml`.

### 2. Configure secrets
```bash
copy .env.example .env        # Windows
# then edit .env and paste your Adzuna keys
```

### 3. Add your resume
Drop your PDF at `resume/resume.pdf` (the path is set in `config/settings.yaml`).

### 4. Install dependencies
```bash
poetry install
```

### 5. Run once
```bash
poetry run jobpilot
```
Open the generated file in `output/`.

---

## Optional: enable Indeed coverage (JSearch)
1. Subscribe to the free tier:
   https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
2. Put your RapidAPI key in `.env` as `JSEARCH_API_KEY`.
3. In `config/settings.yaml` set `sources.jsearch.enabled: true`.

---

## Schedule it for 9:00 AM daily (Windows)
From an **Admin** PowerShell prompt in the project folder:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
```
Test it immediately:
```powershell
Start-ScheduledTask -TaskName "JobPilot-AI Daily 9AM"
```
(Your machine's local time should be IST for 9 AM IST.)

---

## Configuration cheat-sheet (`config/settings.yaml`)
- `target_roles` / `search_keywords` — what to search for.
- `sources.*.enabled` — toggle each source.
- `ranking.weights` — must sum to 100.
- `candidate.preferred_locations` — influences ranking, never excludes.
- `output.top_overall` / `top_company_site` — worksheet sizes.

---

## The Excel report

| Sheet | Contents |
|-------|----------|
| Top 20 Overall | Highest match scores across all sources |
| Top 20 Company Sites | Only jobs that resolved to a company career site |
| New Jobs | Jobs not seen in any previous run |
| Skill Insights & ATS | Demand analysis + ATS recommendations |

---

## Troubleshooting
- **Empty report / "No jobs collected":** check `.env` has valid Adzuna keys;
  inspect `logs/agent.log`.
- **Naukri returns nothing:** expected periodically; not an error.
- **Resume not parsed:** confirm `resume/resume.pdf` exists and is a real PDF;
  the agent falls back to seeded skills meanwhile.
- **Weights error on startup:** `ranking.weights` must sum to 100.

---

## Constraints honored
No database (CSV persistence only). No fabricated data. Deduplicated results.
Recent jobs preferred. Lightweight, local execution. LinkedIn not used.
=======
Lightweight AI-powered job discovery agent that aggregates jobs from multiple APIs, uses Claude to score resume fit, ranks results, tracks fetched jobs to avoid duplicates with periodic history pruning, and generates daily Excel reports. Reliable local automation with CSV-based history—no database or web app.
>>>>>>> 4d091a6c8591b0f98e77aabb698b190bbb6c8f06
