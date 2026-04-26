#!/usr/bin/env bash
# PreToolUse hook for `git push`: announce target branch and block direct
# pushes to main/master. Project policy (CLAUDE.md): always use a feature
# branch + PR. If user explicitly authorizes a main push, this hook still
# blocks once — they must re-confirm before the retry succeeds.

set -e
cd "$(dirname "$0")/../.."

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# Belt-and-braces: only act on `git push`. Catches the case where this hook
# is wired without an `if:` filter, or if the filter ever loosens.
if ! [[ "$cmd" =~ (^|[^[:alnum:]_])git[[:space:]]+push([[:space:]]|$) ]]; then
  exit 0
fi

current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

# Default target = current branch's upstream. Override if command has an
# explicit `git push <remote> <refspec>`. For `src:dst` refspecs, dst wins.
target="$current_branch"
read -ra tokens <<<"$cmd"
push_idx=-1
for i in "${!tokens[@]}"; do
  if [[ "${tokens[$i]}" == "push" ]]; then
    push_idx=$i
    break
  fi
done

if [[ $push_idx -ge 0 ]]; then
  positionals=()
  for ((i=push_idx+1; i<${#tokens[@]}; i++)); do
    t="${tokens[$i]}"
    [[ "$t" == -* ]] && continue
    positionals+=("$t")
  done
  if [[ ${#positionals[@]} -ge 2 ]]; then
    ref="${positionals[1]}"
    [[ "$ref" == *:* ]] && ref="${ref#*:}"
    target="$ref"
  fi
fi

if [[ "$target" == "main" || "$target" == "master" ]]; then
  jq -nc --arg t "$target" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("BLOCKED: pushing to " + $t + " violates project policy (CLAUDE.md: never push directly to main). Default workflow is feature branch + PR. If the user explicitly authorized this push, ask them to confirm out loud before retrying.")
    }
  }'
  exit 0
fi

jq -nc --arg b "$current_branch" --arg t "$target" '{
  systemMessage: ("Pushing branch " + $b + " to origin/" + $t)
}'
exit 0
