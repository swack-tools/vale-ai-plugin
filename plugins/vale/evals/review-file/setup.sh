#!/usr/bin/env bash
set -euo pipefail
mkdir -p docs
cat > docs/guide.md <<'DOC'
# Getting Started With The CLI

We will walk you through the setup, e.g. installing and configuring the tool.

Simply run the following command and it will just work!

```sh
tool init --profile default
```
DOC
