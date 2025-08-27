from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .models import EventSchedule


def load_events(path: str | Path) -> EventSchedule:
    """Load events from a JSON file into an EventSchedule.

    Example schema (see events.sample.json):
    {
      "events": [
        {
          "name": "CPI Release",
          "symbols": ["BTC"],
          "category": "macro",
          "impact": "high",
          "start": "2025-01-12T13:30:00Z",
          "end": "2025-01-12T14:30:00Z",
          "description": "US CPI"
        }
      ]
    }
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Events file not found: {p}")

    data = p.read_text(encoding="utf-8")
    try:
        return EventSchedule.model_validate_json(data)
    except ValidationError as e:
        raise ValueError(f"Invalid events file: {p}: {e}")
