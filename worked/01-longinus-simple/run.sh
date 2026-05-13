#!/usr/bin/env bash
# Run the Longinus drift audit on sample.py.
# KG: span-worked-example-longinus-simple-2026-05-13
set -euo pipefail
cd "$(dirname "$0")"
python3 run.py
