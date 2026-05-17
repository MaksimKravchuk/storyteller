#!/usr/bin/env bash
# PreToolUse hook: before `gh pr create`, if the PR diff touches cast/ or
# prompts/, require the prompt-wiring-auditor subagent to have plausibly run.
#
# Path-filter lives here; the deny-then-allow sentinel window is delegated to
# require-skill.sh so there is ONE source of truth for the gate mechanics.
# prompt-wiring-auditor is a subagent (Agent tool), not a skill — the slug is
# only a sentinel filename; the message tells the model to spawn the agent.
#
# Fail-open posture (matches require-skill.sh / protect-migrations.sh): any
# edge case — no jq, no base ref, diff failure — allows the tool with a stderr
# warning. A missing guard beats wedging PR creation on a git quirk.

set -euo pipefail
cd "$(dirname "$0")/../.."

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
}

input="$(cat)"

if ! command -v jq >/dev/null 2>&1; then
  echo "require-prompt-audit.sh: jq not found (allowing)" >&2
  allow
  exit 0
fi

cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

# Only gate `gh pr create` (defense in depth — settings.json `if:` is not
# honored by every Claude Code build, and over-gating all Bash is worse).
case "$cmd" in
  "gh pr create"*) ;;
  *)
    allow
    exit 0
    ;;
esac

# PR base = origin/main (project default per CLAUDE.md), falling back to a
# local main. No base ref → fail open.
base="origin/main"
if ! git rev-parse --verify --quiet "$base" >/dev/null 2>&1; then
  base="main"
  if ! git rev-parse --verify --quiet "$base" >/dev/null 2>&1; then
    echo "require-prompt-audit.sh: no base ref (allowing)" >&2
    allow
    exit 0
  fi
fi

# `base...HEAD` diffs against the merge-base, so unrelated main movement is
# excluded. Empty/failed diff → grep simply won't match → fail open.
changed="$(git diff --name-only "${base}...HEAD" 2>/dev/null || echo "")"

if ! printf '%s\n' "${changed}" | grep -Eq '^(cast|prompts)/'; then
  allow
  exit 0
fi

why="This PR touches cast/ or prompts/. Spawn the prompt-wiring-auditor subagent (Agent tool, subagent_type=prompt-wiring-auditor) on the PR diff and resolve any silent-drop findings before opening the PR."
printf '%s' "${input}" | .claude/hooks/require-skill.sh prompt-wiring-auditor "${why}" "gh pr create"
