# user_data

Detta är arbetsmappen som delas in i containern på `/freqtrade/user_data`. Här finns strategier, konfig och alla artefakter (loggar, rapporter, resultat).

## Översikt (icke-teknisk)
- Här hamnar det mesta som boten använder och producerar.
- Du kan byta strategi i `configs/` och se resultat/loggar i respektive mappar nedan.
- Radera inte filer här om du är osäker – de kan behövas för att reproducera resultat.

## Mappar och innehåll
- `strategies/` – Egna strategier (.py). Ex: `ma_crossover_strategy.py`.
- `configs/` – Konfigfiler för testnet (`config.testnet.json`), mainnet och backtest.
- `data/` – Historisk marknadsdata (skapas vid behov). Kan bli stor över tid.
- `logs/` – Loggar. Standardfil: `freqtrade.log` (se `docker-compose.yml`).
- `backtest_results/` – Backtest-artefakter: `.meta.json`, `.zip` m.m.
- `hyperopt_results/` – Resultat från hyperopt (`.fthypt`).
- `plot/` – Diagram/plots om aktiverat.
- `notebooks/` – (Valfritt) Jupyter-notebooks för analys.
- `freqaimodels/` – (Valfritt) Modeller om AI/ML används.
- `hyperopts/` – (Valfritt) Ytterligare hyperopt-material.
- `reports/` – Rapporter genererade av script/verktyg. Skapas vid behov (t.ex. DCA-plan).

## Vanliga uppgifter
- Byta strategi: Ändra fältet `"strategy"` i `configs/config.*.json` till klassnamnet.
- Byta par/timeframe: Uppdatera `pair_whitelist` och `timeframe` i konfig.
- Hitta resultat: Se `backtest_results/`, `hyperopt_results/`, `logs/`.

## Städning och lagring
- Rensa gamla backtests/hyperopt-artefakter om disken blir full.
- `data/` kan bli stor; spara endast nödvändiga perioder. Dokumentera vilket datafönster som användes.
- Behåll kopior av `.meta.json`-filer för spårbarhet i rapporter.

## Tips (tekniskt)
- Volymen monteras från repo-roten: `./user_data -> /freqtrade/user_data` i container.
- Script kan skapa mappar vid behov (ex. `reports/`).
- Använd Git LFS eller extern lagring om du versionerar stora artefakter.
