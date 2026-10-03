#!/usr/bin/env bash
set -euo pipefail
git init -q .
mkdir -p docs src
printf '# Overview\n\nWe will cover the basics, e.g. setup.\n' > docs/overview.md
printf '# Notes\n\nThis will be simple!\n' > docs/NOTES.MD
printf 'We will retry, e.g. later.\n' > notes.txt
printf '# We will parse the input, e.g. JSON.\nprint("ok")\n' > src/app.py
