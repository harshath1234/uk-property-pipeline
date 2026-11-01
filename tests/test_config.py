from ppd.config import DEFAULT_CONFIG, load_settings


def test_env_overrides_are_typed(tmp_path):
    s = load_settings(
        DEFAULT_CONFIG,
        env={"PPD_SOURCE_YEARS": "2024,2025", "PPD_SOURCE_MAX_RETRIES": "2",
             "PPD_STORAGE_BACKEND": "gcs"},
        root=tmp_path,
    )
    assert s.source["years"] == [2024, 2025]
    assert s.source["max_retries"] == 2
    assert s.storage["backend"] == "gcs"


def test_paths_resolve_under_root(tmp_path):
    s = load_settings(DEFAULT_CONFIG, env={}, root=tmp_path)
    assert s.path("landing") == tmp_path / "data" / "landing"
