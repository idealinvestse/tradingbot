# Tradingbot – Freqtrade-baserad

Detta repo innehåller en Freqtrade-baserad krypto-tradingbot med ett stort fokus på säkerhet, reproducerbarhet och tydlig struktur. Dokumentationen är avsedd både för icke-tekniska läsare (för att förstå syfte, risker och hur man kör i testläge) och tekniska användare (för att bygga, testa och köra strategier i Docker).

Kortfattat:
- Kör paper trading (simulerad handel) som standard via Docker Compose.
- Bygg och testa strategier med backtesting och hyperopt.
- Gå till live först när backtester är stabila och risker är kända.

## Förkrav
- Docker Desktop (Windows)
- Git

## Setup
1. Kopiera `.env.example` till `.env`.
   - För paper/backtest kan API-nycklar vara tomma.
   - För live krävs riktiga nycklar. Lagra aldrig hemligheter i repo.
2. Granska `user_data/configs/config.testnet.json` (par, timeframe, riskparametrar) och justera vid behov.
3. Bekräfta att `docker-compose.yml` pekar på testnet-konfig och `--dry-run` (paper).

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
- Docker Compose kör en container av `freqtradeorg/freqtrade:stable` enligt `docker-compose.yml`.
- Volym: `./user_data` monteras till `/freqtrade/user_data` i containern.
- Standardkommando: `trade -c ...config.testnet.json --dry-run` för paper trading.
- Strategier ligger i `user_data/strategies/` (ex. `ma_crossover_strategy.py`, `mean_reversion_bb.py`).
- Konfigfiler i `user_data/configs/` (testnet/mainnet/backtest).

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
- Ändra timeframe/par i `config.*.json` (ex. `timeframe: "5m"`, `pair_whitelist`).
- Finjustera risk i strategi (t.ex. `minimal_roi`, `stoploss`, trailing stop) samt hyperoptbara parametrar.
- Aktivera Telegram i konfig för notifieringar (`telegram.enabled=true`).
- Byt strategi via konfig (`"strategy": "MaCrossoverStrategy"`).

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

## Träd
```
user_data/
  strategies/
  configs/
  data/
  logs/
  reports/
