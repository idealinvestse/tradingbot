# Tradingbot Roadmap – Konsolidering till Produktion

Denna roadmap fokuserar på en säker och reproducerbar väg till produktionsdugligt läge. Den är uppdelad i flera parallella arbetslinjer (lanes) med 5 prioriterade steg per kategori. Alla aktiviteter följer `docs/CODE_GUIDELINES.md` (säkerhet, determinism, observability, typer, Decimal, CI-gates) och utgår från befintliga moduler:

- `app/strategies/runner.py`, `metrics.py`, `reporting.py`, `persistence/sqlite.py`, `introspect.py`, `registry.py`
- `scripts/strategy_cli.py` (+ registry-skript)
- Artefakter i `user_data/backtest_results/` och `user_data/hyperopt_results/`

## Status (2025-08-29)

### ✅ Implementerat (Konsolideringsfas)
- **Precision**: `Decimal` med 8 decimalers kvantisering integrerad i `app/strategies/metrics.py` och `reporting.py`
- **Validering**: Pydantic-modeller för backtest/hyperopt; regressionstester implementerade
- **Risk Management**: `RiskManager` med circuit breaker, concurrency locks, drawdown guardrails och live limits
- **Incidentloggning**: `log_incident()` persisterar till SQLite `incidents`-tabell med strukturerad JSON-loggning
- **CI/CD**: GitHub Actions med `pytest`, `ruff`, `black`, `mypy`, `safety` - alla steg gröna
- **CLI-verktyg**: `scripts/strategy_cli.py` för indexering, rapportgenerering och dokumentation
- **Backup/Restore**: `scripts/backup_restore.py` för disaster recovery
- **Dokumentation**: Omfattande uppdatering av alla docs med aktuell information

### 🔄 Pågående
- **Observability**: JSON-loggning med korrelations-ID implementerat, metrics under utveckling
- **Automatisering**: CLI-integration för kontinuerlig rapportgenerering
- **Testning**: Utökad testsuite med property-based testing

### 📋 Nästa steg
- **Prometheus-integration**: Metrics export för Grafana dashboards
- **Live trading**: Production-ready deployment med full observability
- **AI-strategier**: Utökad ML-pipeline med feature engineering

## Nästa 5 steg (kärnkategorier)

### Observability & Loggning
1) Central logg‑fabrik i `app/` (JSON + correlation_id injection).
2) Mätvärden i `metrics.py`: parse‑latens, indexerade runs, felräknare.
3) `reporting.py`: inkludera konfig‑hash/datafönster i rapporter.
4) Spec för Grafana dashboards; definiera exportformat.
5) Incident‑rapportgenerator (Markdown) från `incidents`.

### Risk & Orderpolicy
1) Post‑trade audit: slippage och orderlatens som metrics.
2) Automatisk CB‑trigger vid upprepade fel/avvikelser (policy + tests).
3) Per‑strategi exponeringsgränser (feature flag via env/konfig).
4) Idempotenta order‑ID (design + tests) för live‑läge.
5) Enhetliga riskhändelsekoder och dokumenterad severity‑taxonomy.

### Data & Reproducerbarhet
1) Logga `schema_version`, seeds och konfig‑hash per run i DB.
2) Checksums (SHA256) för artefakter i `artifacts`‑tabellen.
3) Datafönster‑metadata (UTC) i `runs.data_window` och rapport.
4) CLI‑indexering i `scripts/strategy_cli.py` med dubblettskydd.
5) Regression “golden master” för utvalda strategier.

### CI/CD & Supply Chain
1) Cacha testdata/venv för snabbare pipelines.
2) Publicera test‑artefakter (rapport/coverage) i Actions.
3) Coverage‑gate (ex. 80% för `app/`).
4) Safety/dep‑scan rapport som artifacts och badge.
5) PR‑mall med checklista från `CODE_GUIDELINES.md`.

### Dokumentation & Runbooks
1) `RESULTS.md`: sektion för incidenter senaste veckan.
2) `RUNBOOK.md`: loggnivåpolicy och examples (JSON snippets).
3) ADR om penningprecision/SQLite‑schema och beslut.
4) DX‑guide: pre‑commit‑hooks installation och användning.
5) README‑badge för CI‑status.

## Lane 1 — Arkitektur & Orkestrering (Runtime)
- Mål: Enhetligt, idempotent körnav för backtest/hyperopt/paper/live med tydliga kontrakt och loggning.
- Ägare: Runtime Maintainer (backup: Windsurf-agent). Beroenden: Observability, Risk.
- Steg (5):
  1) Förstärk `runner.py` med metoder: `run_backtest`, `run_hyperopt`, `run_paper`, `run_live` + correlation_id.
     - Deliverable: Körbar modul med enhetliga signaturer.
  2) Pydantic-kontrakt för in-/utdata (params/resultat) och `run_id`/artefaktpaths.
     - Deliverable: `models.py`/`runner.py`-typer; mypy strict pass.
  3) Idempotens + retries: client IDs, exponential backoff med jitter vid I/O.
     - Deliverable: Helfallstester och loggat retry-beteende.
  4) Felklasser: `DataValidationError`, `ExchangeTimeout`, `RateLimitExceeded` med kontext.
     - Deliverable: Central felhantering + strukturerade loggar.
  5) CLI-koppling: `strategy_cli.py` kommandon som triggar ovanstående och returnerar status.
     - Deliverable: Dokumenterade kommandon i `docs/`.

## Lane 2 — Observability & Loggning
- Mål: Full spårbarhet (JSON-loggar, correlation-id) och basala mätvärden (Prometheus-stil).
- Ägare: Observability Maintainer. Beroenden: Runtime, Reporting.
- Steg (5):
  1) Logg-fabrik i `app/` som injicerar `correlation_id`, `run_id`, `strategy`, `timeframe` (JSON).
  2) Metrics i `metrics.py`: counters/gauges för körningstid, fel, trades, parse-/I/O-latens.
  3) Spårbarhet i `reporting.py`: konfig-hash, datafönster, schema-version i alla rapporter.
  4) Loggnivåpolicy (INFO/DEBUG/WARN/ERROR) dokumenterad i `docs/RUNBOOK.md`.
  5) Dashboard-baskort (specifikation) för Grafana; endpoints redo att skördas.

## Lane 3 — Risk & Orderpolicy
- Mål: Guardrails före alla affärer och robust incidenthantering.
- Ägare: Risk Maintainer. Beroenden: Runtime, Observability.
- Steg (5):
  1) `RiskManager` i `app/`: max daglig DD, max samtidiga trades, per-marknadsexponering (Decimal).
  2) `runner.py` anropar `pre_trade_check()` före order/backtest-simulering.
  3) Idempotenta orders, `clientOrderId`-policy, timeouts och backoff.
  4) Circuit breaker vid tröskel av fel/avvikelser; skriv incident till SQLite.
  5) Post-trade audit: slippage/avvikelse loggas och exponeras som metrics.

## Lane 4 — Data & Reproducerbarhet
- Mål: Validerade artefakter och deterministiska regressionskörningar.
- Ägare: Data Maintainer. Beroenden: Metrics/Reporting, Persistence.
- Steg (5):
  1) Pydantic-modeller för backtest-/hyperopt-artefakter i `metrics.py` (+ schema_version).
  2) Checksums (SHA256) och lineage; lagras via `persistence/sqlite.py`.
  3) Källmetadata och datafönster loggas och rapporteras.
  4) Determinism: seeds, parametrar, timeframe; dokumenterat i rapport.
  5) CLI-indexering i `strategy_cli.py` för artefakter med dubblettskydd (checksum).

## Lane 5 — Test & Kvalitet
- Mål: Hög täckning och regressionstrygghet.
- Ägare: QA Maintainer. Beroenden: Data & Runtime.
- Steg (5):
  1) Backtest-regressioner i `tests/` (PnL/Sharpe/trade count mot golden master).
  2) Hypothesis för indikatorer/signaler (NaN/inf, invariants).
  3) Kontrakttester för adapters/parsers.
  4) Mypy strict i `app/` och `app/strategies/`; ruff/black/isort speglas i CI.
  5) Stabil testdata/fixtures med versionerade dataset.

## Lane 6 — CI/CD & Supply Chain
- Mål: Automatiska grindar och säker beroendehantering.
- Ägare: CI Maintainer. Beroenden: Test, Guidelines.
- Steg (5):
  1) CI-steg: ruff, black, isort, mypy, pytest (fail-fast; artifacts sparas).
  2) Safety/dep-scan med rapport i pipeline.
  3) Artefakthantering: publicera test-/benchmark-/rapport-artefakter.
  4) Branch-policy: min 1 review, gröna checks, coverage-mål.
  5) Release-taggar (semver) + changelog generering; runbook-spårning.

## Lane 7 — Infrastruktur & Drift (Windows → Container)
- Mål: Härdad containerisering och återställbarhet.
- Ägare: Infra Maintainer. Beroenden: Observability, CI.
- Steg (5):
  1) Docker/Compose: multi-stage, non-root, healthcheck, volymer för `user_data/`.
  2) Miljöparitet: samma Python minor och låsta beroenden i Dev/CI.
  3) Backup/restore-skript i `scripts/` för SQLite och artefakter; dokumentera i `RUNBOOK.md`.
  4) DR-övning: simulera korrupt artifact/avbruten körning; följ runbook.
  5) Prometheus-/Grafana-förberedelser: definiera endpoints/logg-konsumenter.

## Lane 8 — Strategi R&D & Portfölj
- Mål: Säker innovation ovanpå stabil bas.
- Ägare: Research Maintainer. Beroenden: Runner, Data, Test.
- Steg (5):
  1) CI-validering av `introspect.py`/`registry.py` (strategier exponeras korrekt).
  2) Variant-fabrik för parametrar i `app/strategies/` för snabba experiment.
  3) Cross-validation: kör flera marknader/timeframes via `runner.py`.
  4) A/B- och regime-tester (bull/bear/sideways) med standardrapporter.
  5) Senare: portföljprinciper (risk-paritet, korrelationsgränser) och portfölj-metrics.

## Lane 9 — Developer Experience (DX)
- Mål: Hög utvecklarhastighet utan att sänka kvalitet.
- Ägare: DX Maintainer. Beroenden: Guidelines, CI.
- Steg (5):
  1) Pre-commit hooks (black/ruff/isort/mypy) dokumenterade och aktiverade.
  2) README: Snabbstart + länk till `docs/CODE_GUIDELINES.md`.
  3) Templates: PR, strategi-mall, runbook-checklistor.
  4) Minimal notebook/REPL för säker signalvisualisering (utan secrets).
  5) Troubleshooting-sektion i `docs/RUNBOOK.md`.

---

## Tidslinje (förslag)
- Vecka 1–2: Lanes 1–3 (Runtime, Observability, Risk)
- Vecka 2–3: Lanes 4–5 (Data, Test)
- Vecka 3–4: Lanes 6–7 (CI/CD, Infra)
- Vecka 4–5: Lanes 8–9 (R&D, DX)

## KPI:er
- Observability: 100% körningar med correlation-id, <1% oklassificerade fel.
- Test: 80%+ täckning i `app/`; regressionsdiff = 0 inom toleranser.
- Risk: 0 dubblettorders; automatisk circuit breaker vid trösklar.
- Data: 100% artefakter validerade (Pydantic); 0 schema-brott i CI.
- CI: <10 min total runtime; dep-scan utan blockerande CVE.

## Risker & Mitigering
- Tekniska skulder: bryt ned i små patchar, följ guidelines, fail-fast CI.
- Datakvalitet: Pydantic + checksums + lineage; alerts på avvikelser.
- Operativt: DR-övningar och tydlig ägarskap i runbooks.

## Change Control
- Conventional Commits, PR-krav i `CODE_GUIDELINES.md`, granska dashboards/rapporter per release.

## Bilaga — Mappning till repo & dokument
- Runtime: `app/strategies/runner.py`, CLI `scripts/strategy_cli.py`
- Observability: `app/strategies/metrics.py`, `reporting.py`, logg-fabrik i `app/`
- Risk: `app/` (RiskManager), `persistence/sqlite.py`
- Data: `user_data/`, `metrics.py`, `reporting.py`
- Test: `tests/`
- CI: `pyproject.toml`, `mypy.ini`, `.pre-commit-config.yaml`
- Infra: `docker-compose.yml`
- Docs: `docs/CODE_GUIDELINES.md`, `docs/RUNBOOK.md`, `docs/ROADMAP.md`
