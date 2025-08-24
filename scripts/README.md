# Scripts

Hjälpskript för datanedladdning, rapportgenerering och batch-körningar. På Windows rekommenderas PowerShell (`.ps1`) eller direkta Python-anrop.

## DCA-scheduler (`dca_scheduler.py`)
Skapar en regelbunden köpplan (Dollar-Cost Averaging) mellan två datum och skriver ut en CSV-fil som kan användas i vidare analys/automatisering.

### När används detta?
- Icke-teknisk: För att planera återkommande småköp (t.ex. varje vecka) över tid, för att minska timing-risk.
- Teknisk: För att generera deterministiska inköpsscheman som senare kan matas in i andra pipelines.

### JSON-konfig (inparametrar)
```json
{
  "start_utc": "2025-01-01T00:00:00Z",
  "end_utc": "2025-03-01T00:00:00Z",
  "interval": "weekly",
  "pair": "BTC/USDT",
  "amount_usdt": 50
}
```
- `interval`: ett av `daily`, `weekly`, `biweekly`, `monthly`.
- `amount_usdt`: belopp i stake-valuta (USDT) per köp.

### Exempel (Windows PowerShell)
1) Skapa en konfigfil, t.ex. `user_data/configs/dca.sample.json`.
2) Kör skriptet och skriv en CSV till `user_data/reports/dca_plan.csv`:
```powershell
py -3 scripts/dca_scheduler.py --config user_data/configs/dca.sample.json --out user_data/reports/dca_plan.csv
```

CSV-format:
```csv
at_utc,pair,amount
2025-01-01T00:00:00+00:00,BTC/USDT,50.00
2025-01-08T00:00:00+00:00,BTC/USDT,50.00
...
```

### Vanliga frågor
- Behövs API-nycklar? Nej, detta skript använder inga börs-anrop.
- Tidszon? Ange alltid tider i UTC (`Z` på slutet). Filen skriver ut tider i UTC.
- Kan jag byta valuta? Ja, men skriptet tolkar `amount_usdt` som stake-valuta-belopp. Anpassa namn/kolumn efter behov.

## Backup/Restore (`backup_restore.py`)
Skapar och återställer backup av artefakter och SQLite‑register under `user_data/`.

- Skapa backup (default `user_data/backups/`):
  ```powershell
py -3 scripts/backup_restore.py backup
```
  Flaggar:
  - `--logs` inkluderar `user_data/logs/` i backupen (zippad)
  - `--out <dir>` anger alternativ backupkatalog
  - `--no-backtests`/`--no-hyperopts`/`--no-registry` för att exkludera delar

- Återställ från backup:
  ```powershell
py -3 scripts/backup_restore.py restore user_data\backups\backup_YYYYmmdd_HHMMSS --overwrite
```
  Delmängd:
  - `--only registry|backtests|hyperopts|logs` (kan upprepas)

Rekommenderat: Kör restore i test/paper‑miljö först innan live.

## Circuit Breaker (`circuit_breaker.py`)
Styr circuit breaker‑läget (på/av/status). Skriver/läser `circuit_breaker.json` under `user_data/state/` som standard.

### Exempel (Windows PowerShell)
```powershell
py -3 scripts/circuit_breaker.py status --state-dir user_data\state
py -3 scripts/circuit_breaker.py enable --reason "manual" --minutes 60 --state-dir user_data\state
py -3 scripts/circuit_breaker.py disable --state-dir user_data\state
```

Flaggor:
- `--file <path>` pekar direkt på CB‑filen och åsidosätter `--state-dir`.
- `--minutes <N>` varaktighet i minuter.
- `--until 2025-08-17T10:15:00Z` alternativt absolut UTC‑tidpunkt.

## Live‑runner (`run_live.py`)
Startar `freqtrade trade` via vår runner med RiskManager‑guardrails (CB, live‑concurrent trades, per‑market exposure). Du kan ange aktuell kontext så att guardrails kan bedömas innan start.

## Strategy CLI (`strategy_cli.py`)

Detta är det centrala CLI-verktyget för att hantera strategiregister, dokumentation och databasexporter. Det ersätter det gamla `strategies_registry_sync.py`-skriptet.

### Kommandon

- `docs`: Genererar `docs/STRATEGIES.md` från registry JSON
- `export-db`: Exporterar registry JSON till SQLite-databas
- `index-backtests`: Indexerar backtestresultat till SQLite-databasen
- `index-hyperopts`: Indexerar hyperoptresultat till SQLite-databasen
- `report-results`: Genererar Markdown-rapport från SQLite-resultatdatabasen
- `all`: Kör både `docs` och `export-db`
- `introspect`: Skannar `user_data/strategies` och skapar en JSON-sammanfattning

### Exempel (Windows PowerShell)
```powershell
# Generera dokumentation från registry
py -3 scripts/strategy_cli.py docs

# Exportera registry till SQLite-databas
py -3 scripts/strategy_cli.py export-db

# Indexera backtestresultat
py -3 scripts/strategy_cli.py index-backtests

# Generera resultatrapport
py -3 scripts/strategy_cli.py report-results

# Kör alla registeroperationer
py -3 scripts/strategy_cli.py all
```

## Strategiregistry Sync (DEPRECATED)

Skriptet `strategies_registry_sync.py` är nu föråldrat och ersatt av `strategy_cli.py`. Använd `strategy_cli.py docs` istället för att generera dokumentation från registry JSON.

### Exempel (Windows PowerShell)
```powershell
py -3 scripts/run_live.py --config user_data\configs\config.mainnet.json --strategy MaCrossoverStrategy `
  --open-trades 3 --exposure BTC/USDT=25% --exposure ETH/USDT=0.15
```

Flaggor:
- `--config <path>` (krävs) – Freqtrade‑konfig.
- `--strategy <Name>` (valfri) – Strategiklass; kan annars läsas från konfig.
- `--open-trades <N>` – Aktuellt antal öppna trades (int).
- `--exposure <mkt=val>` (repetera) – Per‑marknadsexponering. Accepterar `25%` eller `0.25`.
- `--extra <arg>` (repetera) – Extra CLI‑flaggor som skickas vidare till `freqtrade`.
- `--correlation-id <id>` – Eget korrelations‑ID i loggar.
