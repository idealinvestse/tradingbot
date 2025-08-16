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

## 8. Vidare läsning
- Översikt, FAQ och exempel: `README.md`
- Kodstandard och utvecklingspolicy: `docs/CODE_GUIDELINES.md`
- Scripts och DCA-planer: `scripts/README.md`
