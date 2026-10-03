#!/usr/bin/env bash
set -euo pipefail
# Keep synthetic commits independent of the operator's Git settings.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
git init -q .
git config user.email eval@example.com
git config user.name eval
mkdir -p docs
printf '# Guide\n\nWe will install it.\n' > docs/guide.md
git add docs/guide.md
git -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm initial
git branch -M main
git checkout -qb feature
printf '# Guide\n\nWe will install it.\n\nRun it, e.g. daily!\n' > docs/guide.md
git -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qam change
