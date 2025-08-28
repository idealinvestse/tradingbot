---
trigger: always_on
---

# Coding Guidelines – Tradingbot-projekt

Följ denna standard för all kod i projektet. Den är optimerad för en Python-baserad krypto-tradingbot (t.ex. Freqtrade) som körs på en **Ubuntu-server med potentiell GPU-acceleration (AMD ROCm) eller via ett molnbaserat GPU-API**. Fokus ligger på backtest, paper trading och säker live-handel.

 # Coding Guidelines – Tradingbot-projekt (Konsolideringsfas)
 
 Denna version av riktlinjer är optimerad för nuvarande fas: konsolidering till produktionsduglig grund. Fokus: säkerhet, reproducerbarhet, observability, risk‑guardrails, och strikt kvalitet. Gäller hela repo:t (**Ubuntu-miljö med GPU-stöd**), Freqtrade‑kompatibla strategier och vår fristående strategi-/rapportmodul under `app/strategies/`.
 
 Uppdaterad (UTC): 2025-08-28
 
 ## Sammanfattning (icke-teknisk)
 - Syfte: Bygga en stabil, spårbar och säker grund innan vidare innovation.
 - Säkerhet: Inga hemligheter i repo. Testnet/paper före live. Guardrails på plats.
 - Spårbarhet: Resultat, konfig och datafönster versioneras och kan återskapas.
 - Kvalitet: Strikta typer, lint, tester och tydliga loggar/metrics.

## Principer
- Säkerhet först. Ingen API‑nyckel i repo/bild. Testnet default. Guardrails i kod och CI.
- Reproducerbarhet. Deterministiska backtester, frysta beroenden, versionerad data/konfig.
- Enkelhet > smarthet. Läsbar, testbar kod. Feature flags för experiment.
- Fail fast + tydliga loggar. Strukturerad loggning, observability, mätvärden.

## Nuvarande fas och fokus
- Konsolidera: Implementera robust körning, indexering och rapportering.
- Observability: JSON‑loggar, mätvärden, grundläggande incidentspårning.
- Risk: Globala guardrails, timeouts, backoff och circuit breaker.
- Testbarhet: 80%+ enhetstester i `app/` och kritiska utils, regressionstester för backtest.

## Projektstruktur (konkret)
- `app/` – kärnlogik, adapters, risk, utils
- `app/strategies/` – registry, introspect, metrics, reporting, `persistence/sqlite.py`, `runner.py`
- `user_data/` – Freqtrade artefakter
  - `strategies/` – strategiklasser
  - `configs/` – `config.testnet.json`, `config.mainnet.json`
  - `backtest_results/` – `.meta.json` + `.zip`
  - `hyperopt_results/` – `.fthypt`
- `scripts/` – `strategy_cli.py`, `strategies_registry_sync.py`, `strategies_registry_export_sqlite.py`, `dca_scheduler.py`
- `tests/` – unit, integration, regression
- `docs/` – riktlinjer, runbooks, rapporter (ex. `RESULTS.md`)
- `docker-compose.yml` – lokal/server-drift (Ubuntu)

## Python‑stil och typer
- Formatter/lint: Black, Ruff, isort. MyPy strict för `app/` och `app/strategies/`.
- PEP8 + typer: All ny kod typannoteras. Publika API:er har docstrings (Google/Numpy).
- Namngivning: `snake_case` (funktion/variabel), `PascalCase` (klass), `UPPER_CASE` (konstant).
- Imports: Standardlib, tredjeparts, lokalt – separerade block. Inga imports mitt i filer.
- Felhantering: Fånga specifika undantag, lägg till kontext, logga strukturerat, återkasta vid behov.

## AI‑assistent (Windsurf) – samarbetsrutin
- Små, fokuserade patchar. Dela stora ändringar i sektioner (<300 rader per patch).
- Följ repo‑regler: typer, lint, tester. Uppdatera/skriv tester för ändrat beteende.
- Inga hemligheter i patch/output. Aldrig visa nycklar/loggutdrag med känsligt innehåll.
- Imports alltid överst. Om ändring kräver import, se till att filens topp uppdateras separat.
- Använd befintliga moduler: `app/strategies/metrics.py`, `app/strategies/reporting.py`, `app/strategies/persistence/sqlite.py`, `app/strategies/runner.py`.
- Commit‑stil: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:` …) + kort motiv.

## Konfiguration och hemligheter
- Pydantic `BaseSettings` för validerad konfig; schema i kod där rimligt.
- `.env` endast lokalt, miljövariabler i CI. Aldrig API‑nycklar i repo/Docker‑image.
- Miljöer: `testnet` default lokalt. Explicit växel till `mainnet`.
- Feature flags: via env/konfig per strategi/funktion.

## Numerisk korrekthet (kritisk)
- Decimal för pengar: `decimal.Decimal` med korrekt precision/`quantize`. Undvik float för belopp/avgifter.
- Tidsserier: Numpy/Pandas för vectoriserade beräkningar. Kontrollera NaN/inf.
- Rundning: Centralisera regler per marknad/ticksize.

## Tid, zoner och data
- All intern tid i UTC. Konvertera vid I/O. Dokumentera tidsfönster i rapporter.
- Klocka: Server- eller exchange‑tid; skydda mot drift.
- Datakvalitet: Validera OHLCV (luckor/duplikat). Lagra källmetadata och version.

## Strategistandard (Freqtrade)
- Struktur:
  - `populate_indicators()` – indikatorer, inga side effects.
  - `populate_entry_trend()` / `populate_exit_trend()` – signaler, inga externa anrop.
  - Parametrar via `IntParameter`, `DecimalParameter` för hyperopt.
- Prestanda: Vectorisera; undvik per‑rad Python‑loopar i indikatorer.
- Dokumentera: Hypotes, marknader, timeframe, indikatorer, riskantaganden.
- Backtest‑determinism: Lås seeds, versionera datafönster, logga konfig i rapport.

## Risk- och orderhantering
- Globala guardrails: Max daglig drawdown, max samtidiga trades, per‑marknadsexponering.
- Orderpolicy: Tidsgränser, idempotens (`clientOrderId`), retry med backoff, hantera rate limits.
- Stop/TP: Alltid definierade, hantera glidning och partial fills.

### RiskManager och guardrails (implementerat)
- Kod: `app/strategies/risk.py` (`RiskManager`, `RiskConfig`). `pre_run_check()` gate: Circuit Breaker. Körslots via `acquire_run_slot()`/`release_run_slot()`. Extra backtest-/live‑guardrails finns i `_continue_pre_run_check()` för anropare som vill strikt‑gatera.
- Loggning: Korrelations‑ID (`correlation_id`) propageras i loggar och sparas i lockfiler (`cid`).
 
__Miljövariabler och defaultvärden__
- `RISK_MAX_CONCURRENT_BACKTESTS`: int|None. Begränsar endast `kind='backtest'` i `acquire_run_slot()`.
- `RISK_CONCURRENCY_TTL_SEC`: standard 900 sek (TTL för lockfiler).
- `RISK_STATE_DIR`: standard `user_data/state`.
- `RISK_CIRCUIT_BREAKER_FILE`: standard `${RISK_STATE_DIR}/circuit_breaker.json`.
- `RISK_ALLOW_WHEN_CB`: `1`/`true` tillåter körning trots aktiv CB.
- `RISK_MAX_BACKTEST_DRAWDOWN_PCT`: float, 0..1 (eller >1 tolkas som procent).
- `RISK_DB_PATH`: standard `user_data/registry/strategies_registry.sqlite`.
- `RISK_LIVE_MAX_CONCURRENT_TRADES`: int (live‑gating via context).
- `RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT`: float, 0..1 (eller >1 tolkas som procent).
 
__Samtidighet (körslots via lockfiler)__
- Katalog: `${RISK_STATE_DIR}/running/`. Filnamn: `{kind}_{unix_ts}_{pid}_{cid}.lock`.
- TTL‑städning: filer äldre än `RISK_CONCURRENCY_TTL_SEC` rensas automatiskt.
- Användning: `ok, reason, lock = RiskManager().acquire_run_slot(kind, correlation_id)` och frigör alltid i `finally`: `release_run_slot(lock, correlation_id)`.
- Observera: `app/strategies/runner.py::run_ai_strategies()` använder `kind="ai_strategy"` (ej begränsad av `RISK_MAX_CONCURRENT_BACKTESTS`). Sätt `kind='backtest'` om du vill tillämpa kvoten.
 
__Circuit breaker__
- Lagring: JSON‑fil `RISK_CIRCUIT_BREAKER_FILE` (default `user_data/state/circuit_breaker.json`).
- Strukturexempel:
   ```json
   {
     "active": true,
     "reason": "manual",
     "until_iso": "2025-08-17T10:15:00+00:00"
   }
   ```
- CLI `scripts/circuit_breaker.py`:
  - Status: `python -m scripts.circuit_breaker status`
  - Aktivera (60 min): `python -m scripts.circuit_breaker enable --reason "incident-123" --minutes 60`
  - Aktivera tills ISO‑tid: `python -m scripts.circuit_breaker enable --until 2025-08-17T10:15:00Z`
  - Avaktivera: `python -m scripts.circuit_breaker disable`
  - Alternativ: `--state-dir` eller `--file` för filväg.
- `pre_run_check()` blockerar körning när CB är aktiv (om inte `RISK_ALLOW_WHEN_CB` är satt).
 
__Backtest‑drawdown‑guard__
- När `RISK_MAX_BACKTEST_DRAWDOWN_PCT` är satt läses senaste `max_drawdown_account` från SQLite (`RISK_DB_PATH`). Värden >1 tolkas som procent (25 ⇒ 0.25).
- Implementerat i `_recent_backtest_drawdown()`. Gating sker i `_continue_pre_run_check()` för de anrop som väljer det.
 
__Live‑guardrails__
- `RISK_LIVE_MAX_CONCURRENT_TRADES` och `RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT` används med `context`:
  - `open_trades_count`: antal öppna trades.
  - `market_exposure_pct`: dict `{marknad: andel}` (0..1 eller procent >1).
- Normalisering: värden >1 betraktas som procent.
- Gating i `_continue_pre_run_check()`; `check_risk_limits()` gör en snabb CB‑kontroll.

## Indexering och rapportering av resultat (backtest/hyperopt)
- Kod: `app/strategies/metrics.py` (indexering) och `app/strategies/reporting.py` (Markdown‑rapport). DB‑schema: `app/strategies/persistence/sqlite.py`.

__Indexering (scripts/strategy_cli.py)__
- Backtests: `python -m scripts.strategy_cli index-backtests --dir user_data/backtest_results --db-out user_data/registry/strategies_registry.sqlite`
- Hyperopts: `python -m scripts.strategy_cli index-hyperopts --dir user_data/hyperopt_results --db-out user_data/registry/strategies_registry.sqlite`

__Rapportgenerering__
- Variant A (rekommenderad, samma DB):
  - `python -m scripts.strategy_cli report-results --db user_data/registry/strategies_registry.sqlite --out docs/RESULTS.md`
- Variant B (alternativ script med egna default‑vägar):
  - `python -m scripts.render_results_report --db user_data/backtest_results/index.db --out user_data/backtest_results/RESULTS.md --limit 50`

__DB‑vägar och tabeller__
- Standard i indexering/rapport (Variant A): `user_data/registry/strategies_registry.sqlite`.
- Alternativ default i `render_results_report.py`: `user_data/backtest_results/index.db`.
- Nyckeltabeller: `runs`, `metrics`, `artifacts`, `experiments`, `incidents`.

__Nyckelmetrik (urval)__
- Rapport (`generate_results_markdown_from_db`): `profit_total`, `profit_total_abs`, `sharpe`, `sortino`, `max_drawdown_abs`, `winrate`, `loss`, `trades` (+ `Data Window`, `Config Hash` om finns).
- Indexering (`index_backtests`): lägger även `window_days`, `timeframe_minutes`, `parse_ms`; ZIP‑parsern extraherar bl.a. `profit_total_pct`, `max_drawdown_account` m.fl.
- Precision: Monetära värden hanteras som `Decimal` och kvantiseras till 8 decimaler innan DB‑skrivning (REAL).

## Fel‑tolerans och robusthet
- Timeout + backoff: Alla I/O med timeout, exponential backoff, jitter.
- Circuit breaker: Pausa handel vid upprepade fel/avvikelser.
- Atomiska steg: Bryt ner sekvenser; återskapa från säkra checkpoints.

## Loggning och observability
- Strukturerade loggar (JSON) med korrelations‑ID.
- Nivåer: INFO (flöde), DEBUG (dev), WARN/ERROR (incidenter).
- Mätvärden: Latens, orders lyckade/misslyckade, PnL, drawdown, slippage.
- Spårbarhet: Logga konfig‑hash, datafönster, versionsinfo i backtest/hyperopt‑rapporter.

## Testpolicy
- Unit tests: 80%+ i `app/` och kritiska utils. Pytest.
- Property‑based: Hypothesis för indikatorer/signaler.
- Integration: Sandbox/Testnet mot börs‑API, rate‑limit mocks.
- Backtest‑regression: Golden‑master på PnL/Sharpe/trade count per strategi.
- Contract tests: Mot externa adapters (utbytes‑API, datakälla).
- CI‑gates: Blockera merge om tester/lint/mypy failar.

## GPU-acceleration och prestanda
- **Lokal GPU (AMD ROCm)**: För att använda AMD Vega 64-GPU:n på Ubuntu-servern, säkerställ att ROCm-drivrutinerna är korrekt installerade. Bibliotek som `pytorch-rocm` kan användas för ML-modeller.
- **Moln-GPU API**: Som alternativ kan externa GPU-API:er (t.ex. Vast.ai, RunPod, Google Colab Pro) användas för tunga beräkningar som hyperoptimization eller modellträning. Detta kräver adapters för att skicka data och ta emot resultat.
- **Parallellism**: Multiprocess för backtests; undvik GIL‑hotspots. Utforska GPU-accelererade bibliotek för tidsserieanalys om flaskhalsar uppstår.

## Samtidighet
- I/O‑tyngt: `asyncio` eller välkapslad trådpool. Blockera inte event loop.
- Avslut: Graceful shutdown; cancel tasks, flush loggar, stäng sessions.
- Trådsäkerhet: Delade objekt skyddas; inga globala mutabla tillstånd i strategier.
