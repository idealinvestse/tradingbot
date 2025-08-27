from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "strategies" not in data or "methods" not in data or "concepts" not in data:
        raise ValueError("Invalid registry JSON: missing required top-level keys")
    return data


def _fmt_list(values: list[Any]) -> str:
    if not values:
        return "-"
    return ", ".join(str(v) for v in values)


def generate_markdown(registry: dict[str, Any]) -> str:
    updated = registry.get("updated_utc") or datetime.now(timezone.utc).isoformat()
    lines: list[str] = []
    lines.append("# Strategier, metoder och koncept – Registry")
    lines.append("")
    lines.append(f"Senast uppdaterad (UTC): {updated}")
    lines.append("")

    # Strategies
    lines.append("## Strategier")
    lines.append("")
    lines.append("| ID | Namn | Klass | Fil | Status | Timeframes | Marknader | Indikatorer | Taggar |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for s in registry.get("strategies", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    s.get("id", ""),
                    s.get("name", ""),
                    s.get("class_name", ""),
                    s.get("file_path", ""),
                    s.get("status", ""),
                    _fmt_list(s.get("timeframes", [])),
                    _fmt_list(s.get("markets", [])),
                    _fmt_list(s.get("indicators", [])),
                    _fmt_list(s.get("tags", [])),
                ]
            )
            + " |"
        )
    lines.append("")

    # Methods
    lines.append("## Metoder")
    lines.append("")
    lines.append("| ID | Namn | Kategori | Beskrivning | Relaterade strategier | Referenser |")
    lines.append("|---|---|---|---|---|---|")
    for m in registry.get("methods", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    m.get("id", ""),
                    m.get("name", ""),
                    m.get("category", ""),
                    m.get("description", "").replace("\n", " "),
                    _fmt_list(m.get("related_strategies", [])),
                    _fmt_list(m.get("references", [])),
                ]
            )
            + " |"
        )
    lines.append("")

    # Concepts
    lines.append("## Koncept")
    lines.append("")
    lines.append("| ID | Namn | Beskrivning | Referenser |")
    lines.append("|---|---|---|---|")
    for c in registry.get("concepts", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    c.get("id", ""),
                    c.get("name", ""),
                    c.get("description", "").replace("\n", " "),
                    _fmt_list(c.get("references", [])),
                ]
            )
            + " |"
        )
    lines.append("")

    # Sources (optional)
    if registry.get("sources"):
        lines.append("## Källor")
        lines.append("")
        lines.append("| ID | Titel | Plats | Ämne | Kvalitet |")
        lines.append("|---|---|---|---|---|")
        for src in registry.get("sources", []):
            lines.append(
                "| "
                + " | ".join(
                    [
                        src.get("id", ""),
                        src.get("title", ""),
                        src.get("path", ""),
                        src.get("topic", ""),
                        src.get("quality", ""),
                    ]
                )
                + " |"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Läser docs/strategies_registry.json och genererar docs/STRATEGIES.md med tabeller."
        )
    )
    p.add_argument(
        "--registry",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "strategies_registry.json"),
        help="Sökväg till registry JSON",
    )
    p.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "STRATEGIES.md"),
        help="Sökväg till utdata Markdown",
    )
    args = p.parse_args()

    reg_path = Path(args.registry)
    out_path = Path(args.out)

    registry = load_registry(reg_path)
    md = generate_markdown(registry)

    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
