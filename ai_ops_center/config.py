from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def load_agents() -> list[dict[str, Any]]:
    return load_yaml("agents.yaml").get("agents", [])


def load_machines() -> list[dict[str, Any]]:
    return load_yaml("machines.yaml").get("machines", [])


def load_revenue_strategy() -> dict[str, Any]:
    return load_yaml("revenue_strategy.yaml")

