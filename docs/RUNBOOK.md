# Runbook – Tradingbot

Denna runbook beskriver hur du kör boten i paper (test), gör backtests och hyperopt, förbereder live, var du hittar loggar/artifakter samt hur du agerar vid incidenter. Alla kommandon utgår från att du kör Windows med Docker Desktop och detta repo klonat lokalt.

## 1. Paper trading (standardläge)
Paper = simulerad handel, säkert läge för att validera flöden.

1) Dra/uppdatera image
```bash
docker compose pull
```

2) Starta paper (foreground – visar loggström)
```bash
docker compose up
```

3) Stoppa
```bash
docker compose down
```

Konfiguration: `docker-compose.yml` startar `freqtrade` med `--dry-run` och `config.testnet.json`.
Loggar: `user_data/logs/freqtrade.log` (se även konsolutskrift).

## 2. Backtesting
Kör historiska tester för att utvärdera en strategi.

Exempel (MaCrossoverStrategy):
```bash
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/configs/config.testnet.json \
  --strategy MaCrossoverStrategy
```

Tips:
- Ange tidsintervall och datasource via Freqtrade-flaggor vid behov (se Freqtrade docs).
- Se till att `timeframe` och par finns i konfig (`pair_whitelist`).

Artefakter:
- Resultat lagras i `user_data/backtest_results/` (t.ex. `.meta.json`, `.zip`).

## 3. Hyperopt
Söker parametrar som förbättrar strategiutfall. Kräver tid och tydlig avgränsning.

Exempel:
```bash
docker compose run --rm freqtrade hyperopt \
  -c /freqtrade/user_data/configs/config.testnet.json \
  --strategy MaCrossoverStrategy \
  --spaces buy sell roi stoploss
```

Artefakter:
- `user_data/hyperopt_results/` (`.fthypt`).

## 4. Live – förberedelser och start
Gör detta sist, efter stabila backtester och paper-resultat.

Checklista före live:
- [ ] Uppdatera `user_data/configs/config.mainnet.json` (par, risk, protections).
- [ ] Sätt riktiga API-nycklar i `.env` (lämna aldrig nycklar i repo).
- [ ] Sänk exponering initialt (`max_open_trades`, stake-regler).
- [ ] Aktivera notifieringar (t.ex. Telegram) och övervaka första timmarna.

Starta live:
```bash
docker compose run --rm freqtrade trade \
  -c /freqtrade/user_data/configs/config.mainnet.json
```

Stoppa live:
```bash
docker compose down
```

## 5. Loggar och artefakter
- Loggfil: `user_data/logs/freqtrade.log`
- Backtest: `user_data/backtest_results/`
- Hyperopt: `user_data/hyperopt_results/`
- Strategier: `user_data/strategies/`

## 6. Vanliga problem och åtgärder
- Boten startar inte: Kontrollera Docker Desktop och att volymen `./user_data` finns.
- Får inga trades i paper: Verifiera `pair_whitelist`, `timeframe`, och att strategins signaler faktiskt triggas.
- Backtests utan data: Ladda ner historik eller justera period/timeframe.

## 7. Incidenthantering
Mål: Minimera risk, återgå till säkert läge, dokumentera.

Akut steg:
1) Stoppa körning
```bash
docker compose down
```
2) Växla till paper/testnet igen och verifiera beteende innan ev. återstart av live.
3) Dokumentera incidenten i `docs/` (symptom, tid, påverkan, loggutdrag, rotorsak, åtgärd).
4) Om oväntade förluster: granska `protections` och strategi-params; strama åt risk.

### Automatisk incidentloggning
När riskincidenter inträffar loggas de automatiskt till databasen (`user_data/registry/strategies_registry.sqlite`) i tabellen `incidents`. Dessa loggar innehåller:
- Unikt incident-ID
- Körnings-ID (om tillgängligt)
- Allvarlighetsgrad (t.ex. "warning", "error")
- Beskrivning av incidenten
- Sökväg till loggutdrag (om tillgängligt)
- Tidsstämpel

För att visa de senaste incidenterna:
```sql
SELECT * FROM incidents ORDER BY created_utc DESC LIMIT 10;
```

### Loggnivåpolicy och JSON‑exempel
Loggar skrivs i JSON via `app/strategies/logging_utils.py` och kan innehålla kontextfält som `correlation_id` och `run_id`.
- INFO: normal flödesinformation (t.ex. start/stopp, slot_acquired).
- WARNING: avvikelse som inte stoppar körning (t.ex. `max_dd_block`).
- ERROR: fel som kräver åtgärd (t.ex. parsning/persistens fel), fortsätt försiktigt.
- CRITICAL: allvarligt fel; överväg att aktivera circuit breaker.

Exempel (incident):
```json
{
  "ts": "2025-08-25T00:00:00+00:00",
  "level": "WARNING",
  "logger": "risk",
  "message": "incident_logged",
  "correlation_id": "abc123",
  "incident_id": "incident_1692921600_12345_abc123",
  "run_id": "run_bt_2025-08-25",
  "severity": "warning",
  "description": "max drawdown threshold exceeded",
  "log_excerpt_path": "user_data/logs/freqtrade.log"
}
```

Exempel (slot):
```json
{
  "ts": "2025-08-25T00:00:00+00:00",
  "level": "INFO",
  "logger": "risk",
  "message": "slot_acquired",
  "correlation_id": "abc123",
  "kind": "backtest",
  "active_before": 1,
  "lock": "user_data/state/running/backtest_1692921600_12345_abc123.lock"
}
```

## 8. Vidare läsning
- Översikt, FAQ och exempel: `README.md`
- Kodstandard och utvecklingspolicy: `docs/CODE_GUIDELINES.md`
- Strategiregister och strategiöversikt: `docs/STRATEGIES.md`
- Scripts och DCA-planer: `scripts/README.md`

## 9. CI/CD och kvalitetsgrindar
Projektet använder GitHub Actions för kontinuerlig integration med automatiska kvalitetskontroller:

- Testning: `pytest` körs mot Python 3.10 och 3.11
- Kodkvalitet: `ruff` för linting
- Kodformatering: `black` för formatering
- Typkontroll: `mypy` för statisk typkontroll
- Säkerhet: `safety` för att upptäcka sårbarheter i beroenden

Workflow-filen finns i `.github/workflows/ci.yml`. Alla kvalitetsgrindar måste passeras innan kod kan merge:as till `main`-branchen.

## 9. Disaster Recovery (DR) – Backup/Restore
Syfte: Snabb återställning av artefakter och registry.

- Skapa backup (default till `user_data/backups/`):
  ```powershell
  py -3 scripts/backup_restore.py backup
  ```
  Flaggar:
  - `--logs` inkluderar zippade loggar.
  - `--out <dir>` anger alternativ backupplats.

- Återställ från backup:
  ```powershell
  py -3 scripts/backup_restore.py restore user_data\backups\backup_YYYYmmdd_HHMMSS
  ```
  Delmängd:
  - `--only registry|backtests|hyperopts|logs` (kan upprepas)
  - `--overwrite` skriver över befintliga filer.

- Innehåll:
  - `user_data/registry/strategies_registry.sqlite`
  - `user_data/backtest_results/` (zip)
  - `user_data/hyperopt_results/` (zip)
  - `user_data/logs/` (valfritt zip)

- Rekommenderad rutin:
  1) Stoppa körning (`docker compose down`).
  2) Ta backup innan större ändringar.
  3) Testa återställning i isolerad miljö (paper) innan live.

## 10. Circuit Breaker – Pausa handel vid avvikelser
Mål: Minimera risk vid incidenter eller avvikande beteende.

- Manuell CB (omedelbar):
  1) `docker compose down` för att stoppa processer.
  2) Växla till paper (`config.testnet.json`) och verifiera i test.
  3) Sätt striktare risk i konfig (t.ex. `max_open_trades: 0`, skydd i `protections`).
  4) Starta endast i paper tills rotorsak är åtgärdad.

- Observability (pågående arbete):
  - Strukturerad JSON-logg med korrelations-ID implementerad i `app/strategies/`.
  - Plan: Prometheus-metrik med larm (Grafana) för att trigga CB-process.

- Runbook-checklista inför återstart:
  - [ ] Incident dokumenterad och rotorsak åtgärdad.
  - [ ] Backtest/paper visar förväntat beteende.
  - [ ] Riskparametrar och protections verifierade.
  - [ ] Notifieringar aktiva (t.ex. Telegram).

## 11. Risk‑guardrails – miljövariabler och CB‑format

__Miljövariabler (RiskManager)__

- `RISK_MAX_CONCURRENT_BACKTESTS` (int) – Max parallella backtests. 0/blank = obegränsat.
- `RISK_CONCURRENCY_TTL_SEC` (int, default 900) – TTL för lockfiler (städar bort föräldralösa).
- `RISK_STATE_DIR` (path, default `user_data/state`) – Tillståndskatalog för `running/*.lock` och CB.
- `RISK_CIRCUIT_BREAKER_FILE` (path, default `<state_dir>/circuit_breaker.json`) – CB‑fil.
- `RISK_ALLOW_WHEN_CB` (0/1) – Tillåt körning trots CB (manual override).
- `RISK_MAX_BACKTEST_DRAWDOWN_PCT` (float) – Blockera backtest om senaste `max_drawdown_account` ≥ detta (0.2 = 20%).
- `RISK_DB_PATH` (path, default `user_data/registry/strategies_registry.sqlite`) – SQLite med `runs`/`metrics`.
- `RISK_LIVE_MAX_CONCURRENT_TRADES` (int) – Max samtidiga öppna trades i live.
- `RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT` (float) – Max exponering per marknad (0.25 = 25%).

__Circuit Breaker filformat__ (`circuit_breaker.json`):

```json
{
  "active": true,
  "reason": "incident-123",
  "until_iso": "2025-08-17T10:15:00Z"
}
```

- `active`: true/false – på/av.
- `reason`: kort beskrivning.
- `until_iso`: (valfri) UTC‑tid när CB slutar gälla.

__CLI‑hjälpare__ (`scripts/circuit_breaker.py`):

```powershell
py -3 scripts/circuit_breaker.py status --state-dir user_data\state
py -3 scripts/circuit_breaker.py enable --reason "manual" --minutes 60 --state-dir user_data\state
py -3 scripts/circuit_breaker.py disable --state-dir user_data\state
```

Flaggor:

- `--file <path>` kan ersätta `--state-dir` för att peka direkt på filen.
- `--minutes` eller `--until 2025-08-17T10:15:00Z` sätter varaktighet.
