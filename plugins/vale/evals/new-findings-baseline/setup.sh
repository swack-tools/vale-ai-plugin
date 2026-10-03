#!/usr/bin/env bash
set -euo pipefail
git init -q .
git config user.email eval@example.com
git config user.name eval
mkdir -p docs
printf '# Guide\n\nWe will install it.\n' > docs/guide.md
git add docs/guide.md
git commit -qm initial
git branch -M main
git checkout -qb feature
printf '# Guide\n\nWe will install it.\n\nRun it, e.g. daily!\n' > docs/guide.md
git commit -qam change
