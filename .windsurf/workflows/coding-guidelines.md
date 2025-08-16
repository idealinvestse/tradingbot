---
description: 
auto_execution_mode: 3
---

Coding Guidelines – Tradingbot-projekt
Följ denna standard för all kod i projektet. Den är optimerad för en Python-baserad krypto-tradingbot (t.ex. Freqtrade) på Windows med fokus på backtest, paper trading och säker live-handel. Kontext hämtad från 
strategy.json
 (strategier som DCA, MA-crossover, Swing etc.).

Principer
Säkerhet först: Inga hemligheter i repo. Testnet före Mainnet. Guardrails i kod och CI.
Reproducerbarhet: Deterministiska backtester, frysta beroenden, versionsspårad data/konfig.
Enkelhet före smarthet: Läsbar, testbar, liten komplexitet. Feature-flaggor för experiment.
Fail fast + tydliga loggar: Snabba, tydliga fel. Strukturerad loggning och mätvärden.
Projekt­struktur (förslag)
app/ – kärnlogik, adapters (börser, data), risk, utils
strategies/ – Freqtrade-strategier (MA-crossover, DCA m.fl.)
configs/ – config.testnet.json, config.mainnet.json, schema/validering
tests/ – unit, integration, backtest-regression
data/ – historik (read-only), cache
scripts/ – verktyg (download-data, hyperopt, rapport)
docs/ – setup, runbooks, ADRs
infra/ – Dockerfile, docker-compose, CI/CD
Python-stil och typer
Formatter/lint: Black, Ruff, isort. MyPy (strict för app/ och strategies/).
PEP8 + typer: All ny kod typannoteras. Publika API:er har docstrings (Google/Numpy-stil).
Namngivning: snake_case för funktioner/variabler, PascalCase för klasser, UPPER_CASE för konstanter.
Imports: Standardlib, tredjeparts, lokala – i den ordningen, separerade block.
Felhantering: Fånga specifika undantag, lägg till kontext, logga strukturerat, återkasta vid behov.
Konfiguration och hemligheter
Pydantic BaseSettings för konfigvalidering; schema i kod.
.env (lokalt), miljövariabler i CI. Aldrig API-nycklar i repo.
Miljöer: testnet default lokalt. Explicit switch krävs till mainnet.
Feature flags: Sätt via env/konfig för att aktivera/avaktivera strategier/funktioner.
Numerisk korrekthet (kritisk)
Decimal för pengar: Använd decimal.Decimal med rätt precision/quantize. Undvik float för belopp/avgifter.
Tidsserier: Numpy/Pandas för vectoriserade beräkningar. Kontrollera NaN/inf.
Rundning: Centralisera rundningsregler per marknad/ticksize.
Tid, zoner och data
Timezone: All intern tid i UTC. Konvertera vid in/ut.
Klockor: Använd serverns tid eller exchange server time; skydda mot drift.
Datakvalitet: Validera OHLCV (luckor, duplikat), lagra källmetadata och version.
Strategi­standard (Freqtrade)
Struktur:
populate_indicators() – endast indikatorberäkning, inga side effects.
populate_entry_trend() / populate_exit_trend() – enbart signaler, inga externa anrop.
Parametrar som IntParameter, DecimalParameter för hyperopt.
Prestanda: Vectorisera; inga per-rad Python-loopar vid indikatorer.
Dokumentera: Hypotes, marknader, timeframe, indikatorer, riskantaganden.
Backtest­determinism: Lås random seeds, versionera datafönster, logga konfig i rapport.
Risk- och orderhantering
Globala guardrails: Max daglig drawdown, max samtidiga trades, per-marknadsexponering.
Orderpolicy: Tidsgränser, idempotens (clientOrderId), retry med backoff, hantera rate limits.
Stop/TP: Alltid definierade, med glidning och partial fills hanterade.
Fel­tolerans och robusthet
Timeout + backoff: Alla I/O med timeout, exponential backoff, jitter.
Circuit breaker: Pausa handel på upprepade fel/avvikelser.
Atomiska steg: Bryt ner sekvenser; återskapa från säkra checkpoints.
Loggning och observability
Strukturerade loggar (JSON) med korrelations-ID.
Nivåer: INFO för flöde, DEBUG vid utveckling, WARN/ERROR vid incidenter.
Mätvärden: Latens, orders lyckade/misslyckade, PnL, drawdown, slippage. Exportera Prometheus om möjligt.
Spårbarhet: Logga konfig-hash, datafönster, versionsinfo i backtestrapporter.
Testpolicy
Unit tests: 80%+ i app/ och kritiska utils. Pytest.
Property-based (Hypothesis) för indikatorer/signaler.
Integration: Sandbox/Testnet mot börs-API, rate-limit mocks.
Backtest-regression: Golden-master på PnL/Sharpe/trade count per strategi.
Contract tests: Mot externa adapters (utbytes-API, datakälla).
CI-gates: Blockera merge om tester/lint failar.
Prestanda och resurser
Profileringsregim: Kör profiler vid större ändringar.
Cache: OHLCV-cache per market/timeframe med invalidation på ny data.
Parallellism: Multiprocess för backtests; undvik GIL-hotspots i heta slingor.
Samtidighet
I/O-tyngt: asyncio eller välkapslad trådpool. Blockera inte event loop.
Avslut: Graceful shutdown; cancel tasks, flush loggar, stäng sessions.
Trådsäkerhet: Delade objekt skyddas; inga globala mutabla tillstånd i strategier.
Beroenden och build
Verktyg: Poetry eller pip-tools. Lås versionsfil (poetry.lock/requirements.txt fryst).
Pythonversion: 3.11+.
Säker kedja: Hash-checks, skanna beroenden i CI (t.ex. Safety).
Containers och drift
Docker: Multi-stage build, non-root, healthcheck. Inga hemligheter i image.
Compose: Volymer för data/ och configs/. En tjänst per process.
Windows: Testa lokalt (Docker Desktop), dokumentera paths/line endings.
Git-flöde och code review
Branching: Trunk-based med kortlivade feature branches eller GitFlow om ni föredrar release-grenar.
Conventional Commits: feat:, fix:, docs:, refactor:, etc.
PR-krav: 1+ godkännande, gröna CI-checks, ingen ny debt utan TODO/issue.
Code owners: Kritiskt område kräver extra review (risk/ordermotor/strategi).
Dokumentation
README för snabbstart (testnet).
Runbooks: Incidenter, rollback, nyckelrotation, checklistor inför live.
ADRs för större beslut (dataschema, ordermotor, riskpolicy).
Strategi­blad: För varje strategi – syfte, indikatorer, parametrar, kända risker, backtest-sammanfattning.
Definition of Done
Kod: Typad, lintad, testad med täckningskrav uppfyllt.
Backtest: Reproducerbara resultat bifogade (versionerad data + konfig).
Dokumentation: Uppdaterad README/runbook/strategiblad.
Observability: Loggar och mätvärden på plats.
Säkerhet: Hemligheter säkra; inga hårdkodade nycklar.
PR-checklista (kopiera i PR-beskrivning)
 Lint/format/mypy ok
 Nya/ändrade tester
 Backtest-artefakter bifogade (om strategi)
 Risk-guardrails oförändrade eller dokumenterade
 Dokumentation uppdaterad
 Inga hemligheter i diff
 Miljövariabler/konfig beskrivna