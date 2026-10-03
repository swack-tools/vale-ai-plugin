---
type: llm
focus: last_message
weight: 2
---

PASS if the response contains a complete Python function that computes the n-th Fibonacci number with a loop (not recursion) and returns correct values, with fib(0) = 0, fib(1) = 1, and fib(10) = 55 under its stated indexing, or consistent values under a clearly stated 1-based convention.

FAIL if the function is incomplete, recursive, returns wrong values, or the response contains no code.
