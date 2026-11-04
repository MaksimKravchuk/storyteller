---
type: Component
title: Costs
description: Model pricing and reporting helpers for tracking provider usage cost.
resource: costs/
tags: [costs, pricing, reporting]
---

# Directory Instructions

Root `AGENTS.md` and `CLAUDE.md` remain authoritative. This file adds local
context for `costs/`.

# Boundary

`costs/` owns model pricing and usage reporting helpers. It is pure
computation: no DB queries (rows come from callers in
[interfaces](/interfaces/AGENTS.md)) and no provider calls.

# Contents

- `model_pricing.py` — `DEFAULT_MODEL_PRICES`, `ModelPrice`, `CallCost`,
  `configured_prices` (`MODEL_PRICING_JSON` overrides), `price_for_model`,
  `calculate_call_cost_usd`.
- `reports.py` — `build_cost_summary(rows, cfg)` for admin spend reports.
- Consumers: `interfaces/admin_reports.py`, `interfaces/web/beta_policy.py`.

# Local Rules

- Keep pricing data explicit and covered by tests.
- Coordinate provider naming with [llm](/llm/AGENTS.md).
- Price changes and new models are recorded in the ADR that motivates them
  (ADR-0018 for `gpt-6-luna`, ADR-0020 for poster image models).

# Patterns

- Money is `Decimal`, built via `_decimal_from_config` (`Decimal(str(x))`),
  quantized to six places in `calculate_call_cost_usd`.
- Price tables are `MappingProxyType` keyed by base model id; dated snapshot
  ids resolve by stripping `_SNAPSHOT_SUFFIX`.
- Unknown models and missing usage return flags (`unpriced`,
  `missing_usage`) with zero cost instead of raising.

# Anti-patterns

- Using `float` for prices or totals; binary-float artifacts leak into
  reports (`_decimal_from_config` docstring; `tests/test_model_pricing.py`).
- Dropping a price for a model that may be switched back to; budget gates
  then see zero spend (`gpt-image-1-mini` comment, #355).
- Changing `_Fields` JSON names in `reports.py`; admin report consumers read
  them (`tests/test_admin_cost_reports.py`).

# Related

- [Interfaces](/interfaces/AGENTS.md)
- [Defaults](/defaults/AGENTS.md)
- [LLM](/llm/AGENTS.md)
