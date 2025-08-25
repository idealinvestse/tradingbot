---
trigger: always_on
---

# Coding Guidelines – Tradingbot-projekt

Följ denna standard för all kod i projektet. Den är optimerad för en Python-baserad krypto-tradingbot (t.ex. Freqtrade) som körs på en **Ubuntu-server med potentiell GPU-acceleration (AMD ROCm) eller via ett molnbaserat GPU-API**. Fokus ligger på backtest, paper trading och säker live-handel.

# Coding Guidelines – Tradingbot-projekt (Konsolideringsfas)

Denna version av riktlinjer är optimerad för nuvarande fas: konsolidering till produktionsduglig grund. Fokus: säkerhet, reproducerbarhet, observability, risk‑guardrails, och strikt kvalitet. Gäller hela repo:t (**Ubuntu-miljö med GPU-stöd**), Freqtrade‑kompatibla strategier och vår fristående strategi-/rapportmodul under `app/strategies/`.

Uppdaterad (UTC): 2025-08-25

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

## Beroenden och build (Ubuntu)
- **Verktyg**: Poetry eller pip‑tools. Lås versionsfil (`poetry.lock`/fryst `requirements.txt`).
- **Systemberoenden**: Vissa Python-paket kräver systembibliotek. För `TA-Lib`, installera via `sudo apt-get install -y ta-lib-dev`.
- **Pythonversion**: `>=3.10`.
- **Supply chain**: Hash‑checks, skanna beroenden i CI (ex. Safety).

## Containers och drift (Ubuntu/GPU)
- **Docker**: Multi‑stage build, non‑root, healthcheck. Inga hemligheter i image.
- **GPU-stöd i Docker**: För att ge en container tillgång till AMD GPU:er, installera ROCm-drivrutiner på värden och använd `--device=/dev/kfd --device=/dev/dri` med `docker run`.
- **Compose**: Volymer för `user_data/` (data + configs). En tjänst per process. Anpassa `docker-compose.yml` för GPU-stöd vid behov.

## Git‑flöde och code review
- Branching: Trunk‑based med kortlivade feature branches (alternativt GitFlow för releases).
- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:` …) + kort motiv.
- PR‑krav: 1+ godkännande, gröna CI‑checks, ingen ny skuld utan TODO/issue.
- Code owners: Extra review för kritiska områden (risk/ordermotor/strategi).

## Dokumentation
- README för snabbstart (testnet) + lokala körinstruktioner (Ubuntu).
- Runbooks: Incidenter, rollback, nyckelrotation, checklistor inför live.
- ADRs: Större beslut (dataschema, ordermotor, riskpolicy).
- Strategiblad: Per strategi – syfte, indikatorer, parametrar, kända risker, backtest‑sammanfattning.

## Definition of Done
- Kod: Typad, lintad, testad med täckningskrav uppfyllt.
- Backtest: Reproducerbara resultat bifogade (versionerad data + konfig).
- Dokumentation: Uppdaterad README/runbook/strategiblad.
- Observability: Loggar och mätvärden på plats.
- Säkerhet: Hemligheter säkra; inga hårdkodade nycklar.

## PR‑checklista (kopiera i PR‑beskrivning)
- [ ] Lint/format/mypy OK
- [ ] Nya/ändrade tester
- [ ] Backtest/hyperopt artefakter bifogade (om strategi)
- [ ] Risk‑guardrails oförändrade eller dokumenterade
- [ ] Dokumentation uppdaterad
- [ ] Inga hemligheter i diff
- [ ] Miljövariabler/konfig beskrivna