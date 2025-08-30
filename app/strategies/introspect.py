from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

INDICATOR_KEYWORDS = [
    # Common TA keywords (case-insensitive)
    "EMA",
    "SMA",
    "WMA",
    "HMA",
    "RSI",
    "MACD",
    "STOCH",
    "BOLLINGER",
    "BB",
    "ATR",
    "ADX",
    "CCI",
    "MFI",
    "VWAP",
    "ICHIMOKU",
    "SUPERTREND",
]

PARAMETER_SUFFIX = "Parameter"  # e.g., IntParameter, DecimalParameter


@dataclass
class ParameterInfo:
    name: str
    kind: str  # e.g., IntParameter, DecimalParameter, CategoricalParameter


@dataclass
class StrategyInfo:
    class_name: str
    file_path: str
    timeframe: str | None
    parameters: list[ParameterInfo]
    indicators: list[str]
    docstring: str | None


def _indicator_scan(text: str) -> list[str]:
    found = set()
    for kw in INDICATOR_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", text, flags=re.IGNORECASE):
            found.add(kw.upper())
    return sorted(found)


def _get_name_from_node(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def parse_strategy_file(path: Path) -> list[StrategyInfo]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    results: list[StrategyInfo] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            # Heuristic: strategy classes typically end with 'Strategy'
            if not class_name.endswith("Strategy"):
                continue

            # Extract class-level fields (e.g., timeframe = "5m") and parameter attributes
            timeframe: str | None = None
            params: list[ParameterInfo] = []

            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    # timeframe = "5m"
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == "timeframe":
                            if isinstance(stmt.value, ast.Constant) and isinstance(
                                stmt.value.value, str
                            ):
                                timeframe = stmt.value.value

                    # parameter = <Something>Parameter(...)
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            if isinstance(stmt.value, ast.Call):
                                func_name = _get_name_from_node(stmt.value.func)
                                if func_name and func_name.endswith(PARAMETER_SUFFIX):
                                    params.append(ParameterInfo(name=target.id, kind=func_name))

            indicators = _indicator_scan(src)
            doc = ast.get_docstring(node)
            results.append(
                StrategyInfo(
                    class_name=class_name,
                    file_path=str(path),
                    timeframe=timeframe,
                    parameters=params,
                    indicators=indicators,
                    docstring=doc,
                )
            )

    return results


def discover_strategies(base_dir: Path) -> list[StrategyInfo]:
    items: list[StrategyInfo] = []
    for p in sorted(base_dir.glob("*.py")):
        try:
            items.extend(parse_strategy_file(p))
        except Exception:
            # Keep robust: skip files that fail to parse
            continue
    return items


def to_json_dict(items: Iterable[StrategyInfo]) -> dict[str, Any]:
    return {
        "updated_utc": None,
        "strategies": [
            {
                "class_name": it.class_name,
                "file_path": it.file_path,
                "timeframe": it.timeframe,
                "parameters": [asdict(p) for p in it.parameters],
                "indicators": it.indicators,
                "docstring": it.docstring,
            }
            for it in items
        ],
    }
