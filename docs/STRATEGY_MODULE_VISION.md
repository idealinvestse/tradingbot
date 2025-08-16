# Strategimodul – fördjupning och vision

Denna text beskriver hur strategier hanteras idag i projektet, vilka mål vi har framåt, och ett konkret förslag till en fristående strategimodul som stödjer hela kedjan från idé → experiment → körningar → analys → beslut, med mätetal och artefakter spårade och dokumenterade.

## Sammanfattning
- **Nuläge**: Freqtrade‑strategier ligger i `user_data/strategies/`. Vi har ett centralt JSON‑register (`docs/strategies_registry.json`), en tabellvy (`docs/STRATEGIES.md`) och en SQLite‑export (`user_data/registry/strategies_registry.sqlite`).
- **Mål**: Separera strategi‑domänen i en modul som standardiserar metadata, körningar (backtest/hyperopt/paper), mätetal, artefakter och beslut. Säkerställa reproducerbarhet och uppmuntra idégenerering via lättviktigt arbetsflöde och tydligt mätsystem.
- **Förslag**: Lägg till `app/strategies/` med tjänster för registry, introspektion, körningsorkestrering, mätinsamling, persistens (SQLite) och rapporter. Komplettera med CLI/scripts samt CI‑steg för validering och dokumentgenerering.

## Nuläge i repo
- Strategier (Freqtrade): `user_data/strategies/*.py` (t.ex. `MaCrossoverStrategy`, `WmaStochSwingStrategy`).
- Register (källa): `docs/strategies_registry.json` → genererar `docs/STRATEGIES.md` via `scripts/strategies_registry_sync.py`.
- Register (DB): `scripts/strategies_registry_export_sqlite.py` → `user_data/registry/strategies_registry.sqlite`.
- Artefakter idag (standard Freqtrade):
  - Backtest: `user_data/backtest_results/` (JSON + ZIP).
  - Hyperopt: `user_data/hyperopt_results/` (fthypt‑filer).

## Mål
- **Separering**: Strategi‑logik och kunskapshantering i en modul (`app/strategies/`) – oberoende av UI/CLI.
- **Reproducerbarhet**: Frys versioner, datafönster, seeds; lagra config‑hash och körmiljö.
- **Mätbarhet**: Enhetliga nyckeltal (PnL, Sharpe, max drawdown, trades) och spårade artefakter.
- **Idédriven utveckling**: Enkel väg från idé till experiment, med tydliga beslutspunkter och dokumenterade källor/hypoteser.
- **Automatisering**: CI validerar register, genererar docs och uppdaterar DB.

## Föreslagen arkitektur
```
app/strategies/
  __init__.py
  specs.py            # Datamodeller/typer (pydantic) för Strategy, Idea, Experiment, Run, Metric, Artifact
  registry.py         # Läsa/skriva JSON‑register + synk mot SQLite
  introspect.py       # Inspektera Freqtrade‑klasser, extrahera parametrar/indikatorer
  runner.py           # Orkestrera backtest/hyperopt/paper via Freqtrade‑CLI (subprocess)
  metrics.py          # Parsers för backtest/hyperopt‑artefakter → normaliserade metrics
  persistence/
    __init__.py
    sqlite.py         # DB‑access, migrations, queries
  reporting.py        # Generera sammanfattningar, Markdown/HTML‑rapporter
  ideation.py         # Idé/experiment‑workflow, statusar och länkar till källor
scripts/
  strategy_cli.py     # CLI: idea create, experiment plan/run, report, sync‑docs, export‑db
```

### Dataflöde (översikt)
1. Utvecklare lägger till/ändrar strategi i `user_data/strategies/`.
2. `introspect.py` läser klass(er) och uppdaterar `docs/strategies_registry.json` (klassnamn, parametrar, indikatorer).
3. `registry.py` synkar registret till SQLite. `reporting.py` genererar `docs/STRATEGIES.md` och ev. html‑rapporter.
4. `runner.py` kör backtest/hyperopt/paper. Artefakter hamnar i `user_data/*`. `metrics.py` extraherar nyckeltal → SQLite.
5. `ideation.py` binder samman Idé → Experiment → Körningar → Beslut och uppdaterar dokumentation.

### Kontrakt och format
- **Konfiguration**: Snapshot av använd `config.*.json` och CLI‑flaggor sparas per körning.
- **Seeds**: Standardiserad seed för determinism (loggas och sparas i DB).
- **Hashar**: Config‑hash, datafönster‑hash, artefakt‑hashar för spårbarhet.
- **Tider**: Allt i UTC internt; konvertering vid presentation.
- **Pengar**: `decimal.Decimal` i kod; persistens som text/number i SQLite.

## Datamodell (SQLite – utökning)
Befintligt: `strategies`, `methods`, `concepts`, `sources`.

Nya tabeller (förslag):
- `ideas(id, title, description, status, tags, sources, owner, created_utc)`
- `experiments(id, idea_id, strategy_id, hypothesis, timeframe, markets, period_start_utc, period_end_utc, seed, config_hash, created_utc)`
- `runs(id, experiment_id, kind, started_utc, finished_utc, status, docker_image, freqtrade_version, config_json, data_window, artifacts_path)`
- `metrics(run_id, key, value)` – normaliserad nyckel/värde, t.ex. `pnl_net`, `sharpe`, `max_drawdown`, `trades`.
- `artifacts(run_id, name, path, sha256)` – kopplingar till `.meta.json`, `.zip`, rapporter.
- `decisions(id, idea_id, decision, rationale, decided_utc, approver)` – t.ex. Promote/Reject/Park.
- `incidents(id, run_id, severity, description, log_excerpt_path, created_utc)` – koppling till run vid avvikelser.

## Mätetal (minimi‑set)
- **Backtest**: `pnl_net`, `sharpe`, `calmar`, `max_drawdown`, `winrate`, `trades`, `exposure_time`, `avg_trade_duration`, `profit_factor`.
- **Hyperopt**: bästa målfunktion, parametrar (snapshot), antal utvärderingar, körningstid.
- **Live/paper**: orderlatens, slippage‑estimat, fail‑rate, retrys, protections‑triggers.

## Workflows
- **Idé → Experimentplan → Körning(ar) → Analys → Beslut**
  1. Skapa idé med hypotes, källor, acceptanskriterier.
  2. Planera experiment (strategi, period, marknader, seed, mätetal).
  3. Kör backtest/hyperopt; spara artefakter och metrics.
  4. Rapport: Jämför mot baseline och acceptanskriterier.
  5. Beslut: Promote/Reject/Park + motivering. Schemalägg regressionstester.
- **Regression**: Periodiskt jobb som kör utvalda strategier mot fasta fönster; larma vid regress.

## Kvalitet och guardrails
- **Determinism**: Frysta beroenden (pyproject), seeds, fixerat datafönster, versionsloggning.
- **Typning och lint**: MyPy strikt i `app/strategies/`; Black/Ruff/isort.
- **Felhanteirng**: Specifika undantag, strukturerad logg (JSON), korrelations‑ID.
- **Säkerhet**: Testnet default; aldrig hemligheter i repo; `.env`/CI‑secrets.
- **Numerik**: `Decimal` för pengar; kontrollera NaN/inf i pandas; centraliserad rundning.

## Integration med Freqtrade
- Kör via CLI (Docker eller lokalt) från `runner.py`.
- Parsning av `.meta.json`/rapporter i `metrics.py`.
- Kontraktsgräns: Ingen direkt intern import av Freqtrade; håll modul oberoende och ersättlig.

## Idéutveckling – att premiera
- **Lätt CLI**: `strategy_cli.py` med kommandon:
  - `idea create`, `idea list`, `idea link-source`
  - `experiment plan`, `experiment run backtest|hyperopt|paper`
  - `report build`, `docs sync`, `db export`
- **Mallfiler**: Templates för idé/experiment (Markdown + YAML‑frontmatter) som också läses in till DB.
- **Synlighet**: Autogenererade sammanställningar i `docs/` (topplistor, regressionsrapport, beslut).

## Roadmap (etapper)
1. **Skelett + registerkoppling**
   - Skapa `app/strategies/` + `persistence/sqlite.py` + migrations.
   - Lyft nuvarande registry‑kod till modulens `registry.py`; håll `scripts/*` tunna.
2. **Introspektion + körning + mätetal**
   - `introspect.py` för att skrapa parametrar/indikatorer ur strategiklasser.
   - `runner.py` för backtest/hyperopt; `metrics.py` för parsning till DB.
3. **Rapporter + CI**
   - `reporting.py` genererar markdown/HTML. CI validerar register, uppdaterar docs/DB.
4. **Live‑observability + governance**
   - Parser för live‑loggar, incidentkoppling, beslut/approvals‑flöde.

---
Denna arkitektur följer projektets kodstandard och mål: säkerhet, reproducerbarhet, enkelhet, tydliga loggar/mätningar och testbarhet. Den är modulär och gör det enkelt att lägga till/utvärdera strategiska idéer utan att kompromissa med drift eller spårbarhet.
