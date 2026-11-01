from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from ppd.config import load_settings

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ppd"


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    if not (FIXTURE_DIR / "pp-2024.csv").exists():
        sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
        from make_fixtures import main

        main(str(FIXTURE_DIR))
    return FIXTURE_DIR


@pytest.fixture()
def settings(tmp_path: Path, fixture_dir: Path):
    """Settings pointing every path at a fresh temp folder."""
    cfg = tmp_path / "pipeline.yaml"
    shutil.copy(ROOT / "config" / "pipeline.yaml", cfg)
    return load_settings(config_path=cfg, env={}, root=tmp_path)
