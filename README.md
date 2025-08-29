# Tradingbot – Freqtrade-baserad

Detta repo innehåller en Freqtrade-baserad krypto-tradingbot med ett stort fokus på säkerhet, reproducerbarhet och tydlig struktur. Projektet är i **konsolideringsfas** med fokus på produktionsduglig grund, säkerhet och observability.

## Översikt

**För icke-tekniska användare:**

- Säker testmiljö med paper trading (simulerad handel) som standard
- Automatisk riskhantering med circuit breaker och guardrails
- Tydlig dokumentation och spårbarhet av alla resultat

**För tekniska användare:**

- Strukturerad JSON-loggning med korrelations-ID
- Decimal-precision för monetära värden
- Omfattande testsuite med CI/CD-pipeline
- Modulär arkitektur med separerad strategihantering

**Kortfattat:**

- Kör paper trading (simulerad handel) som standard via Docker Compose
- Bygg och testa strategier med backtesting och hyperopt
- Robust riskhantering och incidentloggning
- Gå till live först när backtester är stabila och risker är kända

## Förkrav
- **Docker Desktop** (Windows) - för containeriserad körning
- **Git** - för versionshantering
- **Python 3.10+** - för utveckling och skript
- **PowerShell** - rekommenderat för Windows-kommandon

## Setup

### 1. Miljövariabler
Kopiera `.env.example` till `.env`:
```bash
cp .env.example .env
```
- **Paper/backtest**: API-nycklar kan vara tomma
- **Live**: Krävs riktiga nycklar. **Lagra aldrig hemligheter i repo**

### 2. Konfiguration
Granska och justera konfigurationsfiler:
- `user_data/configs/config.testnet.json` - testnet/paper trading
- `user_data/configs/config.mainnet.json` - live trading (använd försiktigt)
- `user_data/configs/config.bt.json` - backtesting

### 3. Docker Compose
Bekräfta att `docker-compose.yml` pekar på testnet-konfig och `--dry-run` (paper mode).

### 4. Katalogstruktur
Projektet skapar automatiskt nödvändiga kataloger:
```
user_data/
├── strategies/          # Freqtrade strategier
├── configs/            # Konfigurationsfiler
├── backtest_results/   # Backtest-artefakter
├── hyperopt_results/   # Hyperopt-artefakter
├── registry/           # SQLite-databaser
├── state/              # Risk manager tillstånd
└── logs/               # Loggfiler
```

## Kommandon (Docker Compose)
- Dra image:
  ```bash
  docker compose pull
  ```
- Paper trading (default i compose):
  ```bash
  docker compose up
  ```
- Backtesting:
  ```bash
  docker compose run --rm freqtrade backtesting \
    -c /freqtrade/user_data/configs/config.testnet.json \
    --strategy MaCrossoverStrategy
  ```
- Hyperopt:
  ```bash
  docker compose run --rm freqtrade hyperopt \
    -c /freqtrade/user_data/configs/config.testnet.json \
    --strategy MaCrossoverStrategy \
    --spaces buy sell roi stoploss
  ```
- Live (kräver mainnet-konfig och real keys – gör detta sist och försiktigt):
  ```bash
  docker compose run --rm freqtrade trade \
    -c /freqtrade/user_data/configs/config.mainnet.json
  ```

## Överblick (icke-teknisk)
- Syfte: Bygga och testa automatiska handelsstrategier i en säker testmiljö (paper) innan eventuell live-handel.
- Risk: Kryptohandel har hög risk. Förluster kan överstiga insättning vid felaktig hävstång/derivat (används ej här). Kör alltid i testläge först.
- Säkerhet: Inga hemligheter i repo. `.env` hanterar nycklar lokalt. Live kräver separat mainnet-konfiguration.
- Transparens: Backtester genererar rapporter under `user_data/backtest_results/` som kan delas och reproduceras.

## Arkitektur (teknisk översikt)

### Container-arkitektur
- **Docker Compose** kör `freqtradeorg/freqtrade:stable`
- **Volym**: `./user_data` monteras till `/freqtrade/user_data`
- **Standardkommando**: `trade -c config.testnet.json --dry-run` (paper trading)

### Modulstruktur
```
app/
├── strategies/         # Strategihantering och risk
│   ├── risk.py        # RiskManager med circuit breaker
│   ├── metrics.py     # Resultatindexering
│   ├── reporting.py   # Rapportgenerering
│   ├── runner.py      # Körningsorkestrering
│   └── persistence/   # SQLite-hantering
├── adapters/          # Externa API-adapters
├── data_services/     # Datahantering
└── reasoning/         # AI/ML-modeller

scripts/
├── strategy_cli.py    # Huvudsakligt CLI-verktyg
├── circuit_breaker.py # Circuit breaker-hantering
├── backup_restore.py  # Backup/restore-funktioner
└── dca_scheduler.py   # DCA-planering

user_data/
├── strategies/        # Freqtrade-strategier
├── configs/          # Konfigurationsfiler
└── [resultat/logs]   # Artefakter och loggar
```

### Dataflöde
1. **Strategier** definieras i `user_data/strategies/`
2. **Körning** via Docker Compose eller CLI-skript
3. **Resultat** indexeras automatiskt till SQLite
4. **Rapporter** genereras från databas
5. **Risk** övervakas kontinuerligt med guardrails

## Konsolideringsfas (mot produktion)
Det pågår en konsolidering för att höja produktsäkerhet och spårbarhet:
- Strukturerad JSON-loggning med korrelations-ID i `app/strategies/` (runner, metrics, reporting).
- Pydantic-validering av artefakter (backtest/hyperopt) vid indexering.
- RiskManager‑guardrails (grund, utökas med drawdown/samtidighet/exponering).
- Regressions- och property‑baserade tester; CI-gates (ruff/black/isort/mypy/pytest/safety).
- Prometheus‑kompatibla mätvärden (plan) och DR‑rutiner med backup/restore.
- Default: testnet/paper; inga hemligheter i repo.

## CI och kvalitetsgrindar
- GitHub Actions workflow: `.github/workflows/ci.yml`
- Kör: `pytest`, `ruff`, `black --check`, `mypy app/`, `safety check`
- Krav: alla steg måste passera innan merge till `main`.

## Precision & incidentloggning
- Monetära värden hanteras med `decimal.Decimal` och kvantiseras till 8 decimaler i `app/strategies/metrics.py` och `reporting.py`.
- Rapporter visar monetära värden med 8 decimalers precision (se `tests/test_reporting.py`).
- Riskincidenter loggas via `RiskManager.log_incident()` till SQLite‑tabellen `incidents` och till strukturerad JSON‑logg.

## Var hamnar resultat?
- Backtest: `user_data/backtest_results/` (JSON och ZIP-rapporter, t.ex. `.meta.json`, `.zip`).
- Hyperopt: `user_data/hyperopt_results/` (fthypt-filer).
- Loggar: `user_data/logs/freqtrade.log` (konfigureras i `docker-compose.yml`).
- Plot/rapporter (om aktiverat): `user_data/plot/` och `user_data/reports/`.

## Vanliga justeringar

### Handelsparametrar
- **Timeframe/par**: Ändra i `config.*.json` (ex. `"timeframe": "5m"`, `"pair_whitelist"`)
- **Risk**: Justera `minimal_roi`, `stoploss`, trailing stop i strategier
- **Strategi**: Byt via konfig (`"strategy": "MaCrossoverStrategy"`)

### Notifieringar
- **Telegram**: Aktivera i konfig (`"telegram": {"enabled": true}`)
- **Webhook**: Konfigurera för externa system

### Riskhantering
- **Circuit Breaker**: `py -3 scripts/circuit_breaker.py enable --reason "maintenance"`
- **Miljövariabler**: Se [Miljövariabler](#miljövariabler) för fullständig lista
- **Guardrails**: Konfigurera via `RISK_*` environment variables

## Säkerhet
- Använd testnet/paper tills backtest/paper är stabilt.
- Lagra aldrig hemligheter i repo. Använd `.env` lokalt och CI-secrets i pipelines.
- Sätt begränsningar: `max_open_trades`, protections (`MaxDrawdown`, `StoplossGuard`) i konfig.
- Kör med låga belopp initialt i live, och övervaka loggar/telegram-notiser.

## Felsökning (snabbguide)
- Containern startar inte: Kontrollera Docker Desktop, och att port/volym inte är låst.
- Får inte igenom order i paper: Se `freqtrade.log` och bekräfta att `--dry-run` är aktivt samt par finns i `pair_whitelist`.
- Backtest saknar data: Ladda ner historik via Freqtrade-kommandon eller kör om med annan period.
- Strategi importfel: Stava klassnamn korrekt i konfig (ex. `"MaCrossoverStrategy"`).

## FAQ
- Behöver jag API-nycklar för paper/backtest?
 - Nej. Lämna dem tomma i `.env` för test/paper. Krävs endast för live.
- Kan jag köra utan Docker?
 - Ja, men detta repo är optimerat för Docker. Följ Freqtrade-installationsguide om du vill köra lokalt.
- Var konfigurerar jag riskguardrails?
 - I konfig (`protections`) samt i strategi (ROI/stoploss/trailing). Se `user_data/configs/config.*.json` och `user_data/strategies/*.py`.

## Vidare läsning
- Riktlinjer och utvecklingsstandard: `docs/CODE_GUIDELINES.md`
- Operativ körning & incidenter: `docs/RUNBOOK.md`
- Roadmap och konsolideringsplan: `docs/ROADMAP.md`
- Strategiregister och strategiöversikt: `docs/STRATEGIES.md`
- Script och verktyg: `scripts/README.md`

### Backup/Restore (artefakter och SQLite‑register)
- Skapa backup: `py -3 scripts/backup_restore.py backup`
- Återställ: `py -3 scripts/backup_restore.py restore <sökväg_till_backup>`
- Arkiverar/återställer: `user_data/backtest_results/`, `user_data/hyperopt_results/`, `user_data/registry/*.sqlite`, (valfritt) `user_data/logs/`.

## Miljövariabler

### Risk Management
```bash
# Circuit Breaker
RISK_CIRCUIT_BREAKER_FILE=user_data/state/circuit_breaker.json
RISK_ALLOW_WHEN_CB=0  # 1 för att tillåta körning trots CB

# Concurrency
RISK_MAX_CONCURRENT_BACKTESTS=2
RISK_CONCURRENCY_TTL_SEC=900

# Drawdown Protection
RISK_MAX_BACKTEST_DRAWDOWN_PCT=0.20  # 20%

# Live Trading Limits
RISK_LIVE_MAX_CONCURRENT_TRADES=5
RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT=0.25  # 25%

# Database
RISK_DB_PATH=user_data/registry/strategies_registry.sqlite
RISK_STATE_DIR=user_data/state
```

### Logging
```bash
# Strukturerad JSON-loggning aktiveras automatiskt
# Korrelations-ID propageras genom alla operationer
```

## CLI-verktyg

### Strategy CLI (Huvudverktyg)
```powershell
# Generera dokumentation
py -3 scripts/strategy_cli.py docs

# Indexera resultat
py -3 scripts/strategy_cli.py index-backtests
py -3 scripts/strategy_cli.py index-hyperopts

# Generera rapport
py -3 scripts/strategy_cli.py report-results

# Exportera register till SQLite
py -3 scripts/strategy_cli.py export-db
```

### Circuit Breaker
```powershell
# Status
py -3 scripts/circuit_breaker.py status

# Aktivera (60 minuter)
py -3 scripts/circuit_breaker.py enable --reason "incident-123" --minutes 60

# Avaktivera
py -3 scripts/circuit_breaker.py disable
```

### Backup/Restore
```powershell
# Skapa backup
py -3 scripts/backup_restore.py backup --logs

# Återställ
py -3 scripts/backup_restore.py restore user_data\backups\backup_20250829_173000
```
