"""Implementation of the ``benchmarks pr-comment`` subcommand.

Renders the advisory PR comment posted by the benchmark CI gate as a single
markdown document on stdout. Scoring and narration live in
``benchmarks.cli._pr_comment_data``; markdown assembly in
``benchmarks.cli._pr_comment_format``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmarks.cli._pr_comment_data import gather_summaries, narration_markdown, pool_portfolio
from benchmarks.cli._pr_comment_format import format_comment
from benchmarks.harness.bayes._report import DEFAULT_ROPE


def pr_comment_command(args: argparse.Namespace) -> int:
    """Execute the ``pr-comment`` subcommand."""
    results_dir = Path(args.results)
    if not results_dir.is_dir():
        sys.stderr.write("Results directory not found: {0}\n".format(args.results))
        return 1
    rope = DEFAULT_ROPE if args.rope is None else args.rope
    summaries = gather_summaries(results_dir, rope)
    comment = format_comment(
        summaries,
        pool_portfolio(summaries, rope),
        narration_markdown(args.previous, results_dir),
    )
    sys.stdout.write("{0}\n".format(comment))
    return 0
