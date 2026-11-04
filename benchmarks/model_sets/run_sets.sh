#!/usr/bin/env bash
# Run the benchmark suite against three alternate model sets
# (max / optimal / economy) and tag archive files with the set name.
#
# Idempotent — a (set, scenario) pair whose final iteration is already
# archived is skipped on rerun. A failure inside one scenario does NOT
# abort the rest of the batch; the driver tags whatever was produced
# and moves on. Re-run the script to retry failed scenarios.
set -euo pipefail

ITERATIONS="${ITERATIONS:-3}"
SCENARIOS=(
  memory_follow_up_marcus
  memory_follow_up_marcus_graph_only
  autonomy_three_guards_tavern
  escalation_guard_assault
  npc_autonomy_murder_plot
)

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RESULTS_DIR="$REPO_ROOT/benchmarks/results"
LOG_DIR="$REPO_ROOT/benchmarks/model_sets/logs"
mkdir -p "$LOG_DIR"
cd "$REPO_ROOT"

_tag_new_files() {
  # Tag every untagged archive file newer than the marker with set-<name>__
  local marker="$1" set_name="$2"
  find "$RESULTS_DIR" -newer "$marker" -type f \
    \( -name "*.json" -o -name "*.md" \) \
    -exec bash -c '
      for f in "$@"; do
        dir="${f%/*}"; base="${f##*/}"
        case "$base" in
          set-*) continue ;;
        esac
        mv "$f" "$dir/set-${SET_NAME}__${base}"
      done
    ' _ {} +
}

# Run one (set, scenario) pair. Tolerates failures.
run_one() {
  local set_name="$1" scenario="$2"; shift 2
  local logfile="$LOG_DIR/${set_name}.log"
  local final_iter=$((ITERATIONS - 1))
  # Skip if the last iteration is already archived for this set+scenario.
  if compgen -G "$RESULTS_DIR/set-${set_name}__*_${scenario}_iter${final_iter}.json" > /dev/null; then
    echo "[$set_name/$scenario] already complete — skipping" | tee -a "$logfile"
    return 0
  fi
  local marker
  marker="$(mktemp)"
  touch "$marker"
  echo "=== [$set_name/$scenario] start: $(date -u +%FT%TZ) ===" | tee -a "$logfile"
  set +e
  env "$@" uv run python -m benchmarks run --scenario "$scenario" --iterations "$ITERATIONS" >> "$logfile" 2>&1
  local rc=$?
  set -e
  if [ "$rc" -ne 0 ]; then
    echo "[$set_name/$scenario] FAILED (rc=$rc) — tagging partial output and continuing" | tee -a "$logfile"
  else
    echo "[$set_name/$scenario] OK ($(date -u +%FT%TZ))" | tee -a "$logfile"
  fi
  SET_NAME="$set_name" _tag_new_files "$marker" "$set_name"
  rm -f "$marker"
}

run_set() {
  local set_name="$1"; shift
  echo "===== SET: $set_name ====="
  for scenario in "${SCENARIOS[@]}"; do
    run_one "$set_name" "$scenario" "$@"
  done
}

# Max (frontier)
run_set "max" \
  DIRECTOR_MODEL=gpt-5.4 \
  AGENT_MODEL=google/gemini-2.5-pro \
  NARRATOR_MODEL=claude-sonnet-5-5 \
  DRAMATURGE_MODEL=gpt-5.4 \
  DRAMATURGE_ENABLED=true

# Optimal (Pareto sweet spot)
run_set "optimal" \
  DIRECTOR_MODEL=gpt-5.4-mini \
  AGENT_MODEL=deepseek/deepseek-chat-v3.1 \
  NARRATOR_MODEL=deepseek/deepseek-v4-pro \
  DRAMATURGE_MODEL=gpt-5.4-mini \
  DRAMATURGE_ENABLED=true

# Economy (rock-bottom)
run_set "economy" \
  DIRECTOR_MODEL=gpt-5.4-nano \
  AGENT_MODEL=deepseek/deepseek-chat-v3.1 \
  NARRATOR_MODEL=google/gemini-2.5-flash \
  DRAMATURGE_MODEL=gpt-5.4-nano \
  DRAMATURGE_ENABLED=false

echo "All model sets attempted. Check benchmarks/model_sets/logs/ and benchmarks/results/ for outputs."
