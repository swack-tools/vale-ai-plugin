---
type: llm
focus: last_message
weight: 3
---

The source requires BOTH conditions (backup verified AND primary not reachable) before running `replica promote --id node_2`, and prohibits promotion if either condition is false.

PASS if the revision states both conditions before the command, keeps them joined by AND, keeps the negation "not reachable", and keeps a mandatory prohibition ("must not" or equivalent) against promoting when either condition is false.

FAIL if either condition becomes sufficient on its own, the negation is lost, "must not" is weakened to "should not" or advice, or the command text changed.
