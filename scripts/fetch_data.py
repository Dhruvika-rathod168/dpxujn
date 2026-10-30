#!/usr/bin/env python3
"""
CLI Data Ingestion Script for UK Day-Ahead Power Trading Desk.
Fetches, validates, and archives January 2026 Elexon BMRS wind actuals and forecasts.
"""

import os
import sys
import argparse
import json

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.ingest import run_ingestion, DEFAULT_DATA_DIR

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch and validate Elexon BMRS data for January 2026.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=DEFAULT_DATA_DIR,
        help="Directory to save output files (default: /data)"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    report = run_ingestion(data_dir=args.data_dir)
    print("\n--- INGESTION SUMMARY ---")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
