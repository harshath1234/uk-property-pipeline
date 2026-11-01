from __future__ import annotations

import requests

from ppd import ingest
from ppd.ingest import Manifest, land_file


def test_landing_from_local_dir_is_idempotent(settings, fixture_dir):
    first = ingest.run(settings, from_dir=fixture_dir)
    assert set(first.values()) == {"landed"}
    second = ingest.run(settings, from_dir=fixture_dir)
    assert set(second.values()) == {"duplicate"}

    manifest = Manifest(settings.path("manifest"))
    assert len(manifest.entries) == 4
    assert sorted(e.load_seq for e in manifest.entries) == [1, 2, 3, 4]
    monthly = [e for e in manifest.entries if e.kind == "monthly"]
    assert monthly[0].name.startswith("pp-monthly-update-new-version-")
    assert not list(settings.path("landing").glob(".incoming-*"))


class _Resp:
    def __init__(self, headers=None, body=b"", status=200):
        self.headers = headers or {}
        self._body = body
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def iter_content(self, _n):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_unchanged_remote_file_is_skipped(settings, monkeypatch, fixture_dir):
    body = (fixture_dir / "pp-2024.csv").read_bytes()
    calls = {"get": 0}

    def fake_get(url, stream, timeout):
        calls["get"] += 1
        return _Resp(body=body)

    def fake_head(url, timeout, allow_redirects):
        return _Resp(headers={"ETag": '"abc"', "Content-Length": str(len(body))})

    monkeypatch.setattr(ingest.requests, "get", fake_get)
    manifest = Manifest(settings.path("manifest"))
    url = "https://example.test/pp-2024.csv"
    assert land_file(settings, manifest, "pp-2024.csv", url, "yearly", fake_head) == "landed"
    assert land_file(settings, manifest, "pp-2024.csv", url, "yearly", fake_head) == "skipped"
    assert calls["get"] == 1


def test_transient_errors_are_retried(settings, monkeypatch, fixture_dir):
    body = (fixture_dir / "pp-2023.csv").read_bytes()
    attempts = {"n": 0}

    def flaky_get(url, stream, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise requests.ConnectionError("boom")
        return _Resp(body=body)

    monkeypatch.setattr(ingest.requests, "get", flaky_get)
    monkeypatch.setattr(ingest.time, "sleep", lambda _s: None)
    manifest = Manifest(settings.path("manifest"))
    head = lambda url, timeout, allow_redirects: _Resp(headers={"ETag": '"x"'})  # noqa: E731
    out = land_file(settings, manifest, "pp-2023.csv", "https://example.test/pp-2023.csv",
                    "yearly", head)
    assert out == "landed"
    assert attempts["n"] == 3
