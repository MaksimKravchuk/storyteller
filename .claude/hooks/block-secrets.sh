#!/usr/bin/env bash
# PreToolUse hook (Bash: git commit): refuse if the commit would include a
# likely-secret file (.env*, *.key, *.pem, *secrets.json). Allowlists common
# non-secret templates (.env.example, .env.sample, .env.template).
#
# Inspects three sources:
#   1) currently-staged files       (always)
#   2) modified-but-tracked files   (only if -a / --all)
#   3) positional path args         (path-mode `git commit path/to/file`)
#
# Gate is on `git commit`, not `git add`, so secrets staged via any path
# (CLI, IDE, git GUI) still get caught at the point of no return.
#
# Fail-open posture (matches check-git-push.sh / protect-migrations.sh): any
# misconfiguration — missing jq, not a git repo, unknown command shape —
# allows the tool with a stderr warning. A hook bug should not wedge a
# legitimate commit.

set -euo pipefail
cd "$(dirname "$0")/../.."

allow() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}\n'
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

# Walk args after `commit`. Skip flag-value pairs (-m "msg", -F file, etc.)
# so the message body isn't scanned as a path. Tokens after `--` are paths.
dash_a=0
positionals=()
i=$((commit_idx + 1))
end=${#tokens[@]}
while [ $i -lt $end ]; do
  t="${tokens[$i]}"
  case "$t" in
    -a|--all) dash_a=1 ;;
    -am|-ma) dash_a=1 ;;
  esac
  case "$t" in
    -m|--message|-F|--file|-c|--reedit-message|-C|--reuse-message|--author|--date|--cleanup|--gpg-sign|-S|-t|--template|--squash|--fixup)
      i=$((i + 2))
      continue
      ;;
    --)
      i=$((i + 1))
      break
      ;;
    -*)
      ;;
    *)
      positionals+=("$t")
      ;;
  esac
  i=$((i + 1))
done
while [ $i -lt $end ]; do
  positionals+=("${tokens[$i]}")
  i=$((i + 1))
done

# Collect candidate paths the commit will include, then filter via grep.
# Deny pattern matches .env, .env.<anything-without-slash>, *.key, *.pem,
# *secrets.json — anchored to start-of-name (line start or after slash).
# Allow pattern exempts common non-secret templates (.env.example etc.).
deny_re='(^|/)(\.env(\.[^/]*)?|[^/]*\.key|[^/]*\.pem|[^/]*secrets\.json)$'
allow_re='(^|/)\.env\.(example|sample|template)$'

hits="$(
  {
    git diff --cached --name-only 2>/dev/null || true
    if [ "$dash_a" -eq 1 ]; then
      git ls-files -m 2>/dev/null || true
    fi
    if [ ${#positionals[@]} -gt 0 ]; then
      printf '%s\n' "${positionals[@]}"
    fi
  } | awk 'NF' | sort -u | grep -E "$deny_re" | grep -Ev "$allow_re" || true
)"

if [ -n "$hits" ]; then
  reason="BLOCKED: this commit would include likely-secret file(s):"$'\n'"${hits}"$'\n'"Move secrets out of the working tree, add a matching entry to .gitignore, and use .env.example (or similar) for safe templates. If the match is a false positive (file is intentionally checked in and contains no secrets), rename it or ask the user to confirm out loud before bypassing."
  jq -nc --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
fi

allow
exit 0
