# Runbook – Tradingbot

## Start (paper)
```bash
docker compose pull
docker compose up
```

## Backtesting
```bash
docker compose run --rm freqtrade backtesting \
  -c /freqtrade/user_data/configs/config.testnet.json \
  --strategy MaCrossoverStrategy
```

## Hyperopt
```bash
docker compose run --rm freqtrade hyperopt \
  -c /freqtrade/user_data/configs/config.testnet.json \
  --strategy MaCrossoverStrategy \
  --spaces buy sell roi stoploss
```

## Loggar
- Fil: `user_data/logs/freqtrade.log`

## Incident
- Stoppa containern: `docker compose down`
- Växla till testnet/dry-run vid avvikelse.
- Skapa incident-anteckning i `docs/`.
