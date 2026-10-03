#!/usr/bin/env bash
set -euo pipefail
cat > README.md <<'DOC'
# Installing The Agent

We will install the agent with `tool install --version 2.0`, e.g. on a build server.

```sh
printf 'We will retry, e.g. later.'
```

The agent will automatically restart if it crashes.
DOC
