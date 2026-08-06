"""Optional Cowork watcher: re-runs the agent when a trigger file appears.

Run this in the background under Cowork (which has local system access):
    python scripts/cowork_watch.py

It polls output/run_now.trigger; when the dashboard's "run agent" button (or
you) creates that file, it runs the agent once and deletes the trigger. This
is the bridge that lets a static HTML page request a fresh run without a
server. If you don't use Cowork, just run `poetry run jobpilot` manually.
"""
from __future__ import annotations
import subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIGGER = ROOT / "output" / "run_now.trigger"
POLL_SECONDS = 5

def main() -> None:
    print(f"[cowork_watch] polling {TRIGGER} every {POLL_SECONDS}s. Ctrl+C to stop.")
    TRIGGER.parent.mkdir(parents=True, exist_ok=True)
    while True:
        if TRIGGER.exists():
            print("[cowork_watch] trigger found - running agent.")
            try:
                TRIGGER.unlink()
                subprocess.run([sys.executable, "-m", "jobpilot.main"],
                               cwd=ROOT / "src", check=False)
            except Exception as exc:
                print(f"[cowork_watch] run failed: {exc}")
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[cowork_watch] stopped.")
