"""JSON export/import utilities."""

import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


def export_state(data: Dict[str, Any], output_path: str = "exports/state_export.json") -> str:
    """Export simulation state to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "version": "1.0",
        **data,
    }

    with open(path, "w") as f:
        json.dump(export_data, f, indent=2, default=str)

    return str(path)


def import_state(input_path: str) -> Dict[str, Any]:
    """Import simulation state from JSON file."""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Import file not found: {input_path}")

    with open(path, "r") as f:
        data = json.load(f)

    # Validate version
    version = data.get("version", "unknown")
    if version != "1.0":
        raise ValueError(f"Incompatible import version: {version}")

    return data
