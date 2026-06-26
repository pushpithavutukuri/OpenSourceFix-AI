"""
config.py
Loads config/config.yaml and exposes it as a plain dict.
"""

import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def load_config(path: Path = _CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
