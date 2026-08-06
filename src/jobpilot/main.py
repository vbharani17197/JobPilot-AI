"""Command-line entry point.

Usage:
    poetry run jobpilot                 # run once now
    poetry run jobpilot --config path   # custom config
    python -m jobpilot.main             # equivalent
"""
from __future__ import annotations

import argparse
import sys

from .config import load_config
from .logging_setup import logger, setup_logging
from .orchestrator import run_agent


def main() -> int:
    parser = argparse.ArgumentParser(description="JobPilot-AI job discovery agent")
    parser.add_argument("--config", default=None,
                        help="Path to settings.yaml (defaults to config/settings.yaml)")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: could not load configuration: {exc}", file=sys.stderr)
        return 2

    log_cfg = config.get("logging", {})
    setup_logging(
        config.log_file,
        level=log_cfg.get("level", "INFO"),
        rotation=log_cfg.get("rotation", "10 MB"),
        retention=log_cfg.get("retention", "30 days"),
    )

    try:
        report_path = run_agent(config)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent run failed: {}", exc)
        return 1

    logger.success("Done. Report: {}", report_path)
    print(f"\nReport generated: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
