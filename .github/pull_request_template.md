# Pull Request

Please follow our Coding Guidelines and complete this checklist.

## Summary
- What does this PR change and why?
- Link to related issues/ADRs (if any).

## Checklist (Conventional Commits + Quality Gates)
- [ ] Title uses Conventional Commits (feat:, fix:, docs:, refactor:, test:, chore:)
- [ ] Lint/format/typecheck/tests pass locally (ruff/black/mypy/pytest)
- [ ] Security scan (safety) passes locally
- [ ] No secrets or API keys added to repo or Docker image
- [ ] Environment variables/config described in README/RUNBOOK if changed
- [ ] Risk guardrails unchanged or documented (circuit breaker, concurrency, drawdown, live caps)
- [ ] Backtest/paper before live (if applicable)
- [ ] Updated docs (README, RUNBOOK, ROADMAP, STRATEGY_MODULE_VISION) if needed
- [ ] Added/updated tests (unit/integration/regression) for behavior changes
- [ ] Observability: logs/metrics updated if behavior changed

## Testing
- [ ] Unit tests added/updated
- [ ] Integration/smoke tests (note any skipped external deps)
- [ ] Regression artifacts updated (if strategy behavior changed)

## Screenshots/Artifacts (optional)
- Attach logs, reports, or screenshots if useful.
