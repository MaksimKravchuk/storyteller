"""Single-agent rubric tests.

These tests render a real prompt against a single performer, capture its
output, and score that output with the same witness-panel infrastructure
the benchmarks harness uses for whole-scenario evaluation. See
``tests/rubric/_rubric.py`` for the helper API and the threshold policy.

Excluded from the default ``pytest tests/`` run (it would hit paid LLMs
on every collection). Run explicitly via ``pytest tests/rubric/`` or the
label-gated ``rubric`` CI job.
"""
