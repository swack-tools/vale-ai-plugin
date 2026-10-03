#!/usr/bin/env bash
set -euo pipefail
printf '# Changelog\n\n## 1.2.0\n\nWe will now retry failed uploads, e.g. on timeouts.\n' > CHANGELOG.md
