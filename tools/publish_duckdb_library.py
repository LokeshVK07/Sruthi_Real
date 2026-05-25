#!/usr/bin/env python3
"""Write a publish manifest for the generated Sruthi DuckDB catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "sruthi.duckdb"
DEFAULT_MANIFEST = ROOT / "cloudflare" / "data" / "library-manifest.json"
DEFAULT_RELEASE_TAG = "sruthi-library"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish Sruthi DuckDB library metadata.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--release-tag", default=DEFAULT_RELEASE_TAG)
    parser.add_argument("--version", default=None)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_metrics(db_path: Path) -> dict:
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        row = connection.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM albums) AS album_count,
              (SELECT COUNT(*) FROM songs) AS song_count,
              (SELECT COUNT(*) FROM songs WHERE COALESCE(NULLIF(audio_128_url, ''), NULLIF(remote_audio_128_url, ''), NULLIF(audio_320_url, ''), NULLIF(remote_audio_320_url, ''), NULLIF(audio_url, ''), '') <> '') AS playable_song_count,
              (SELECT COUNT(*) FROM download_links) AS download_link_count,
              (SELECT COUNT(DISTINCT movie) FROM songs WHERE TRIM(COALESCE(movie, '')) <> '') AS distinct_movie_count,
              (SELECT MAX(updated_at) FROM songs) AS latest_song_updated_at
            """
        ).fetchone()
    finally:
        connection.close()
    return {
        "albumCount": int(row[0] or 0),
        "songCount": int(row[1] or 0),
        "playableSongCount": int(row[2] or 0),
        "downloadLinkCount": int(row[3] or 0),
        "distinctMovieCount": int(row[4] or 0),
        "latestSongUpdatedAt": row[5],
    }


def main() -> int:
    args = parse_args()
    db_path = args.db_path.resolve()
    manifest_path = args.manifest.resolve()
    if not db_path.exists() or db_path.stat().st_size < 4096:
        raise SystemExit(f"DuckDB catalog is missing or too small: {db_path}")

    version = args.version or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    release_file = db_path.name
    download_url = f"https://github.com/{args.repo}/releases/download/{args.release_tag}/{release_file}"
    raw_manifest_url = f"https://raw.githubusercontent.com/{args.repo}/{args.ref}/{manifest_path.relative_to(ROOT).as_posix()}"
    metrics = collect_metrics(db_path)
    payload = {
        "name": "Sruthi DuckDB Library",
        "version": version,
        "releaseTag": args.release_tag,
        "downloadUrl": download_url,
        "download_url": download_url,
        "manifestUrl": raw_manifest_url,
        "manifest_url": raw_manifest_url,
        "databaseFile": release_file,
        "databaseBytes": db_path.stat().st_size,
        "sha256": sha256_file(db_path),
        "repo": args.repo,
        "ref": args.ref,
        "updatedAt": version,
        **metrics,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "manifest": str(manifest_path), **metrics}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
