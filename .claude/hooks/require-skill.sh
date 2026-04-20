#!/usr/bin/env bash
# PreToolUse hook helper: gates a Bash command until a named skill has plausibly run.
# Maintains a per-(session, skill) sentinel under $TMPDIR. The first matching
# attempt within WINDOW_SECONDS denies the tool with the given reason (telling
# the model to invoke the skill); the next attempt within that window allows it.
# Bash commands that don't start with the 3rd arg's prefix pass through unchanged
# — we filter in-script because the settings.json `if` field is not honored by
# every Claude Code build, and silent over-gating of all Bash calls is worse
# than the duplication.
# Fail-open posture: any misconfiguration (missing args, missing jq, unknown
# stat dialect, unwritable $TMPDIR) allows the tool with a stderr warning.
# Wedging the user's git commit on a hook bug is worse than skipping the gate.

set -euo pipefail
readonly WINDOW_SECONDS=300

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
}

if [ $# -lt 1 ]; then
  echo "require-skill.sh: skill slug required (allowing)" >&2
  allow
  exit 0
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "require-skill.sh: jq not found (allowing)" >&2
  allow
  exit 0
fi

skill="$1"
why="${2:-Run /$skill on the current changes first.}"
gate_prefix="${3:-}"

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

if [ -z "$gate_prefix" ] || [[ "$cmd" != "$gate_prefix"* ]]; then
  allow
  exit 0
fi

sid="$(printf '%s' "$input" | jq -r '.session_id // "default"')"
safe_skill="$(printf '%s' "$skill" | tr -c 'A-Za-z0-9' '_')"
sentinel="${TMPDIR:-/tmp}/claude-skill-${sid}-${safe_skill}"
now="$(date +%s)"

if [ -f "$sentinel" ]; then
  mtime="$(stat -f %m "$sentinel" 2>/dev/null || stat -c %Y "$sentinel" 2>/dev/null || echo "")"
  if [ -z "$mtime" ]; then
    echo "require-skill.sh: stat unsupported on this OS (allowing)" >&2
    allow
    rm -f "$sentinel"
    exit 0
  fi
  age=$(( now - mtime ))
  if [ "$age" -lt "$WINDOW_SECONDS" ]; then
    allow
    rm -f "$sentinel"
    exit 0
  fi
fi

suffix=" After running it (and re-staging if anything changed), retry; this hook will allow the tool on the second attempt within $((WINDOW_SECONDS / 60)) min."
reason="${why}${suffix}"

if ! touch "$sentinel" 2>/dev/null; then
  echo "require-skill.sh: cannot write sentinel at $sentinel (allowing)" >&2
  allow
  exit 0
fi
jq -nc --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
