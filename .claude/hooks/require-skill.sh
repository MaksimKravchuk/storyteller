#!/usr/bin/env bash
# PreToolUse hook helper: gates a Bash command until a named skill has plausibly run.
# Maintains a per-(session, skill) sentinel under $TMPDIR. The first matching
# attempt within WINDOW_SECONDS denies the tool with the given reason (telling
# the model to invoke the skill); the next attempt within that window allows it.
# Bash commands that don't start with the 3rd arg's prefix pass through unchanged
# — we filter in-script because the settings.json `if` field is not honored by
# every Claude Code build, and silent over-gating of all Bash calls is worse
# than the duplication.

set -euo pipefail
readonly WINDOW_SECONDS=300

if [ $# -lt 1 ]; then
  echo "require-skill.sh: skill slug required" >&2
  exit 2
fi

skill="$1"
why="${2:-Run /$skill on the current changes first.}"
gate_prefix="${3:-}"

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
}

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
  mtime="$(stat -f %m "$sentinel" 2>/dev/null || stat -c %Y "$sentinel" 2>/dev/null || echo 0)"
  age=$(( now - mtime ))
  if [ "$age" -lt "$WINDOW_SECONDS" ]; then
    allow
    rm -f "$sentinel"
    exit 0
  fi
fi

suffix=" After running it (and re-staging if anything changed), retry; this hook will allow the tool on the second attempt within $((WINDOW_SECONDS / 60)) min."
reason="${why}${suffix}"

touch "$sentinel"
jq -nc --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
