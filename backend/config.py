"""Loads config/scoring.yaml, config/web_patterns.yaml and config/honeytokens.yaml."""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "config"


@dataclass(frozen=True)
class Config:
    windows: dict
    classes: dict  # class name -> list of compiled patterns, in file order
    hidden_paths: frozenset
    weights: dict
    cap: int
    needs_confirmation: frozenset
    severity: dict  # name -> inclusive lower bound
    low_priority_below: int
    honeytokens: dict  # token id -> {"planted_on", "valid_on", ...} (hashes only)
    scoring_version: int = 1
    patterns_version: int = 1


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_config(config_dir: Optional[str] = None) -> Config:
    d = Path(config_dir or os.environ.get("DG_CONFIG_DIR") or DEFAULT_DIR)
    scoring = _read(d / "scoring.yaml")
    patterns = _read(d / "web_patterns.yaml")
    tokens = _read(d / "honeytokens.yaml")
    return Config(
        windows=dict(scoring["windows"]),
        classes={name: [re.compile(p, re.IGNORECASE) for p in pats]
                 for name, pats in patterns["classes"].items()},
        hidden_paths=frozenset(p.lower() for p in patterns["hidden_paths"]),
        weights=dict(scoring["weights"]),
        cap=int(scoring["cap"]),
        needs_confirmation=frozenset(scoring.get("needs_confirmation", [])),
        severity=dict(scoring["severity"]),
        low_priority_below=int(scoring["low_priority_below"]),
        honeytokens={t["id"]: t for t in tokens.get("tokens", [])},
        scoring_version=scoring.get("version", 1),
        patterns_version=patterns.get("version", 1),
    )
