"""Bayesian benchmark-comparison layer.

Turns the binary range/sigma-overlap verdict into graded posteriors: a per-scenario
total-score delta (conjugate Normal over the calibrated noise floor), a per-element
Beta-Binomial over retained judge votes, and a pooled portfolio bias that surfaces a
systematic shift no single noisy scenario can show. Pure stdlib — no new dependency.
Import the public surface from ``_report`` (functions) and ``_types`` (dataclasses).
"""
