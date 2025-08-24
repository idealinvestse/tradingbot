# ADR 0001: Monetary Precision with Decimal (8 dp)

Status: Accepted
Date: 2025-08-25

## Context
- Monetary values require deterministic, lossless handling across parsing, reporting, and persistence.
- SQLite `metrics.value` is stored as REAL today. Using float in Python risks rounding drift.

## Decision
- Use `decimal.Decimal` internally for all monetary values within `app/strategies/`.
- Quantize to 8 decimal places at code boundaries (DB insert/fetch and reporting display).
- Keep SQLite schema unchanged (REAL) for compatibility and simplicity; precision is enforced in code.
- Tests assert 8-decimal formatting and equality at the Decimal boundary.

## Alternatives Considered
- Store DECIMAL as TEXT in SQLite: more explicit precision but adds complexity and migrations.
- Store integers with fixed scale (e.g., 1e8): robust but reduces readability and requires consistent scaling helpers.

## Consequences
- Deterministic reports and metrics comparisons; reduced float rounding issues.
- Slight overhead of Decimal conversions at DB boundaries.
- Clear precision contract documented in tests and docs.

## References
- `app/strategies/metrics.py` (quantization on insert/fetch)
- `app/strategies/reporting.py` (8 dp display)
- `tests/test_reporting.py`, `tests/test_metrics.py`, `tests/test_hyperopt_metrics.py`
