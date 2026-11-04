"""Download Price Paid Data files into the landing zone, idempotently.

- One manifest (JSON) records every file landed: URL, size, ETag, SHA-256,
  landed-at timestamp and a monotonically increasing load sequence number.
- A yearly file is re-downloaded only when its remote ETag or size changes
  (HM Land Registry refreshes yearly files every month).
- The monthly change file always has the same URL, so each new release is
  stored under its content hash; a release already in the manifest is skipped.
- Downloads stream to a temp file and are renamed only when complete, so a
  failed run never leaves a half-written file in landing.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from ppd.config import PROJECT_ROOT, Settings
from ppd.logging_utils import get_logger, log

LOG = get_logger("ppd.ingest")
CHUNK = 1 << 20  # 1 MiB


@dataclass
class ManifestEntry:
    name: str           # file name in landing
    source: str         # URL or local path it came from
    kind: str           # "yearly" | "monthly"
    sha256: str
    bytes: int
    etag: str | None
    landed_at: str
    load_seq: int


class Manifest:
    def __init__(self, path: Path):
        self.path = path
        self.entries: list[ManifestEntry] = []
        if path.exists():
            self.entries = [ManifestEntry(**e) for e in json.loads(path.read_text())]

    def by_source(self, source: str) -> ManifestEntry | None:
        matches = [e for e in self.entries if e.source == source]
        return max(matches, key=lambda e: e.load_seq) if matches else None

    def has_hash(self, sha: str) -> bool:
        return any(e.sha256 == sha for e in self.entries)

    def next_seq(self) -> int:
        return max((e.load_seq for e in self.entries), default=0) + 1

    def upsert(self, entry: ManifestEntry) -> None:
        self.entries = [e for e in self.entries if e.name != entry.name] + [entry]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(e) for e in self.entries], indent=2))
        tmp.replace(self.path)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _with_retries(fn, *, retries: int, what: str):
    """Call fn(); retry on network errors with exponential backoff."""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            log(LOG, "retrying", what=what, attempt=attempt, wait_s=wait, error=str(exc))
            time.sleep(wait)
    return None


def planned_sources(settings: Settings) -> list[tuple[str, str, str]]:
    """(landing name, url, kind) for every configured source file."""
    base = settings.source["base_url"].rstrip("/")
    out = [(f"pp-{y}.csv", f"{base}/pp-{y}.csv", "yearly") for y in settings.source["years"]]
    monthly = settings.source["monthly_update_file"]
    out.append((monthly, f"{base}/{monthly}", "monthly"))
    return out


def _download(url: str, dest: Path, timeout: int) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for block in resp.iter_content(CHUNK):
                fh.write(block)
    tmp.replace(dest)


def land_file(
    settings: Settings,
    manifest: Manifest,
    name: str,
    source: str,
    kind: str,
    session_head=requests.head,
) -> str:
    """Land one file. Returns "skipped", "landed" or "duplicate"."""
    landing = settings.path("landing")
    landing.mkdir(parents=True, exist_ok=True)
    timeout = settings.source["timeout_seconds"]
    retries = settings.source["max_retries"]
    is_url = source.startswith("http")

    etag, size = None, None
    if is_url:
        head = _with_retries(
            lambda: session_head(source, timeout=timeout, allow_redirects=True),
            retries=retries,
            what=f"HEAD {source}",
        )
        try:
            head.raise_for_status()
            etag = head.headers.get("ETag")
            size = int(head.headers["Content-Length"]) if "Content-Length" in head.headers else None
        except requests.HTTPError as exc:
            # Some servers refuse HEAD; fall back to downloading and comparing hashes.
            log(LOG, "HEAD refused, will download and compare hash", file=name, error=str(exc))
        previous = manifest.by_source(source)
        if previous and previous.etag and previous.etag == etag and previous.bytes == size:
            log(LOG, "unchanged at source, skipping", file=name, etag=etag)
            return "skipped"

    staging = landing / f".incoming-{name}"
    if is_url:
        _with_retries(
            lambda: _download(source, staging, timeout), retries=retries, what=f"GET {source}"
        )
    else:
        shutil.copyfile(source, staging)

    sha = sha256_of(staging)
    if manifest.has_hash(sha):
        staging.unlink()
        log(LOG, "content already landed, skipping", file=name, sha256=sha[:12])
        return "duplicate"

    # Monthly releases share one URL, so keep each release under its hash.
    final_name = name if kind == "yearly" else f"{Path(name).stem}-{sha[:12]}.csv"
    final = landing / final_name
    staging.replace(final)
    manifest.upsert(
        ManifestEntry(
            name=final_name,
            source=source,
            kind=kind,
            sha256=sha,
            bytes=final.stat().st_size,
            etag=etag,
            landed_at=datetime.now(UTC).isoformat(timespec="seconds"),
            load_seq=manifest.next_seq(),
        )
    )
    manifest.save()
    log(LOG, "landed", file=final_name, bytes=final.stat().st_size, sha256=sha[:12])
    return "landed"


def run(settings: Settings, from_dir: Path | None = None) -> dict[str, str]:
    """Land all configured files. With `from_dir`, copy local files instead of downloading
    (used for offline runs, CI and tests)."""
    manifest = Manifest(settings.path("manifest"))
    results: dict[str, str] = {}
    if from_dir is None and settings.source.get("from_dir"):
        from_dir = Path(settings.source["from_dir"])
        if not from_dir.is_absolute():
            from_dir = PROJECT_ROOT / from_dir
    if from_dir:
        for f in sorted(Path(from_dir).glob("pp-*.csv")):
            kind = "monthly" if "monthly" in f.name else "yearly"
            results[f.name] = land_file(settings, manifest, f.name, str(f), kind)
    else:
        for name, url, kind in planned_sources(settings):
            results[name] = land_file(settings, manifest, name, url, kind)
    if settings.storage["backend"] == "gcs":
        from ppd.cloud import upload_landing

        upload_landing(settings, manifest)
    return results
