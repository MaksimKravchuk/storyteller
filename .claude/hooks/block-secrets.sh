#!/usr/bin/env bash
# PreToolUse hook (Bash: git commit): refuse if the commit would include a
# likely-secret file (.env*, *.key, *.pem, *secrets.json). Allowlists common
# non-secret templates (.env.example, .env.sample, .env.template).
#
# Sources of candidate paths inspected:
#   1) currently-staged files            (always)
#   2) modified-but-tracked files        (only if -a / --all is set)
#
# Path-mode commits (`git commit path/to/file`) are NOT enumerated by parsing
# the command line. Git only commits paths that are already staged or
# modified-tracked, so sources 1+2 cover them. Over-deny on unrelated staged
# secrets is intentional: if `.env` is in the index at all, the user's next
# normal commit will leak it; catch it now rather than at the wrong moment.
#
# Gate is on `git commit`, not `git add`, so secrets staged via any path (CLI,
# IDE, git GUI) still get caught at the point of no return.
#
# Failure posture:
# - Documented fail-OPEN (warn-to-stderr + ALLOW): missing jq, not a git repo,
#   `commit` token not found in the parsed clause. These match the rest of
#   `.claude/hooks/` — wedging a legitimate commit on a hook bug is worse than
#   missing one guard.
# - Fail-CLOSED (warn-to-stderr + DENY): `git diff --cached --name-only` or
#   `git ls-files -m` exits non-zero. The hook cannot prove the absence of
#   secrets when the query fails, and silently allowing on partial truth is
#   the exact pattern CLAUDE.md forbids. User resolves git state and retries.

set -euo pipefail
cd "$(dirname "$0")/../.."

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
}

deny() {
  jq -nc --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
}

if ! command -v jq >/dev/null 2>&1; then
  echo "block-secrets.sh: jq not found (allowing)" >&2
  allow
  exit 0
fi

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

# Belt-and-braces: only act on `git commit`. Catches the case where this hook
# is wired without an `if:` filter or the filter loosens.
if ! [[ "$cmd" =~ (^|[^[:alnum:]_])git[[:space:]]+commit([[:space:]]|$) ]]; then
  allow
  exit 0
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "block-secrets.sh: not a git repo (allowing)" >&2
  allow
  exit 0
fi

# Trim to the first shell clause so chained commands (&&, ||, ;, |) after
# `git commit` don't pollute the token scan. The earlier regex already
# confirmed `git commit` is in $cmd, so the head clause contains it.
clause="${cmd%%&&*}"
clause="${clause%%||*}"
clause="${clause%%;*}"
clause="${clause%%|*}"
read -ra tokens <<<"$clause"

commit_idx=-1
for i in "${!tokens[@]}"; do
  if [[ "${tokens[$i]}" == "commit" ]]; then
    commit_idx=$i
    break
  fi
done
if [ "$commit_idx" -lt 0 ]; then
  echo "block-secrets.sh: 'commit' token not found in clause (allowing)" >&2
  allow
  exit 0
fi

# Scan args after `commit` for -a / --all in any form. Stop at `--`
# (positional separator). We don't track positional path args — see the
# header comment on why sources 1+2 already cover path-mode commits.
dash_a=0
i=$((commit_idx + 1))
end=${#tokens[@]}
while [ $i -lt $end ]; do
  t="${tokens[$i]}"
  if [[ "$t" == "--" ]]; then
    break
  elif [[ "$t" == "-a" || "$t" == "--all" ]]; then
    dash_a=1
    break
  elif [[ "$t" == -a* ]]; then
    # Short-flag bundle starting with -a (e.g. -am "msg", -av, -aSGPGKEY).
    # First-char rule: `-a` must be the FIRST flag in the bundle. Git parses
    # `-ma` as -m with value `a` (NOT -m + -a), so bundles like -ma, -Sa,
    # etc. are correctly not matched by this branch.
    dash_a=1
    break
  fi
  i=$((i + 1))
done

# Collect candidate paths. A failure here means we cannot prove the absence
# of secrets — DENY rather than pass silently. `if ! var=$(...)` is the
# bash-set-e-safe form: assignment happens regardless, exit code is tested.
if ! staged="$(git diff --cached --name-only 2>/dev/null)"; then
  echo "block-secrets.sh: git diff --cached --name-only failed (denying — cannot prove absence of secrets)" >&2
  deny "BLOCKED: could not enumerate staged files (\`git diff --cached --name-only\` failed). The hook cannot prove the absence of secrets in this commit. Resolve the git state (release any \`.git/index.lock\`, fix repository corruption, re-clone if needed) and retry."
  exit 0
fi

modified=""
if [ "$dash_a" -eq 1 ]; then
  if ! modified="$(git ls-files -m 2>/dev/null)"; then
    echo "block-secrets.sh: git ls-files -m failed under -a/--all (denying)" >&2
    deny "BLOCKED: could not enumerate modified-tracked files (\`git ls-files -m\` failed) while a \`-a\` / \`--all\` commit was requested. Resolve the git state and retry."
    exit 0
  fi
fi

# Filter candidates via the deny/allow regexes.
# Deny: .env, .env.<anything-without-slash>, <prefix>.key, <prefix>.pem,
# <prefix>secrets.json — anchored to start-of-name (line start or after /).
# Allow: .env.example, .env.sample, .env.template (basename-anchored).
deny_re='(^|/)(\.env(\.[^/]*)?|[^/]*\.key|[^/]*\.pem|[^/]*secrets\.json)$'
allow_re='(^|/)\.env\.(example|sample|template)$'

hits="$(
  printf '%s\n%s\n' "$staged" "$modified" \
    | awk 'NF' \
    | sort -u \
    | grep -E "$deny_re" \
    | grep -Ev "$allow_re" \
    || true
)"

if [ -n "$hits" ]; then
  reason="BLOCKED: this commit would include likely-secret file(s):"$'\n'"${hits}"$'\n'"Move secrets out of the working tree, add a matching entry to .gitignore, and use .env.example (or similar) for safe templates. If the match is a false positive (file is intentionally checked in and contains no secrets), rename it or ask the user to confirm out loud before bypassing."
  deny "$reason"
  exit 0
fi

allow
exit 0
