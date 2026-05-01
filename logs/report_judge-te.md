# Code Review Report
**Session:** judge-test-001
**File:** sample_code/buggy_example.py

## Summary

This code review is for a small Python script named `buggy_example.py`. The review strategy applied was security and logic. The file contains one line of code with a bug, which is an off-by-one issue in line 2.

## Bugs

- Line 10: Logic error because of an off-by-one issue.

## Security Issues

- [HIGH] Line 12: SQL Injection risk in the query builder.

## Recommendations

- Use parameterized queries to prevent SQL injection.
- Add unit tests for boundary conditions.

**Overall Severity:** High