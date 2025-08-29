# Arkitektur – Tradingbot

Senast uppdaterad (UTC): 2025-08-29T15:33:09Z

## Översikt

Tradingbot-projektet är strukturerat som en modulär applikation med tydlig separation mellan olika ansvarsområden. Arkitekturen följer principerna för säkerhet, reproducerbarhet och observability.

## Huvudkomponenter

### Container-arkitektur

```
Docker Compose
├── freqtradeorg/freqtrade:stable (huvudcontainer)
├── Volume: ./user_data -> /freqtrade/user_data
└── Standardkommando: trade -c config.testnet.json --dry-run
```

### Modulstruktur

#### app/ - Kärnlogik

```markdown
app/
├── strategies/         # Strategihantering och risk
│   ├── risk.py        # RiskManager med circuit breaker
│   ├── metrics.py     # Resultatindexering och parsning
│   ├── reporting.py   # Rapportgenerering
│   ├── runner.py      # Körningsorkestrering
│   ├── logging_utils.py # Strukturerad JSON-loggning
│   ├── registry.py    # Strategiregister
│   ├── introspect.py  # Strategiintrospektion
│   └── persistence/   # SQLite-hantering
│       └── sqlite.py
├── adapters/          # Externa API-adapters
│   ├── news/         # Nyhetsadapters
│   ├── onchain/      # Blockchain-data
│   └── sentiment/    # Sentimentanalys
├── data_services/     # Datahantering
│   ├── models.py     # Datamodeller
│   ├── news_fetcher.py
│   └── sentiment_analyzer.py
├── reasoning/         # AI/ML-modeller
│   ├── models.py     # Basmodeller
│   ├── rule_based_model.py
│   └── ml_model.py
├── analysis/          # Analysverktyg
├── arbitrage/         # Arbitragestrategier
├── cache/            # Cachingmekanismer
├── events/           # Händelsehantering
├── execution/        # Orderexekvering
├── metrics/          # Prometheus-metrics
├── ml/               # Machine Learning
├── monitoring.py     # Övervakning
└── optimization/     # Optimeringsalgoritmer
```

#### scripts/ - CLI-verktytg

```
scripts/
├── strategy_cli.py    # Huvudsakligt CLI-verktyg
├── circuit_breaker.py # Circuit breaker-hantering
├── backup_restore.py  # Backup/restore-funktioner
├── dca_scheduler.py   # DCA-planering
├── run_live.py       # Live trading med guardrails
└── ai_strategy_runner.py # AI-strategikörning
```

#### user_data/ - Freqtrade-data

```
user_data/
├── strategies/        # Freqtrade-strategier (.py)
├── configs/          # Konfigurationsfiler (.json)
├── backtest_results/ # Backtest-artefakter (.meta.json, .zip)
├── hyperopt_results/ # Hyperopt-artefakter (.fthypt)
├── registry/         # SQLite-databaser
├── state/           # Risk manager tillstånd
├── logs/            # Loggfiler
└── data/            # Marknadsdata (Freqtrade)
```

## Dataflöde

### 1. Strategiutveckling

```
Utvecklare → user_data/strategies/ → Freqtrade-klasser
    ↓
scripts/strategy_cli.py introspect → docs/strategies_registry.json
    ↓
scripts/strategy_cli.py docs → docs/STRATEGIES.md
```

### 2. Backtesting

```
Docker Compose → Freqtrade backtest → user_data/backtest_results/
    ↓
scripts/strategy_cli.py index-backtests → SQLite
    ↓
scripts/strategy_cli.py report-results → docs/RESULTS.md
```

### 3. Risk Management

```
app/strategies/risk.py → RiskManager
    ├── Circuit Breaker → user_data/state/circuit_breaker.json
    ├── Concurrency Locks → user_data/state/running/*.lock
    ├── Incident Logging → SQLite incidents-tabell
    └── Live Guardrails → Kontextuell validering
```

### 4. Observability

```
app/strategies/logging_utils.py → Strukturerad JSON-loggning
    ├── Korrelations-ID → Propageras genom alla operationer
    ├── Metrics → app/strategies/metrics.py
    └── Rapporter → app/strategies/reporting.py
```

## Säkerhetsarkitektur

### Miljöseparation
- **Testnet/Paper**: Standard för utveckling och testning
- **Mainnet/Live**: Explicit aktivering med separata konfigurationer
- **Hemligheter**: Aldrig i repo, endast via `.env` eller CI-secrets

### Risk Guardrails
- **Circuit Breaker**: Automatisk avstängning vid incidenter
- **Concurrency Limits**: Begränsar samtidiga körningar
- **Drawdown Protection**: Stoppar vid för stora förluster
- **Live Limits**: Begränsar exponering och antal trades

### Validering
- **Pydantic**: Datavalidering för alla artefakter
- **Type Checking**: MyPy strict för `app/` moduler
- **Decimal Precision**: 8 decimaler för monetära värden

## Observability-arkitektur

### Loggning

```
JSON-strukturerad loggning
├── Korrelations-ID (propageras)
├── Kontextfält (run_id, strategy, etc.)
├── Severity-nivåer (INFO, WARN, ERROR, CRITICAL)
└── Incident-koppling till SQLite
```

### Metrics

```
app/strategies/metrics.py
├── Backtest-parsning → SQLite
├── Hyperopt-parsning → SQLite
├── Performance-metrics
└── Fel-räknare
```

### Rapportering

```
app/strategies/reporting.py
├── Markdown-generering
├── 8-decimals precision
├── Data Window-spårning
└── Config Hash-validering
```

## Databas-arkitektur

### SQLite-schema

```sql
-- Strategiregister
strategies, methods, concepts, sources

-- Körningsdata
runs (id, experiment_id, kind, status, data_window)
metrics (run_id, key, value)
artifacts (run_id, name, path, sha256)

-- Incidenthantering
incidents (id, run_id, severity, description, created_utc)

-- Experimenthantering (framtida)
ideas, experiments, decisions
```

## CI/CD-arkitektur

### GitHub Actions Pipeline

```yaml
.github/workflows/ci.yml
├── Python 3.10 & 3.11 testing
├── pytest (enhetstester)
├── ruff (linting)
├── black --check (formatering)
├── mypy (typkontroll)
└── safety (säkerhetskontroll)
```

### Kvalitetsgrindar
- Alla tester måste passera
- 100% typkontroll för `app/` moduler
- Inga säkerhetsbrister i beroenden
- Kodformatering enligt Black-standard

## Deployment-arkitektur

### Lokal utveckling

```
Windows + Docker Desktop
├── PowerShell för CLI-kommandon
├── Python 3.10+ för utveckling
└── .env för lokala hemligheter
```

### Produktionsmiljö (planerad)

```
Ubuntu Server
├── AMD ROCm GPU-stöd
├── Docker Compose för orkestrering
├── Prometheus + Grafana för monitoring
└── Automatisk backup/restore
```

## Utbyggnadsarkitektur

### Nästa fas - Observability
- Prometheus metrics export
- Grafana dashboards
- Alerting på kritiska events
- Distributed tracing

### Nästa fas - AI/ML
- Feature engineering pipeline
- Model training automation
- A/B testing framework
- Regime detection

### Nästa fas - Multi-exchange
- Exchange adapters
- Arbitrage detection
- Cross-exchange risk management
- Unified order routing

## Designprinciper

### Säkerhet först
- Testnet som standard
- Explicit aktivering för live
- Guardrails på alla nivåer
- Incident-driven förbättringar

### Reproducerbarhet
- Deterministiska backtester
- Versionerad data och konfiguration
- Checksums för artefakter
- Fullständig spårbarhet

### Observability
- Strukturerad loggning överallt
- Metrics för alla kritiska operationer
- Automatisk rapportgenerering
- Incident-koppling

### Moduläritet
- Tydlig separation av ansvar
- Pluggbar arkitektur
- Testbar kod
- Återanvändbara komponenter
