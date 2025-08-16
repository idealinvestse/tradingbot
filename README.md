# Tradingbot – Freqtrade-baserad

Snabbstart för backtest/paper/live via Docker Compose. Fokus: säker testnet, reproducerbara backtester, tydlig struktur.

## Förkrav
- Docker Desktop (Windows)
- Git

## Setup
1. Kopiera `.env.example` till `.env` och fyll i API-nycklar (testnet först).
2. Justera `user_data/configs/config.testnet.json` (par, riskparametrar) vid behov.

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

## Träd
```
user_data/
  strategies/
  configs/
  data/
  logs/
  reports/
```

## Riktlinjer
Se `docs/CODE_GUIDELINES.md`.

## Vanliga justeringar
- Ändra timeframe/par i `config.*.json`.
- Finjustera stoploss/roi i strategi.
- Aktivera Telegram i konfig för notifieringar.

## Säkerhet
- Använd testnet tills backtest/paper är stabilt.
- Lagra aldrig hemligheter i repo. Använd `.env`/CI-secrets.
