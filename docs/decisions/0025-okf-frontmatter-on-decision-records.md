---
type: Decision
title: "Decision records are Open Knowledge Format concepts with a checked `governs` list"
status: stable
governs:
  - docs/decisions
  - tests/test_okf_bundle.py
  - .claude/skills/decision-records/SKILL.md
  - AGENTS.md
---

# ADR-0025: Decision records are Open Knowledge Format concepts with a checked `governs` list

Date: 2026-11-04
Status: Accepted
Decision owner: Max
Related: [Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md), `tests/test_okf_bundle.py`, ADR-0014, ADR-0017

## Context

The scoped `AGENTS.md` files already carry OKF frontmatter and are checked by
`tests/test_okf_bundle.py`. The ADRs in `docs/decisions/` did not: agents had to
read every ADR body to learn which ones constrain the file they are about to
change, even though `CLAUDE.md` requires checking accepted decisions before
touching architecture, prompts, persistence, or player-facing behavior. Nothing
flagged an ADR whose referenced files had been deleted or moved.

The `okf/` folder in `GoogleCloudPlatform/knowledge-catalog` is a frozen copy;
the format now lives in `GoogleCloudPlatform/open-knowledge-format` (Apache 2.0).

## Decision

- Every ADR starts with OKF frontmatter: `type: Decision`, `title`, `status`
  (OKF lifecycle: `draft` = Proposed, `stable` = Accepted, `deprecated` =
  Superseded/Rejected), and a producer-defined `governs` list of repo paths or
  globs the decision constrains.
- `tests/test_okf_bundle.py` checks the frontmatter and that every `governs`
  entry still matches something in the repo.
- The human-readable `Status:` line in the body stays; frontmatter is for
  machines (agents, grep, OKF viewers).
- We adopt the format only. The OKF reference agent (BigQuery, Gemini, ADK) is
  not a dependency.

## Alternatives considered

- **Vendor the OKF reference agent.** Rejected: it ingests BigQuery catalogs and
  pulls heavy Google dependencies with no use here.
- **A separate generated OKF bundle about the codebase.** Rejected: duplicates
  `AGENTS.md` and ADRs and would drift.
- **Generated `index.md` per OKF §8.** Deferred: `grep` over frontmatter answers
  the same question without another file to keep in sync.

## Consequences

- An agent finds the decisions governing a path with
  `grep -l "^  - <path>$" docs/decisions/*.md`.
- Deleting or moving a governed file fails CI until the ADR is updated, which
  forces a look at whether the decision still holds.
- Initial `governs` lists were extracted from backticked paths in each ADR and
  may be broader than the decision's real scope; trim them when touching an ADR.
- New ADRs written from the `decision-records` skill template include the
  frontmatter; ADRs on unmerged branches must add it before merge.

## Verification

`uv run pytest tests/test_okf_bundle.py -v`

## Future-agent guardrails

- Do not remove a `governs` entry just to make CI pass; check whether the
  decision moved with the code first.
- Keep `status` in frontmatter consistent with the body `Status:` line.
