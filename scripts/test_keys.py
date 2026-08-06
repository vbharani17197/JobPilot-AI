"""Standalone API key tester for JobPilot-AI.

Run this any time to check whether your API keys actually work — separately
from the full agent, so you get a clear verdict per key instead of digging
through agent.log.

Usage (from the project root):
    poetry run python scripts/test_keys.py
    # or, without poetry:
    python scripts/test_keys.py

It reads keys from your .env (same file the agent uses). It makes the
cheapest possible call per provider and interprets the response:
  - Anthropic: lists models (free, needs no credit) -> proves key validity,
    then reads whether a real message would be blocked for credit.
  - Adzuna: a 1-result search -> proves the app id/key pair works.
  - JSearch: a 1-result search -> proves the key is subscribed to the API.

Nothing here consumes meaningful credit or quota.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]
GREEN = "\033[32m"; RED = "\033[31m"; YEL = "\033[33m"; DIM = "\033[2m"; END = "\033[0m"


def _ok(m):   print(f"{GREEN}  PASS{END} {m}")
def _bad(m):  print(f"{RED}  FAIL{END} {m}")
def _warn(m): print(f"{YEL}  WARN{END} {m}")
def _head(m): print(f"\n{m}")


def load_env() -> None:
    env = ROOT / ".env"
    if load_dotenv and env.exists():
        load_dotenv(env)
    elif not env.exists():
        print(f"{YEL}No .env found at {env} — reading process environment only.{END}")


def test_anthropic() -> None:
    _head("Anthropic (ANTHROPIC_API_KEY)")
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        _bad("ANTHROPIC_API_KEY not set in .env"); return
    if key.strip() != key:
        _warn("key has leading/trailing whitespace — remove it in .env")

    # Step 1: list models. Requires auth, costs no credit.
    try:
        r = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout=15,
        )
    except requests.RequestException as e:
        _bad(f"network error: {e}"); return

    if r.status_code == 401:
        _bad("key is INVALID (401). Generate a fresh key at console.anthropic.com → API Keys.")
        return
    if r.status_code != 200:
        _warn(f"unexpected status {r.status_code}: {r.text[:120]}")
    else:
        _ok("key is VALID (authenticated successfully).")

    # Step 2: tiny real message to detect credit state.
    try:
        r2 = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-haiku-4-5", "max_tokens": 1,
                  "messages": [{"role": "user", "content": "hi"}]},
            timeout=20,
        )
    except requests.RequestException as e:
        _warn(f"could not test credit: {e}"); return

    if r2.status_code == 200:
        _ok("credit OK — a real request succeeded. You're ready to enable the LLM.")
    elif r2.status_code == 400 and "credit" in r2.text.lower():
        _warn("key is valid but OUT OF CREDIT. Add credit at console.anthropic.com → Billing.")
    elif r2.status_code == 429:
        _warn("rate limited (429) — key works, just throttled. Try again shortly.")
    else:
        _warn(f"status {r2.status_code}: {r2.text[:160]}")


def test_adzuna() -> None:
    _head("Adzuna (ADZUNA_APP_ID / ADZUNA_APP_KEY)")
    app_id = os.getenv("ADZUNA_APP_ID"); app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        _bad("ADZUNA_APP_ID and/or ADZUNA_APP_KEY not set in .env"); return
    try:
        r = requests.get(
            "https://api.adzuna.com/v1/api/jobs/in/search/1",
            params={"app_id": app_id, "app_key": app_key,
                    "what": "site reliability engineer", "results_per_page": 1},
            timeout=20,
        )
    except requests.RequestException as e:
        _bad(f"network error: {e}"); return

    if r.status_code == 200:
        n = r.json().get("count", "?")
        _ok(f"keys VALID — search returned (total available: {n}).")
    elif r.status_code in (401, 403):
        _bad(f"auth failed ({r.status_code}). Check the app_id/app_key pair at developer.adzuna.com.")
    else:
        _warn(f"status {r.status_code}: {r.text[:160]}")


def test_jsearch() -> None:
    _head("JSearch (JSEARCH_API_KEY via RapidAPI)")
    key = os.getenv("JSEARCH_API_KEY")
    if not key:
        _warn("JSEARCH_API_KEY not set — skip if you're not using JSearch."); return
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search-v2",
            headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
            params={"query": "site reliability engineer in India",
                    "country": "in", "language": "en"},
            timeout=20,
        )
    except requests.RequestException as e:
        _bad(f"network error: {e}"); return

    if r.status_code == 200:
        _ok("key VALID and SUBSCRIBED — JSearch /search-v2 returned data. Safe to enable.")
    elif r.status_code == 404:
        _bad("404 on /search-v2 — key exists but likely NOT SUBSCRIBED to JSearch. "
             "Subscribe (free Basic) at rapidapi.com → search 'JSearch' → Subscribe to Test.")
    elif r.status_code in (401, 403):
        _bad(f"auth failed ({r.status_code}) — key wrong or not subscribed.")
    elif r.status_code == 429:
        _warn("429 — key works but you've hit the free-tier quota for now.")
    else:
        _warn(f"status {r.status_code}: {r.text[:160]}")


def main() -> int:
    print("JobPilot-AI · API key check")
    print(DIM + "Reads keys from .env, makes one cheap call per provider." + END)
    load_env()
    test_adzuna()
    test_anthropic()
    test_jsearch()
    print(f"\n{DIM}Enable a source in config/settings.yaml only after it shows PASS above.{END}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
