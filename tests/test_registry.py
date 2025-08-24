from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.strategies.registry import load_registry, export_sqlite
from app.strategies.registry_models import RegistrySchema


def test_load_registry_valid(tmp_path: Path) -> None:
    """Test loading a valid registry JSON file."""
    # Create a valid registry JSON file
    registry_data = {
        "version": 1,
        "updated_utc": "2025-08-16T18:03:00Z",
        "strategies": [
            {
                "id": "test_strategy",
                "name": "Test Strategy",
                "class_name": "TestStrategy",
                "file_path": "user_data/strategies/test_strategy.py",
                "status": "active",
                "timeframes": ["5m"],
                "markets": ["BTC/USDT"],
                "indicators": ["RSI"],
                "parameters": {
                    "rsi_period": {"type": "IntParameter", "default": 14}
                },
                "risk": {
                    "stoploss": -0.10
                },
                "performance": {
                    "last_backtest": None
                },
                "tags": ["test"]
            }
        ],
        "methods": [],
        "concepts": [],
        "sources": []
    }
    
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(registry_data), encoding="utf-8")
    
    # Load and validate the registry
    loaded_registry = load_registry(registry_file)
    
    # Check that the loaded data matches the input
    assert loaded_registry["version"] == 1
    assert loaded_registry["updated_utc"] == "2025-08-16T18:03:00Z"
    assert len(loaded_registry["strategies"]) == 1
    assert loaded_registry["strategies"][0]["id"] == "test_strategy"


def test_load_registry_invalid_structure(tmp_path: Path) -> None:
    """Test that loading an invalid registry raises ValidationError."""
    # Create an invalid registry JSON file (missing required fields)
    invalid_registry_data = {
        "version": 1,
        # Missing updated_utc
        "strategies": [
            {
                "id": "test_strategy",
                # Missing required fields like name, class_name, etc.
            }
        ],
        "methods": [],
        "concepts": [],
        "sources": []
    }
    
    registry_file = tmp_path / "invalid_registry.json"
    registry_file.write_text(json.dumps(invalid_registry_data), encoding="utf-8")
    
    # Loading should raise ValidationError
    with pytest.raises(ValidationError):
        load_registry(registry_file)


def test_registry_schema_validation() -> None:
    """Test that the RegistrySchema model validates correctly."""
    # Valid data
    valid_data = {
        "version": 1,
        "updated_utc": "2025-08-16T18:03:00Z",
        "strategies": [
            {
                "id": "test_strategy",
                "name": "Test Strategy",
                "class_name": "TestStrategy",
                "file_path": "user_data/strategies/test_strategy.py",
                "status": "active"
            }
        ],
        "methods": [],
        "concepts": [],
        "sources": []
    }
    
    # This should not raise an exception
    registry = RegistrySchema(**valid_data)
    assert registry.version == 1
    assert len(registry.strategies) == 1
    
    # Invalid data (missing version)
    invalid_data = {
        # Missing version
        "updated_utc": "2025-08-16T18:03:00Z",
        "strategies": [],
        "methods": [],
        "concepts": [],
        "sources": []
    }
    
    # This should raise ValidationError
    with pytest.raises(ValidationError):
        RegistrySchema(**invalid_data)
