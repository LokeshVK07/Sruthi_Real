#!/usr/bin/env python3
"""Warm Cloudflare R2 audio cache with browser-grade upstream fetching.

Cloudflare Workers cannot control their TLS/browser fingerprint, so MassTamilan
can challenge direct Worker fetches even when the same URL works in Chrome. This
script mirrors the stronger isaibox path: use curl_cffi Chrome impersonation,
validate that the response is real MP3 bytes, then upload to R2.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

try:
    from curl_cffi import requests as cffi_requests
except Exception as exc:  # pragma: no cover - import guard for workflow clarity
    raise SystemExit(
        "Missing dependency curl_cffi. Install with: python -m pip install curl_cffi"
    ) from exc

try:
    import duckdb
except Exception:  # pragma: no cover - DuckDB is only required for .duckdb catalogs.
    duckdb = None


ROOT = Path(__file__).resolve().parents[1]
SITE_ORIGIN = "https://www.masstamilan.dev"
DEFAULT_STATUS_API = "https://sruthi.vklokesh70.workers.dev/api/song-status/{song_id}"
MP3_MIN_BYTES = 64 * 1024
CHALLENGE_MARKERS = (
    b"<!doctype html",
    b"<html",
    b"just a moment",
    b"cloudflare",
    b"captcha",
    b"checking your browser",
)
_cooldown_until = 0.0


def wait_for_cooldown() -> None:
    remaining = _cooldown_until - time.monotonic()
    if remaining > 0:
        time.sleep(remaining + random.random())


def set_cooldown(seconds: float) -> None:
    global _cooldown_until
    _cooldown_until = max(_cooldown_until, time.monotonic() + max(0, seconds))


@dataclass(frozen=True)
class SongCandidate:
    id: str
    title: str
    artist: str
    movie: str
    album_url: str
    audio_128_url: str
    audio_320_url: str
    link_status: str
    updated_at: str


def clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def absolute_url(value: str, base_url: str = SITE_ORIGIN) -> str:
    text = clean_text(value)
    return urljoin(base_url or SITE_ORIGIN, text) if text else ""


def is_valid_mp3(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < MP3_MIN_BYTES:
        return False
    head = path.read_bytes()[:512].lower()
    if head.startswith(b"id3") or (len(head) > 2 and head[0] == 0xFF and head[1] in (0xFB, 0xF3, 0xF2)):
        return True
    return not any(marker in head for marker in CHALLENGE_MARKERS)


def is_audio_response(response) -> bool:
    content_type = clean_text(response.headers.get("content-type")).lower()
    if "text/html" in content_type or "text/plain" in content_type:
        return False
    return response.status_code in (200, 206) and (
        not content_type or content_type.startswith("audio/") or "mpeg" in content_type or "octet-stream" in content_type
    )


def parse_album_tracks(html: str) -> list[dict]:
    match = re.search(r"window\.albumTracks\s*=\s*(\[.*?\]);", html, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []


def track_title(track: dict) -> str:
    return clean_text(track.get("name") or track.get("title"))


def same_title(left: str, right: str) -> bool:
    def norm(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", clean_text(value).lower())

    return bool(norm(left) and norm(left) == norm(right))


def infer_bitrate_url(url: str, bitrate: int) -> str:
    return re.sub(r"/p(?:128|320)_cdn/", f"/p{bitrate}_cdn/", clean_text(url), flags=re.I)


def track_urls(track: dict, album_url: str, prefer_bitrate: int) -> list[str]:
    urls: list[str] = []
    dl_path = clean_text(track.get("dl_path"))
    if dl_path:
        urls.append(absolute_url(dl_path, album_url))
    for key in ("audio128Url", "audio320Url", "audioUrl"):
        if clean_text(track.get(key)):
            urls.append(absolute_url(track[key], album_url))
    expanded: list[str] = []
    for url in urls:
        expanded.append(url)
        if "/p128_cdn/" in url:
            expanded.append(infer_bitrate_url(url, 320))
        if "/p320_cdn/" in url:
            expanded.append(infer_bitrate_url(url, 128))
    unique = []
    seen = set()
    for url in expanded:
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(url)
    preferred = f"/p{prefer_bitrate}_cdn/"
    unique.sort(key=lambda item: 0 if preferred in item else 1)
    return unique


def refresh_urls_from_album(song: SongCandidate, prefer_bitrate: int, timeout: float) -> list[str]:
    if not song.album_url:
        return []
    response = cffi_requests.get(song.album_url, impersonate="chrome124", timeout=timeout)
    if response.status_code != 200 or "window.albumTracks" not in response.text:
        return []
    tracks = parse_album_tracks(response.text)
    if not tracks:
        return []
    matched = None
    for track in tracks:
        if clean_text(track.get("id")) == song.id:
            matched = track
            break
    if not matched:
        matched = next((track for track in tracks if same_title(track_title(track), song.title)), None)
    return track_urls(matched or {}, song.album_url, prefer_bitrate)


def candidate_urls(song: SongCandidate, prefer_bitrate: int) -> list[str]:
    urls = [song.audio_128_url, song.audio_320_url] if prefer_bitrate == 128 else [song.audio_320_url, song.audio_128_url]
    unique = []
    seen = set()
    for url in urls:
        absolute = absolute_url(url, song.album_url)
        if not absolute or absolute in seen:
            continue
        seen.add(absolute)
        unique.append(absolute)
    return unique


def is_duckdb_path(path: Path) -> bool:
    return path.suffix.lower() in {".duckdb", ".ddb"}


def open_catalog(path: Path):
    if is_duckdb_path(path):
        if duckdb is None:
            raise SystemExit("DuckDB catalog requested, but duckdb is not installed. Install with: python -m pip install duckdb")
        return "duckdb", duckdb.connect(str(path), read_only=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return "sqlite", conn


def rows_as_dicts(engine: str, cursor) -> list[dict]:
    if engine == "duckdb":
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    return [dict(row) for row in cursor.fetchall()]


def download_audio(song: SongCandidate, destination: Path, args: argparse.Namespace) -> tuple[bool, str]:
    urls = candidate_urls(song, args.prefer_bitrate)
    last_reason = "no-url"
    for attempt in range(args.retries + 1):
        if attempt:
            time.sleep(min(8.0, 1.4 * attempt) + random.random())
        for url in list(urls):
            response = None
            try:
                wait_for_cooldown()
                if args.request_delay > 0:
                    time.sleep(args.request_delay + random.random() * args.request_delay)
                response = cffi_requests.get(
                    url,
                    headers={
                        "Accept": "audio/mpeg,audio/*;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Referer": song.album_url or SITE_ORIGIN,
                    },
                    impersonate="chrome124",
                    timeout=args.timeout,
                    stream=True,
                    allow_redirects=True,
                )
                if not is_audio_response(response):
                    last_reason = f"bad-upstream:{response.status_code}:{response.headers.get('content-type')}"
                    if response.status_code in (403, 429, 503):
                        set_cooldown(args.challenge_cooldown)
                    continue
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if chunk:
                            handle.write(chunk)
                if is_valid_mp3(destination):
                    return True, "downloaded"
                destination.unlink(missing_ok=True)
                last_reason = "invalid-mp3"
            except Exception as exc:
                last_reason = f"download-error:{type(exc).__name__}"
            finally:
                if response is not None:
                    response.close()
        if attempt == 0:
            wait_for_cooldown()
            fresh_urls = refresh_urls_from_album(song, args.prefer_bitrate, args.timeout)
            for fresh_url in fresh_urls:
                if fresh_url not in urls:
                    urls.append(fresh_url)
    return False, last_reason


def load_candidates(args: argparse.Namespace) -> list[SongCandidate]:
    engine, conn = open_catalog(args.db)
    audio_128_expr = "coalesce(nullif(audio_128_url, ''), nullif(remote_audio_128_url, ''), nullif(audio_url, ''), '')"
    audio_320_expr = "coalesce(nullif(audio_320_url, ''), nullif(remote_audio_320_url, ''), nullif(audio_url, ''), '')"
    filters = [f"({audio_128_expr} != '' OR {audio_320_expr} != '')"]
    params: list[object] = []
    if args.ids:
        ids = [item.strip() for value in args.ids for item in value.split(",") if item.strip()]
        filters.append(f"id IN ({','.join('?' for _ in ids)})")
        params.extend(ids)
    if args.query:
        filters.append("(lower(title) LIKE ? OR lower(movie) LIKE ? OR lower(artist) LIKE ?)")
        like = f"%{args.query.lower()}%"
        params.extend([like, like, like])
    if args.only_unavailable:
        filters.append("link_status = 'unavailable'")

    order = {
        "recent": "CASE WHEN year >= 2020 THEN 0 ELSE 1 END, updated_at DESC, year DESC, lower(title)",
        "unavailable": "CASE WHEN link_status = 'unavailable' THEN 0 ELSE 1 END, updated_at DESC, lower(title)",
        "classic": "CASE WHEN year BETWEEN 1950 AND 2000 THEN 0 ELSE 1 END, year DESC, lower(title)",
        "title": "lower(title)",
    }[args.order]
    try:
        cursor = conn.execute(
            f"""
            SELECT id, title, artist, movie, album_url,
                   {audio_128_expr} AS audio_128_url,
                   {audio_320_expr} AS audio_320_url,
                   link_status, updated_at
            FROM songs
            WHERE {' AND '.join(filters)}
            ORDER BY {order}
            LIMIT ?
            """,
            [*params, args.scan_limit],
        )
        rows = rows_as_dicts(engine, cursor)
        return [
            SongCandidate(
                id=clean_text(row["id"]),
                title=clean_text(row["title"]),
                artist=clean_text(row["artist"]),
                movie=clean_text(row["movie"]),
                album_url=clean_text(row["album_url"]),
                audio_128_url=clean_text(row["audio_128_url"]),
                audio_320_url=clean_text(row["audio_320_url"]),
                link_status=clean_text(row["link_status"]),
                updated_at=clean_text(row["updated_at"]),
            )
            for row in rows
        ]
    finally:
        conn.close()


def status_api_cached(song_id: str, status_api: str, timeout: float) -> bool:
    if not status_api:
        return False
    url = status_api.format(song_id=song_id)
    try:
        response = cffi_requests.get(url, timeout=timeout)
        if response.status_code != 200:
            return False
        payload = response.json()
        return bool(payload.get("durableCached") or payload.get("cached"))
    except Exception:
        return False


def upload_with_wrangler(bucket: str, key: str, source: Path, config: str | None) -> None:
    command = [
        "npx",
        "wrangler",
        "r2",
        "object",
        "put",
        f"{bucket}/{key}",
        "--remote",
        "--file",
        str(source),
        "--content-type",
        "audio/mpeg",
        "--cache-control",
        "public, max-age=31536000",
        "--force",
    ]
    if config:
        command.extend(["--config", config])
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def process_song(song: SongCandidate, args: argparse.Namespace, temp_dir: Path) -> dict:
    started = time.monotonic()
    if status_api_cached(song.id, args.status_api, args.status_timeout):
        return {"id": song.id, "title": song.title, "status": "skipped-cached", "seconds": round(time.monotonic() - started, 2)}

    output = temp_dir / f"{song.id}.mp3"
    ok, reason = download_audio(song, output, args)
    if not ok:
        return {"id": song.id, "title": song.title, "movie": song.movie, "status": "failed", "reason": reason, "seconds": round(time.monotonic() - started, 2)}

    size = output.stat().st_size
    if size > args.max_song_bytes:
        output.unlink(missing_ok=True)
        return {"id": song.id, "title": song.title, "status": "failed", "reason": f"too-large:{size}", "bytes": size}
    upload_with_wrangler(args.bucket, f"audio/{song.id}.mp3", output, args.wrangler_config)
    output.unlink(missing_ok=True)
    return {"id": song.id, "title": song.title, "movie": song.movie, "status": "uploaded", "bytes": size, "seconds": round(time.monotonic() - started, 2)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Warm Sruthi R2 audio cache with validated MP3 files.")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "sruthi.db")
    parser.add_argument("--bucket", default=os.environ.get("R2_BUCKET_NAME", "sruthi-audio-cache"))
    parser.add_argument("--wrangler-config", default=None)
    parser.add_argument("--status-api", default=DEFAULT_STATUS_API)
    parser.add_argument("--ids", action="append", default=[])
    parser.add_argument("--query", default="")
    parser.add_argument("--only-unavailable", action="store_true")
    parser.add_argument("--order", choices=["recent", "unavailable", "classic", "title"], default="recent")
    parser.add_argument("--limit", type=int, default=64)
    parser.add_argument("--scan-limit", type=int, default=500)
    parser.add_argument("--max-total-bytes", type=int, default=350 * 1024 * 1024)
    parser.add_argument("--max-song-bytes", type=int, default=25 * 1024 * 1024)
    parser.add_argument("--prefer-bitrate", type=int, choices=[128, 320], default=128)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--status-timeout", type=float, default=8)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--request-delay", type=float, default=0.35)
    parser.add_argument("--challenge-cooldown", type=float, default=25)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")
    candidates = load_candidates(args)
    print(json.dumps({"event": "loaded-candidates", "count": len(candidates), "limit": args.limit, "order": args.order}))
    if args.dry_run:
        for song in candidates[: args.limit]:
            print(json.dumps({"id": song.id, "title": song.title, "movie": song.movie, "linkStatus": song.link_status}))
        return 0

    uploaded = 0
    failed = 0
    skipped = 0
    total_bytes = 0
    queued: list[SongCandidate] = []
    for song in candidates:
        if len(queued) >= args.limit:
            break
        if status_api_cached(song.id, args.status_api, args.status_timeout):
            skipped += 1
            continue
        queued.append(song)

    with tempfile.TemporaryDirectory(prefix="sruthi-r2-warm-") as raw_temp:
        temp_dir = Path(raw_temp)
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {executor.submit(process_song, song, args, temp_dir): song for song in queued}
            for future in as_completed(futures):
                result = future.result()
                if result["status"] == "uploaded":
                    uploaded += 1
                    total_bytes += int(result.get("bytes") or 0)
                elif result["status"].startswith("skipped"):
                    skipped += 1
                else:
                    failed += 1
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if total_bytes >= args.max_total_bytes:
                    print(json.dumps({"event": "byte-budget-reached", "totalBytes": total_bytes}), flush=True)
                    break

    print(json.dumps({"event": "summary", "uploaded": uploaded, "failed": failed, "skipped": skipped, "totalBytes": total_bytes}))
    return 0 if uploaded or skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
