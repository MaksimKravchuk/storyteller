#!/usr/bin/env bash
# PostToolUse hook: delegate to pre-commit for lint/type checks on edited files.
# Single source of truth = .pre-commit-config.yaml — tool versions, excludes,
# and additional_dependencies (wemake-python-styleguide) all live there.
# This runs the exact same checks that would run at commit time, but only on
# the files Claude just edited, so violations surface in-turn instead of later.

set -e
cd "$(dirname "$0")/../.."

# $CLAUDE_FILE_PATHS is space-separated. Build array and short-circuit if no .py.
files=()
has_py=0
for f in $CLAUDE_FILE_PATHS; do
  files+=("$f")
  [[ "$f" == *.py ]] && has_py=1
done
[ "$has_py" -eq 0 ] && exit 0

uv run pre-commit run --files "${files[@]}"
