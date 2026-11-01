"""Load pipeline settings from config/pipeline.yaml with environment overrides.

Override rule: PPD_<SECTION>_<KEY> (upper case). Lists are comma-separated.
Example: PPD_SOURCE_YEARS="2024,2025" PPD_STORAGE_BACKEND=gcs
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "pipeline.yaml"


def _coerce(value: str, like: Any) -> Any:
    """Convert an env-var string to the type of the default value."""
    if isinstance(like, bool):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(like, int):
        return int(value)
    if isinstance(like, list):
        items = [v.strip() for v in value.split(",") if v.strip()]
        if like and isinstance(like[0], int):
            return [int(v) for v in items]
        return items
    return value


def _apply_env_overrides(cfg: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    for section, values in cfg.items():
        if not isinstance(values, dict):
            continue
        for key, default in values.items():
            env_key = f"PPD_{section}_{key}".upper()
            if env_key in env:
                values[key] = _coerce(env[env_key], default)
    return cfg


@dataclass(frozen=True)
class Settings:
    raw: dict[str, Any]
    root: Path

    def path(self, key: str) -> Path:
        """Resolve a key from the `paths` section against the project root."""
        p = Path(self.raw["paths"][key])
        return p if p.is_absolute() else self.root / p

    @property
    def source(self) -> dict[str, Any]:
        return self.raw["source"]

    @property
    def storage(self) -> dict[str, Any]:
        return self.raw["storage"]

    @property
    def postgres_dsn(self) -> str:
        return self.raw["postgres"]["dsn"]


def load_settings(
    config_path: Path | None = None,
    env: dict[str, str] | None = None,
    root: Path | None = None,
) -> Settings:
    path = Path(config_path or os.environ.get("PPD_CONFIG", DEFAULT_CONFIG))
    with path.open() as fh:
        cfg = yaml.safe_load(fh)
    cfg = _apply_env_overrides(cfg, dict(os.environ if env is None else env))
    data_root = os.environ.get("PPD_ROOT") if env is None else env.get("PPD_ROOT")
    return Settings(raw=cfg, root=Path(root or data_root or PROJECT_ROOT))
