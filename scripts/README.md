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

