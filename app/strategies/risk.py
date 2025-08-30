from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .logging_utils import get_json_logger
from .persistence.sqlite import connect as sqlite_connect
from .persistence.sqlite import ensure_schema as sqlite_ensure_schema


@dataclass
class RiskConfig:
    """Basic risk configuration loaded from environment or provided explicitly.

    Extend this with real guardrails (drawdown, concurrent trades, exposure) as needed.
    """

    max_concurrent_backtests: int | None = None
    concurrency_ttl_sec: int = 900
    state_dir: Path | None = None
    circuit_breaker_file: Path | None = None
    allow_run_when_cb: bool = False
    max_backtest_drawdown_pct: float | None = None  # e.g., 0.2 for 20%
    db_path: Path | None = None
    # Live trading guardrails
    live_max_concurrent_trades: int | None = None
    live_max_per_market_exposure_pct: float | None = None  # 0..1 (values >1 treated as percent)


class RiskManager:
    """Minimal RiskManager placeholder.

    Currently only logs the pre-run check. Extend to enforce:
    - max daily drawdown
    - max concurrent trades / runs
    - per-market exposure caps
    - circuit breaker state
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        logger = get_json_logger("risk", static_fields={"op": "__init__"})
        self.cfg = config or self._load_from_env()
        logger.debug(
            "risk_manager_initialized",
            extra={k: str(v) for k, v in self.cfg.__dict__.items() if v is not None},
        )

    def _load_from_env(self) -> RiskConfig:
        logger = get_json_logger("risk", static_fields={"op": "_load_from_env"})
        raw_mcb = os.getenv("RISK_MAX_CONCURRENT_BACKTESTS")
        try:
            mcb = int(raw_mcb) if raw_mcb is not None else None
        except ValueError:
            mcb = None
        logger.debug("loaded_max_concurrent_backtests", extra={"value": mcb})

        raw_ttl = os.getenv("RISK_CONCURRENCY_TTL_SEC", "900")
        try:
            ttl = int(raw_ttl)
        except ValueError:
            ttl = 900
        logger.debug("loaded_concurrency_ttl_sec", extra={"value": ttl})

        # Resolve project root: app/strategies/ -> project root
        root = Path(__file__).resolve().parents[2]
        user_data = root / "user_data"
        state_dir = Path(os.getenv("RISK_STATE_DIR", str(user_data / "state")))
        logger.debug("loaded_state_dir", extra={"value": state_dir})
        cb_file = os.getenv("RISK_CIRCUIT_BREAKER_FILE", str(state_dir / "circuit_breaker.json"))
        logger.debug("loaded_circuit_breaker_file", extra={"value": cb_file})

        allow_run_when_cb = os.getenv("RISK_ALLOW_WHEN_CB", "0").strip() in {"1", "true", "True"}
        logger.debug("loaded_allow_run_when_cb", extra={"value": allow_run_when_cb})

        raw_dd = os.getenv("RISK_MAX_BACKTEST_DRAWDOWN_PCT")
        try:
            max_dd = float(raw_dd) if raw_dd is not None else None
        except ValueError:
            max_dd = None
        logger.debug("loaded_max_backtest_drawdown_pct", extra={"value": max_dd})

        db_path = Path(
            os.getenv("RISK_DB_PATH", str(user_data / "registry" / "strategies_registry.sqlite"))
        )
        logger.debug("loaded_db_path", extra={"value": db_path})

        # Live guardrails
        raw_lct = os.getenv("RISK_LIVE_MAX_CONCURRENT_TRADES")
        try:
            live_lct = int(raw_lct) if raw_lct is not None else None
        except ValueError:
            live_lct = None
        logger.debug("loaded_live_max_concurrent_trades", extra={"value": live_lct})

        raw_pme = os.getenv("RISK_LIVE_MAX_PER_MARKET_EXPOSURE_PCT")
        try:
            live_pme = float(raw_pme) if raw_pme is not None else None
        except ValueError:
            live_pme = None
        logger.debug("loaded_live_max_per_market_exposure_pct", extra={"value": live_pme})

        return RiskConfig(
            max_concurrent_backtests=mcb,
            concurrency_ttl_sec=ttl,
            state_dir=state_dir,
            circuit_breaker_file=Path(cb_file),
            allow_run_when_cb=allow_run_when_cb,
            max_backtest_drawdown_pct=max_dd,
            db_path=db_path,
            live_max_concurrent_trades=live_lct,
            live_max_per_market_exposure_pct=live_pme,
        )

    def pre_run_check(
        self,
        *,
        kind: str,
        strategy: str,
        timeframe: str | None,
        context: dict[str, Any] | None,
        correlation_id: str | None,
    ) -> tuple[bool, str | None]:
        """Perform a pre-run guardrail check.

        Returns (allowed, reason_if_blocked).
        """
        logger = get_json_logger(
            "risk",
            static_fields={"correlation_id": correlation_id} if correlation_id else None,
        )
        logger.info(
            "pre_run_check",
            extra={
                "kind": kind,
                "strategy": strategy,
                "timeframe": timeframe or "",
                "max_concurrent_backtests": self.cfg.max_concurrent_backtests,
                "max_backtest_drawdown_pct": self.cfg.max_backtest_drawdown_pct,
                "live_max_concurrent_trades": self.cfg.live_max_concurrent_trades,
                "live_max_per_market_exposure_pct": self.cfg.live_max_per_market_exposure_pct,
            },
        )

        # Circuit breaker
        logger.debug("checking_circuit_breaker")
        active, reason = self._circuit_breaker_active(correlation_id=correlation_id)
        if active and not self.cfg.allow_run_when_cb:
            logger.warning("circuit_breaker_block", extra={"reason": reason})
            return False, f"circuit_breaker_active: {reason or ''}"

        # Continue with other checks
        return self._continue_pre_run_check(kind, context, correlation_id)

    def check_risk_limits(self) -> bool:
        """Check if risk limits allow trading.

        Simple check for AI strategy executor compatibility.
        Returns True if trading is allowed.
        """
        logger = get_json_logger("risk", static_fields={"op": "check_risk_limits"})

        # Check circuit breaker
        active, reason = self._circuit_breaker_active()
        if active and not self.cfg.allow_run_when_cb:
            logger.warning("risk_limits_exceeded", extra={"reason": f"circuit_breaker: {reason}"})
            return False

        # For now, allow trading if circuit breaker is not active
        logger.debug("risk_limits_ok")
        return True

    def _continue_pre_run_check(
        self, kind: str, context: dict[str, Any] | None, correlation_id: str | None
    ) -> tuple[bool, str | None]:
        """Continue pre_run_check after circuit breaker check.

        This method contains the rest of pre_run_check logic.
        """
        logger = get_json_logger(
            "risk",
            static_fields={"correlation_id": correlation_id} if correlation_id else None,
        )

        # Optional: block backtests if recent drawdown exceeded threshold
        if kind == "backtest" and self.cfg.max_backtest_drawdown_pct is not None:
            logger.debug("checking_recent_drawdown")
            try:
                dd = self._recent_backtest_drawdown(correlation_id=correlation_id)
            except Exception:
                dd = None
            if dd is not None and abs(dd) >= max(0.0, self.cfg.max_backtest_drawdown_pct):
                logger.warning("max_dd_block", extra={"recent_dd": dd})
                return False, f"recent_drawdown_exceeded: {dd}"

        # Live trading guardrails (pre-run gating via provided context)
        if kind == "live":
            logger.debug("checking_live_guardrails")
            # concurrent trades cap
            if self.cfg.live_max_concurrent_trades is not None:
                open_trades = None
                if context and isinstance(context.get("open_trades_count"), (int, float)):
                    open_trades = int(context["open_trades_count"])
                if open_trades is not None and open_trades >= max(
                    0, self.cfg.live_max_concurrent_trades
                ):
                    logger.warning(
                        "live_concurrent_trades_block",
                        extra={
                            "open_trades": open_trades,
                            "max": self.cfg.live_max_concurrent_trades,
                        },
                    )
                    return (
                        False,
                        f"live_concurrent_trades_exceeded: {open_trades}/{self.cfg.live_max_concurrent_trades}",
                    )

            # per-market exposure cap
            if self.cfg.live_max_per_market_exposure_pct is not None:
                threshold = abs(self.cfg.live_max_per_market_exposure_pct)
                if threshold > 1.0:
                    threshold = threshold / 100.0
                exposures = None
                if context and isinstance(context.get("market_exposure_pct"), dict):
                    exposures = context.get("market_exposure_pct")
                if exposures:
                    # Any market exceeding threshold blocks
                    for mkt, val in exposures.items():
                        try:
                            v = float(val)
                        except Exception:
                            continue
                        av = abs(v)
                        if av > 1.0:
                            av = av / 100.0
                        if av > threshold:
                            logger.warning(
                                "live_per_market_exposure_block",
                                extra={"market": mkt, "exposure": v, "threshold": threshold},
                            )
                            return False, f"per_market_exposure_exceeded:{mkt}:{v}>{threshold}"

        return True, None

    # ---- Concurrency slots ----
    def acquire_run_slot(
        self, *, kind: str, correlation_id: str | None
    ) -> tuple[bool, str | None, Path | None]:
        """Acquire a concurrency slot using lock files.

        Returns (allowed, reason, lock_path). Caller should invoke release_run_slot(lock_path).
        """
        logger = get_json_logger(
            "risk",
            static_fields={"correlation_id": correlation_id} if correlation_id else None,
        )
        max_slots = self.cfg.max_concurrent_backtests if kind == "backtest" else None
        if not max_slots or max_slots <= 0:
            # No limit configured
            lock = self._create_lock(kind, correlation_id)
            logger.info("slot_acquired", extra={"kind": kind, "unbounded": True, "lock": str(lock)})
            return True, None, lock

        count = self._count_active_locks(kind)
        if count >= max_slots:
            logger.warning("slot_denied", extra={"kind": kind, "active": count, "max": max_slots})
            return False, f"too_many_active_{kind}s: {count}/{max_slots}", None

        lock = self._create_lock(kind, correlation_id)
        logger.info(
            "slot_acquired", extra={"kind": kind, "active_before": count, "lock": str(lock)}
        )
        return True, None, lock

    def release_run_slot(self, lock_path: Path | None, *, correlation_id: str | None) -> None:
        logger = get_json_logger(
            "risk",
            static_fields={"correlation_id": correlation_id} if correlation_id else None,
        )
        if lock_path is None:
            return
        try:
            lock_path.unlink(missing_ok=True)
            logger.info("slot_released", extra={"lock": str(lock_path)})
        except Exception:
            logger.warning("slot_release_error", extra={"lock": str(lock_path)})

    # ---- Helpers ----
    def _running_dir(self) -> Path:
        state_dir = self.cfg.state_dir or Path("user_data/state")
        d = state_dir / "running"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _create_lock(self, kind: str, correlation_id: str | None) -> Path:
        rd = self._running_dir()
        name = f"{kind}_{int(time.time())}_{os.getpid()}"
        if correlation_id:
            name += f"_{correlation_id[:12]}"
        path = rd / f"{name}.lock"
        payload = {
            "kind": kind,
            "pid": os.getpid(),
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "cid": correlation_id or "",
        }
        try:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            # Best-effort: if write fails, still return a path to attempt cleanup later
            pass
        return path

    def _count_active_locks(self, kind: str) -> int:
        logger = get_json_logger("risk", static_fields={"op": "_count_active_locks"})
        rd = self._running_dir()
        ttl = max(1, int(self.cfg.concurrency_ttl_sec))
        now_s = time.time()
        active_locks = 0

        for p in rd.glob(f"{kind}_*.lock"):
            try:
                age = now_s - p.stat().st_mtime
            except FileNotFoundError:
                # File was deleted between glob and stat, not active
                continue
            except Exception as e:
                logger.warning(f"Could not process lock file {p.name}: {e}")
                continue  # Potentially corrupted, do not count as active

            if age > ttl:
                # Stale lock found, attempt to clean up and skip.
                logger.debug(
                    "stale_lock_cleanup",
                    extra={"lock_file": str(p), "age_sec": age, "ttl_sec": ttl},
                )
                try:
                    p.unlink()
                except OSError as e:
                    logger.error(f"Failed to remove stale lock {p.name}: {e}")
                continue  # Go to next file, do not count this stale lock.

            # If we reach here, the lock is not stale and is considered active.
            active_locks += 1
        return active_locks

    def _circuit_breaker_active(
        self, *, correlation_id: str | None = None
    ) -> tuple[bool, str | None]:
        logger = get_json_logger(
            "risk",
            static_fields=(
                {"correlation_id": correlation_id, "op": "_circuit_breaker_active"}
                if correlation_id
                else {"op": "_circuit_breaker_active"}
            ),
        )
        cb = self.cfg.circuit_breaker_file
        logger.debug("cb_check", extra={"cb_file": str(cb)})
        if not cb:
            return False, None
        try:
            if not cb.exists():
                logger.debug("cb_file_not_found")
                return False, None
            data = json.loads(cb.read_text(encoding="utf-8"))
            active = bool(data.get("active"))
            reason = str(data.get("reason") or "")
            until_iso = data.get("until_iso")
            if not active:
                return False, None
            if until_iso:
                try:
                    s = until_iso.replace("Z", "+00:00")
                    until = datetime.fromisoformat(s)
                    if until.tzinfo is None:
                        until = until.replace(tzinfo=timezone.utc)
                except Exception:
                    until = datetime.max.replace(tzinfo=timezone.utc)
                if datetime.now(tz=timezone.utc) > until:
                    return False, None
            return True, reason
        except Exception as e:
            logger.error("circuit_breaker_parse_error", extra={"path": str(cb), "error": str(e)})
            return True, "circuit_breaker_parse_error"

    def _recent_backtest_drawdown(self, *, correlation_id: str | None = None) -> float | None:
        """Return most recent backtest 'max_drawdown_account' metric if available."""
        logger = get_json_logger(
            "risk",
            static_fields=(
                {"correlation_id": correlation_id, "op": "_recent_backtest_drawdown"}
                if correlation_id
                else {"op": "_recent_backtest_drawdown"}
            ),
        )
        db = self.cfg.db_path
        if not db or not db.exists():
            logger.debug("dd_check_skipped_no_db", extra={"db_path": str(db)})
            return None
        try:
            con = sqlite3.connect(db)
            cur = con.cursor()
            cur.execute(
                """
                SELECT m.value
                FROM metrics m
                JOIN runs r ON r.id = m.run_id
                WHERE r.kind = 'backtest' AND m.key = 'max_drawdown_account'
                ORDER BY COALESCE(r.started_utc, '') DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            con.close()
            if not row:
                logger.debug("dd_check_no_metric_found")
                return None
            val = row[0]
            if val is None:
                return None
            try:
                f = float(val)
            except Exception:
                return None
            # Normalize to [0..1] if expressed as percent (e.g., 25 => 0.25)
            af = abs(f)
            if af > 1.0:
                af = af / 100.0
            return af if f >= 0 else -af
        except Exception as e:
            logger.error("dd_check_db_error", extra={"db_path": str(db), "error": str(e)})
            return None

    def log_incident(
        self,
        *,
        run_id: str | None,
        severity: str,
        description: str,
        log_excerpt_path: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Log an incident to the database."""
        logger = get_json_logger(
            "risk",
            static_fields={"correlation_id": correlation_id} if correlation_id else None,
        )

        # Normalize severity and generate incident_id early for consistent logging
        sev = (severity or "").strip().lower()
        if sev not in {"info", "warning", "error", "critical"}:
            sev = "warning"

        incident_id = f"incident_{int(time.time())}_{os.getpid()}"
        if correlation_id:
            incident_id += f"_{correlation_id[:12]}"

        # Log the incident with appropriate level
        log_extra = {
            "incident_id": incident_id,
            "run_id": run_id or "",
            "severity": sev,
            "description": description,
            "log_excerpt_path": log_excerpt_path or "",
        }
        if sev == "info":
            logger.info("incident_logged", extra=log_extra)
        elif sev == "warning":
            logger.warning("incident_logged", extra=log_extra)
        elif sev == "error":
            logger.error("incident_logged", extra=log_extra)
        else:
            logger.critical("incident_logged", extra=log_extra)

        # Persist the incident if DB configured
        db = self.cfg.db_path
        if not db:
            logger.info(
                "incident_db_skipped",
                extra={"incident_id": incident_id, "reason": "no_db_configured"},
            )
            return

        try:
            con = sqlite_connect(db)
            # Ensure schema is present (creates 'incidents' table if missing)
            sqlite_ensure_schema(con, with_extended=True)
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO incidents (
                    id, run_id, severity, description, log_excerpt_path, created_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    run_id,
                    sev,
                    description,
                    log_excerpt_path,
                    datetime.now(tz=timezone.utc).isoformat(),
                ),
            )
            con.commit()
            con.close()
            logger.info("incident_stored", extra={"incident_id": incident_id})
        except Exception as e:
            logger.error(
                "incident_store_error", extra={"incident_id": incident_id, "error": str(e)}
            )
