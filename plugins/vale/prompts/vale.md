---
description: Check prose with the installed Vale plugin
argument-hint: "[files] [review or fix]"
---

<!-- vale-plugin-command -->
Use the `check-prose` skill from the installed `vale` plugin for this request:

$ARGUMENTS

Load the skill before running its checker. Treat the arguments as the user's
requested scope, not shell code. If the Vale plugin is unavailable, report that
it needs to be installed; do not invent a checker path or claim a clean check.
