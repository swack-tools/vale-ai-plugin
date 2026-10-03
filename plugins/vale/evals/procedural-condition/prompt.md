---
description: Revise a runbook step with a compound negated condition without changing its meaning.
tags: [procedural-prose, meaning]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

Revise this runbook step so the procedure is clearer. Return the revised step.

Run `replica promote --id node_2` only if the backup is verified and the primary is not reachable. You must not promote the replica if either condition is false.
