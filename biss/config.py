"""Config loading. All tunables live in config.yaml; nothing is hard-coded in the engine."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


class Cfg(dict):
    """dict with attribute access, recursively."""

    def __getattr__(self, k: str) -> Any:
        try:
            v = self[k]
        except KeyError as e:
            raise AttributeError(k) from e
        return Cfg(v) if isinstance(v, dict) and not isinstance(v, Cfg) else v

    def override(self, **dotted: Any) -> "Cfg":
        """Return a deep copy with dotted keys replaced, e.g. override(**{"stop.max_stop_pct": 0.1})."""
        new = Cfg(copy.deepcopy(dict(self)))
        for key, val in dotted.items():
            parts = key.split(".")
            node = new
            for p in parts[:-1]:
                node = node[p]
            node[parts[-1]] = val
        return new


def load(path: str | Path | None = None) -> Cfg:
    p = Path(path) if path else ROOT / "config.yaml"
    with open(p, encoding="utf-8") as f:
        return Cfg(yaml.safe_load(f))


def data_dir(cfg: Cfg) -> Path:
    d = ROOT / cfg.data.dir
    d.mkdir(parents=True, exist_ok=True)
    return d
