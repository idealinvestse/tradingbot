# Strategier, metoder och koncept – Registry

Senast uppdaterad (UTC): 2025-08-29T15:33:09Z

> **Obs**: Detta register uppdateras manuellt. För automatisk generering från koden, använd:
> `py -3 scripts/strategy_cli.py introspect && py -3 scripts/strategy_cli.py docs`

## Strategier

| ID | Namn | Klass | Fil | Status | Timeframes | Marknader | Indikatorer | Taggar |
|---|---|---|---|---|---|---|---|---|
| ma_crossover | MA Crossover Strategy | MaCrossoverStrategy | user_data/strategies/ma_crossover_strategy.py | active | 5m | BTC/USDT, ETH/USDT | EMA, MACD, RSI, BollingerBands, ATR | trend-following, spot, demo-friendly |
| mean_reversion_bb | Mean Reversion BB | MeanReversionBbStrategy | user_data/strategies/mean_reversion_bb.py | draft | 5m | - | BollingerBands, RSI | mean-reversion |
| momentum_macd_rsi | Momentum MACD+RSI | MomentumMacdRsiStrategy | user_data/strategies/momentum_macd_rsi.py | draft | 5m | - | MACD, RSI | momentum |
| bb_breakout | BB Breakout | BollingerBreakoutStrategy | user_data/strategies/bb_breakout_strategy.py | draft | 5m | - | BollingerBands, Volume | breakout |
| breakout_bb_vol | Breakout BB+Vol | BreakoutBbVolStrategy | user_data/strategies/breakout_bb_vol.py | draft | 5m | - | BollingerBands, Volume | breakout |
| wma_stoch | WMA + Stochastic | WmaStochSwingStrategy | user_data/strategies/wma_stoch_strategy.py | draft | 5m | - | WMA, Stochastic | trend, oscillator |
| hodl | HODL Strategy | HodlStrategy | user_data/strategies/hodl_strategy.py | experimental | 1d | - | - | buy-and-hold |
| ai_strategy | AI Strategy | AiStrategy | user_data/strategies/ai_strategy.py | active | 5m | BTC/USDT, ETH/USDT | EMA, MACD, RSI | ai-driven, adaptive |
| template | Template Strategy | TemplateStrategy | user_data/strategies/_template_strategy.py | template | - | - | - | - |

### Strategistatus
- **active**: Produktionsklar, testad i backtest och paper
- **draft**: Under utveckling, grundläggande funktionalitet implementerad
- **experimental**: Experimentell, använd med försiktighet
- **template**: Mall för nya strategier

## Metoder

| ID | Namn | Kategori | Beskrivning | Relaterade strategier | Referenser |
|---|---|---|---|---|---|
| backtesting | Backtesting | evaluation | Kör strategi mot historisk data för att mäta PnL, Sharpe, antal trades m.m. | ma_crossover, mean_reversion_bb, momentum_macd_rsi | - |
| hyperopt | Hyperopt | optimization | Optimerar parametrar för en vald strategi över definierade spaces (buy/sell/roi/stoploss). | ma_crossover, mean_reversion_bb, momentum_macd_rsi | - |
| dca_scheduler | DCA Scheduler | execution-planning | Skapar en regelbunden köpplan (Dollar-Cost Averaging) mellan två datum och exporterar CSV. | - | scripts/dca_scheduler.py |
| indexing | Results Indexing | analysis | Indexerar backtest- och hyperopt-resultat till SQLite för rapportgenerering och analys. | alla strategier | scripts/strategy_cli.py |
| reporting | Results Reporting | analysis | Genererar Markdown-rapporter från indexerade resultat med metrics och spårbarhet. | alla strategier | scripts/strategy_cli.py |
| risk_management | Risk Management | safety | Circuit breaker, concurrency limits, drawdown protection och live trading guardrails. | alla strategier | app/strategies/risk.py |

## Koncept

| ID | Namn | Beskrivning | Referenser |
|---|---|---|---|
| ema_crossover | EMA Crossover | Korsning av kort/lång EMA genererar köp/säljsignal. | - |
| rsi | RSI | Relative Strength Index, momentumindikator. | - |
| bollinger_width | Bollinger Band Width | (Övre - Nedre)/SMA som volatilitetsmått. | - |
| atr | ATR | Average True Range, volatilitetsmått som kan användas för stopdistance. | - |
| max_drawdown_protection | Max Drawdown Protection | Stoppar handel vid för stor nedgång över lookback-fönster. | - |

## Källor

| ID | Titel | Plats | Ämne | Kvalitet |
|---|---|---|---|---|
| internal_analys_doc | Analys av strategier | analys_strategier,.md | research | internal |

