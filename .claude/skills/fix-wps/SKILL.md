---
name: fix-wps
description: Fix WPS (wemake-python-styleguide) linter violations. Use when flake8 reports WPS errors or user asks to fix WPS issues.
context: fork
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Fix WPS linter violations

You fix WPS (wemake-python-styleguide) violations using official documentation for reasoning and solutions.

## Step 1: Identify violations

If the user provided specific WPS codes or file paths, use those. Otherwise run the linter:

```bash
uv run flake8 . --select=WPS 2>&1 | head -100
```

## Step 2: Research each unique violation

For each unique WPS code, fetch the official docs to understand the rule:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_wps_rule.py WPS<CODE>
```

This returns the rule's **reasoning**, **solution**, and **correct/wrong code examples** from the official wemake-python-styleguide documentation.

Read and understand the reasoning before making changes.

## Step 3: Check existing suppressions

Before fixing, check if the rule is already suppressed in `setup.cfg`:

```bash
grep -n "WPS<CODE>" setup.cfg
```

If suppressed globally, skip it.

## Step 4: Fix violations

Apply fixes based on the documented solution:

- **Prefer code fixes over suppressions** — fix the actual code rather than adding `# noqa` comments
- **When suppression is appropriate** — if a rule conflicts with project conventions (e.g., WPS305 f-strings ban), add suppression to `setup.cfg` `ignore` or `per-file-ignores`, not individual `# noqa`
- **Batch by rule** — fix all instances of the same WPS code together for consistency

## Step 5: Verify

Re-run the linter on affected files:

```bash
uv run flake8 <file_paths> --select=WPS
```

$ARGUMENTS
