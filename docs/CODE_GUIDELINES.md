# Coding Guidelines – Tradingbot-projekt

Följ denna standard för all kod i projektet. Den är optimerad för en Python-baserad krypto-tradingbot (t.ex. Freqtrade) på Windows med fokus på backtest, paper trading och säker live-handel. Kontext hämtad från `strategy.json` (strategier som DCA, MA-crossover, Swing etc.).

## Sammanfattning för icke-tekniska läsare

- Syfte: Säker, reproducerbar utveckling av automatiserade handelsstrategier.
- Säkerhet: Inga hemligheter i repo. Testnet/paper först. Live endast efter tydliga backtester.
- Spårbarhet: Resultat och konfiguration versioneras och kan återskapas.
- Kvalitet: Kod ska vara läsbar, testad och typad. Fel ska synas snabbt via loggar och tester.
- Roller: Utvecklare följer denna guide, granskare säkerställer efterlevnad innan ändringar går in.

## Principer

- __Säkerhet först__: Inga hemligheter i repo. Testnet före Mainnet. Guardrails i kod och CI.
- __Reproducerbarhet__: Deterministiska backtester, frysta beroenden, versionsspårad data/konfig.
- __Enkelhet före smarthet__: Läsbar, testbar, liten komplexitet. Feature-flaggor för experiment.
- __Fail fast + tydliga loggar__: Snabba, tydliga fel. Strukturerad loggning och mätvärden.

## Projekt­struktur (förslag)

- `user_data/` – Freqtrade-kompatibelt träd (strategies/, configs/, data/, reports/)
- `tests/` – unit, integration, backtest-regression
- `scripts/` – verktyg (download-data, hyperopt, rapport)
- `docs/` – setup, runbooks, ADRs
- `infra/` – Dockerfile, docker-compose, CI/CD

## Python-stil och typer

- __Formatter/lint__: Black, Ruff, isort. MyPy (strict för strategier och kritiska utils).
- __PEP8 + typer__: All ny kod typannoteras. Publika API:er har docstrings (Google/Numpy-stil).
- __Namngivning__: `snake_case` för funktioner/variabler, `PascalCase` för klasser, `UPPER_CASE` för konstanter.
- __Imports__: Standardlib, tredjeparts, lokala – i den ordningen, separerade block.
- __Felhantering__: Fånga specifika undantag, lägg till kontext, logga strukturerat, återkasta vid behov.

## Konfiguration och hemligheter

- __Pydantic BaseSettings__ för konfigvalidering; schema i kod där det är rimligt.
- __.env__ (lokalt), miljövariabler i CI. __Aldrig__ API-nycklar i repo.
- __Miljöer__: `testnet` default lokalt. Explicit switch krävs till `mainnet`.
- __Feature flags__: Sätt via env/konfig för att aktivera/avaktivera strategier/funktioner.

## Numerisk korrekthet (kritisk)

- __Decimal för pengar__: Använd `decimal.Decimal` med rätt precision/`quantize`. Undvik float för belopp/avgifter.
- __Tidsserier__: Numpy/Pandas för vectoriserade beräkningar. Kontrollera NaN/inf.
- __Rundning__: Centralisera rundningsregler per marknad/ticksize.

## Tid, zoner och data

- __Timezone__: All intern tid i UTC. Konvertera vid in/ut.
- __Klockor__: Använd serverns tid eller exchange server time; skydda mot drift.
- __Datakvalitet__: Validera OHLCV (luckor, duplikat), lagra källmetadata och version.

## Strategi­standard (Freqtrade)

- __Struktur__:
  - `populate_indicators()` – endast indikatorberäkning, inga side effects.
  - `populate_entry_trend()` / `populate_exit_trend()` – enbart signaler, inga externa anrop.
  - Parametrar som `IntParameter`, `DecimalParameter` för hyperopt.
- __Prestanda__: Vectorisera; inga per-rad Python-loopar vid indikatorer.
- __Dokumentera__: Hypotes, marknader, timeframe, indikatorer, riskantaganden.
- __Backtest­determinism__: Lås random seeds, versionera datafönster, logga konfig i rapport.

## Risk- och orderhantering

- __Globala guardrails__: Max daglig drawdown, max samtidiga trades, per-marknadsexponering.
- __Orderpolicy__: Tidsgränser, idempotens (clientOrderId), retry med backoff, hantera rate limits.
- __Stop/TP__: Alltid definierade, med glidning och partial fills hanterade.

## Fel­tolerans och robusthet

- __Timeout + backoff__: Alla I/O med timeout, exponential backoff, jitter.
- __Circuit breaker__: Pausa handel på upprepade fel/avvikelser.
- __Atomiska steg__: Bryt ner sekvenser; återskapa från säkra checkpoints.

## Loggning och observability

- __Strukturerade loggar__ (JSON) med korrelations-ID.
- __Nivåer__: INFO för flöde, DEBUG vid utveckling, WARN/ERROR vid incidenter.
- __Mätvärden__: Latens, orders lyckade/misslyckade, PnL, drawdown, slippage. Exportera Prometheus om möjligt.
- __Spårbarhet__: Logga konfig-hash, datafönster, versionsinfo i backtestrapporter.

## Testpolicy

- __Unit tests__: 80%+ i strategier/kritiska utils. Pytest.
- __Property-based__ (Hypothesis) för indikatorer/signaler.
- __Integration__: Sandbox/Testnet mot börs-API, rate-limit mocks.
- __Backtest-regression__: Golden-master på PnL/Sharpe/trade count per strategi.
- __Contract tests__: Mot externa adapters (utbytes-API, datakälla).
- __CI-gates__: Blockera merge om tester/lint failar.

## Prestanda och resurser

- __Profileringsregim__: Kör profiler vid större ändringar.
- __Cache__: OHLCV-cache per market/timeframe med invalidation på ny data.
- __Parallellism__: Multiprocess för backtests; undvik GIL-hotspots i heta slingor.

## Samtidighet

- __I/O-tyngt__: `asyncio` eller välkapslad trådpool. Blockera inte event loop.
- __Avslut__: Graceful shutdown; cancel tasks, flush loggar, stäng sessions.
- __Trådsäkerhet__: Delade objekt skyddas; inga globala mutabla tillstånd i strategier.

## Beroenden och build

- __Verktyg__: Poetry eller pip-tools. Lås versionsfil (`poetry.lock`/`requirements.txt` fryst).
- __Pythonversion__: 3.11+.
- __Säker kedja__: Hash-checks, skanna beroenden i CI (t.ex. Safety).

## Containers och drift

- __Docker__: Multi-stage build, non-root, healthcheck. Inga hemligheter i image.
- __Compose__: Volymer för `user_data/`. En tjänst per process.
- __Windows__: Testa lokalt (Docker Desktop), dokumentera paths/line endings.

## Git-flöde och code review

- __Branching__: Trunk-based med kortlivade feature branches eller GitFlow om ni föredrar release-grenar.
- __Conventional Commits__: `feat:`, `fix:`, `docs:`, `refactor:`, etc.
- __PR-krav__: 1+ godkännande, gröna CI-checks, ingen ny debt utan TODO/issue.
- __Code owners__: Kritiskt område kräver extra review (risk/ordermotor/strategi).

## Dokumentation

- __README__ för snabbstart (testnet).
- __Runbooks__: Incidenter, rollback, nyckelrotation, checklistor inför live.
- __ADRs__ för större beslut (dataschema, ordermotor, riskpolicy).
- __Strategi­blad__: För varje strategi – syfte, indikatorer, parametrar, kända risker, backtest-sammanfattning.

## Definition of Done

- __Kod__: Typad, lintad, testad med täckningskrav uppfyllt.
- __Backtest__: Reproducerbara resultat bifogade (versionerad data + konfig).
- __Dokumentation__: Uppdaterad README/runbook/strategiblad.
- __Observability__: Loggar och mätvärden på plats.
- __Säkerhet__: Hemligheter säkra; inga hårdkodade nycklar.

## PR-checklista (kopiera i PR-beskrivning)

- [ ] Lint/format/mypy ok
- [ ] Nya/ändrade tester
- [ ] Backtest-artefakter bifogade (om strategi)
- [ ] Risk-guardrails oförändrade eller dokumenterade
- [ ] Dokumentation uppdaterad
- [ ] Inga hemligheter i diff
- [ ] Miljövariabler/konfig beskrivna

## Pre-commit (rekommenderat)

- __Hooks__: black, ruff, isort, mypy, trailing-whitespace, end-of-file-fixer, nbstripout (för notebooks).
- __Policy__: Hooks måste passera innan commit.
