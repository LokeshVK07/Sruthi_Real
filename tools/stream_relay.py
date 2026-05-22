#!/usr/bin/env python3
"""Python playback relay for Worker-blocked MassTamilan audio.

Cloudflare Workers are excellent for the UI, D1, R2, and cached playback, but
they cannot run browser-grade TLS impersonation. This relay is the last-resort
path for uncached songs: the Worker sends one song row here, this process uses
curl_cffi with Chrome impersonation, validates that the upstream is real MP3
audio, and streams it back. The Worker can then persist the successful full
response into R2.
"""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

try:
    from curl_cffi import requests as cffi_requests
except Exception as exc:  # pragma: no cover
    raise SystemExit("Missing dependency curl_cffi. Install with: python -m pip install curl_cffi") from exc

try:
    import boto3
except Exception:  # pragma: no cover - R2 is optional.
    boto3 = None

try:
    import duckdb
except Exception:  # pragma: no cover - DuckDB lookup is optional unless configured.
    duckdb = None


ROOT = Path(__file__).resolve().parents[1]
SITE_ORIGIN = "https://www.masstamilan.dev"
CACHE_AUDIO_DIR = Path(os.environ.get("SRUTHI_RELAY_AUDIO_CACHE", ROOT / ".cache" / "relay-audio"))
DUCKDB_PATH = Path(os.environ.get("SRUTHI_DUCKDB_PATH", ROOT / "data" / "sruthi.duckdb"))
SQLITE_PATH = Path(os.environ.get("SRUTHI_SQLITE_PATH", ROOT / "data" / "sruthi.db"))
LISTEN_HOST = os.environ.get("SRUTHI_RELAY_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("PORT", os.environ.get("SRUTHI_RELAY_PORT", "8088")))
RELAY_TOKEN = os.environ.get("SRUTHI_RELAY_TOKEN", "")
REQUEST_TIMEOUT = float(os.environ.get("SRUTHI_RELAY_TIMEOUT", "35"))
MAX_AUDIO_BYTES = int(os.environ.get("SRUTHI_RELAY_MAX_AUDIO_BYTES", str(26 * 1024 * 1024)))
MP3_MIN_BYTES = 16 * 1024
CHALLENGE_MARKERS = (
    b"<!doctype html",
    b"<html",
    b"just a moment",
    b"cloudflare",
    b"captcha",
    b"checking your browser",
    b"enable javascript and cookies",
    b"error code: 1020",
)


@dataclass(frozen=True)
class RelaySong:
    id: str
    title: str
    album_url: str
    song_page_url: str
    source_url: str
    audio_128_url: str
    audio_320_url: str
    remote_audio_128_url: str
    remote_audio_320_url: str


def clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def absolute_url(value: object, base_url: str = SITE_ORIGIN) -> str:
    text = clean_text(value)
    return urljoin(base_url or SITE_ORIGIN, text) if text else ""


def audio_cache_path(song_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.:-]+", "_", clean_text(song_id))
    return CACHE_AUDIO_DIR / f"{safe_id}.mp3"


def audio_object_key(song_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_.:-]+", "_", clean_text(song_id))
    return f"audio/{safe_id}.mp3"


def is_valid_audio_bytes(data: bytes) -> bool:
    if not data:
        return False
    head = data[:512].lower()
    if any(marker in head for marker in CHALLENGE_MARKERS):
        return False
    if data.startswith(b"ID3"):
        return True
    return len(data) > 2 and data[0] == 0xFF and data[1] in (0xFB, 0xF3, 0xF2)


def is_valid_audio_file(path: Path) -> bool:
    try:
        if path.stat().st_size < MP3_MIN_BYTES:
            return False
        return is_valid_audio_bytes(path.read_bytes()[:512])
    except OSError:
        return False


def r2_configured() -> bool:
    return bool(
        boto3
        and os.environ.get("R2_BUCKET_NAME")
        and os.environ.get("R2_ACCESS_KEY_ID")
        and os.environ.get("R2_SECRET_ACCESS_KEY")
        and (os.environ.get("R2_ENDPOINT_URL") or os.environ.get("R2_ACCOUNT_ID"))
    )


def r2_client_and_bucket():
    if not r2_configured():
        return None, ""
    endpoint = clean_text(os.environ.get("R2_ENDPOINT_URL"))
    if not endpoint:
        endpoint = f"https://{clean_text(os.environ.get('R2_ACCOUNT_ID'))}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    return client, clean_text(os.environ.get("R2_BUCKET_NAME"))


def restore_from_r2(song_id: str, cache_path: Path) -> bool:
    client, bucket = r2_client_and_bucket()
    if not client or not bucket:
        return False
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(f".r2.{os.getpid()}.part")
    try:
        client.download_file(bucket, audio_object_key(song_id), str(temp_path))
        if not is_valid_audio_file(temp_path):
            temp_path.unlink(missing_ok=True)
            return False
        os.replace(temp_path, cache_path)
        return True
    except Exception:
        temp_path.unlink(missing_ok=True)
        return False


def upload_to_r2(song_id: str, cache_path: Path) -> None:
    client, bucket = r2_client_and_bucket()
    if not client or not bucket or not is_valid_audio_file(cache_path):
        return
    try:
        client.upload_file(
            str(cache_path),
            bucket,
            audio_object_key(song_id),
            ExtraArgs={
                "ContentType": "audio/mpeg",
                "CacheControl": "public, max-age=31536000, immutable",
            },
        )
    except Exception as exc:
        print(f"R2 upload failed for song {song_id}: {exc}", file=sys.stderr, flush=True)


def upload_to_r2_background(song_id: str, cache_path: Path) -> None:
    if not r2_configured():
        return
    threading.Thread(target=upload_to_r2, args=(song_id, cache_path), daemon=True).start()


def is_audio_response(response) -> bool:
    content_type = clean_text(response.headers.get("content-type")).lower()
    if "text/html" in content_type or "text/plain" in content_type:
        return False
    return response.status_code in (HTTPStatus.OK, HTTPStatus.PARTIAL_CONTENT) and (
        content_type.startswith("audio/")
        or "mpeg" in content_type
        or "octet-stream" in content_type
        or not content_type
    )


def parse_song(payload: dict) -> RelaySong:
    song = payload.get("song") if isinstance(payload.get("song"), dict) else payload
    return RelaySong(
        id=clean_text(song.get("id")),
        title=clean_text(song.get("title")),
        album_url=absolute_url(song.get("album_url")),
        song_page_url=absolute_url(song.get("song_page_url")),
        source_url=absolute_url(song.get("source_url")),
        audio_128_url=absolute_url(song.get("audio_128_url"), song.get("album_url") or SITE_ORIGIN),
        audio_320_url=absolute_url(song.get("audio_320_url"), song.get("album_url") or SITE_ORIGIN),
        remote_audio_128_url=absolute_url(song.get("remote_audio_128_url"), song.get("album_url") or SITE_ORIGIN),
        remote_audio_320_url=absolute_url(song.get("remote_audio_320_url"), song.get("album_url") or SITE_ORIGIN),
    )


def unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def candidate_urls(song: RelaySong) -> list[str]:
    return unique((song.audio_128_url, song.audio_320_url, song.remote_audio_128_url, song.remote_audio_320_url))


def row_to_song(row: dict) -> RelaySong:
    return RelaySong(
        id=clean_text(row.get("id")),
        title=clean_text(row.get("title")),
        album_url=absolute_url(row.get("album_url")),
        song_page_url=absolute_url(row.get("song_page_url")),
        source_url=absolute_url(row.get("source_url")),
        audio_128_url=absolute_url(row.get("audio_128_url") or row.get("audio_url"), row.get("album_url") or SITE_ORIGIN),
        audio_320_url=absolute_url(row.get("audio_320_url") or row.get("audio_url"), row.get("album_url") or SITE_ORIGIN),
        remote_audio_128_url=absolute_url(row.get("remote_audio_128_url"), row.get("album_url") or SITE_ORIGIN),
        remote_audio_320_url=absolute_url(row.get("remote_audio_320_url"), row.get("album_url") or SITE_ORIGIN),
    )


def query_catalog_song(song_id: str) -> RelaySong | None:
    sql = """
        SELECT id, title, album_url, song_page_url, source_url, audio_url,
               audio_128_url, audio_320_url, remote_audio_128_url, remote_audio_320_url
        FROM songs
        WHERE id = ?
        LIMIT 1
    """
    if DUCKDB_PATH.exists() and duckdb is not None:
        connection = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        try:
            cursor = connection.execute(sql, [song_id])
            row = cursor.fetchone()
            if not row:
                return None
            columns = [description[0] for description in cursor.description]
            return row_to_song(dict(zip(columns, row)))
        finally:
            connection.close()
    if SQLITE_PATH.exists():
        connection = sqlite3.connect(SQLITE_PATH)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(sql, [song_id]).fetchone()
            return row_to_song(dict(row)) if row else None
        finally:
            connection.close()
    return None


def parse_album_tracks(html: str) -> list[dict]:
    match = re.search(r"window\.albumTracks\s*=\s*(\[.*?\]);", html, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return []


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).lower())


def track_title(track: dict) -> str:
    return clean_text(track.get("name") or track.get("title") or track.get("songName"))


def track_urls(track: dict, album_url: str) -> list[str]:
    raw = clean_text(track.get("dl_path"))
    urls = []
    if raw:
        urls.append(absolute_url(raw, album_url))
        if "/p128_cdn/" in raw:
            urls.append(absolute_url(raw.replace("/p128_cdn/", "/p320_cdn/"), album_url))
        if "/p320_cdn/" in raw:
            urls.append(absolute_url(raw.replace("/p320_cdn/", "/p128_cdn/"), album_url))
    return unique(urls)


def refresh_urls_from_album(song: RelaySong) -> list[str]:
    for page_url in unique((song.album_url, song.song_page_url, song.source_url)):
        try:
            response = cffi_requests.get(
                page_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": page_url,
                },
                impersonate="chrome124",
                timeout=REQUEST_TIMEOUT,
            )
        except Exception:
            continue
        if response.status_code != HTTPStatus.OK or "window.albumTracks" not in response.text:
            continue
        tracks = parse_album_tracks(response.text)
        if not tracks:
            continue
        matched = next((track for track in tracks if clean_text(track.get("id")) == song.id), None)
        if not matched:
            wanted = normalize_title(song.title)
            matched = next((track for track in tracks if normalize_title(track_title(track)) == wanted), None)
        urls = track_urls(matched or {}, page_url)
        if urls:
            return urls
    return []


def open_upstream(song: RelaySong, url: str, range_header: str = ""):
    headers = {
        "Accept": "audio/mpeg,audio/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": song.album_url or song.source_url or SITE_ORIGIN,
    }
    if range_header:
        headers["Range"] = range_header
    return cffi_requests.get(
        url,
        headers=headers,
        impersonate="chrome124",
        timeout=REQUEST_TIMEOUT,
        stream=True,
        allow_redirects=True,
    )


def stream_headers_from_response(response, first_chunk: bytes) -> tuple[int, dict[str, str]]:
    status = HTTPStatus.PARTIAL_CONTENT if response.status_code == HTTPStatus.PARTIAL_CONTENT else HTTPStatus.OK
    headers = {
        "Content-Type": response.headers.get("content-type") or "audio/mpeg",
        "Accept-Ranges": response.headers.get("accept-ranges") or "bytes",
        "Cache-Control": "public, max-age=3600",
        "X-Sruthi-Source": "python-relay",
    }
    content_range = response.headers.get("content-range")
    if content_range:
        headers["Content-Range"] = content_range
    content_length = clean_text(response.headers.get("content-length"))
    if content_length:
        try:
            length = int(content_length)
            headers["Content-Length"] = str(length)
        except ValueError:
            pass
    if first_chunk and not headers.get("Content-Length") and response.status_code == HTTPStatus.OK:
        # Leave transfer-length unspecified; http.server will close the response.
        pass
    return int(status), headers


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "SruthiStreamRelay/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self.send_json(
                {
                    "ok": True,
                    "duckdb": DUCKDB_PATH.exists(),
                    "sqlite": SQLITE_PATH.exists(),
                    "r2": r2_configured(),
                }
            )
            return
        match = re.match(r"^/api/stream/([^/]+)$", parsed.path)
        if match:
            if RELAY_TOKEN and self.headers.get("X-Sruthi-Relay-Token") != RELAY_TOKEN:
                self.send_json({"error": "Forbidden."}, HTTPStatus.FORBIDDEN)
                return
            song = query_catalog_song(match.group(1))
            if not song:
                self.send_json({"error": "Song not found in relay catalog."}, HTTPStatus.NOT_FOUND)
                return
            self.handle_song_stream(song)
            return
        match = re.match(r"^/api/song-status/([^/]+)$", parsed.path)
        if match:
            song_id = clean_text(match.group(1))
            cached = audio_cache_path(song_id)
            self.send_json(
                {
                    "id": song_id,
                    "cached": is_valid_audio_file(cached),
                    "r2Configured": r2_configured(),
                    "source": "python-relay",
                }
            )
            return
        self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/relay/stream":
            self.send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        if RELAY_TOKEN and self.headers.get("X-Sruthi-Relay-Token") != RELAY_TOKEN:
            self.send_json({"error": "Forbidden."}, HTTPStatus.FORBIDDEN)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            song = parse_song(payload)
        except Exception:
            self.send_json({"error": "Invalid relay payload."}, HTTPStatus.BAD_REQUEST)
            return
        if not song.id:
            self.send_json({"error": "song.id is required."}, HTTPStatus.BAD_REQUEST)
            return

        self.handle_song_stream(song)

    def handle_song_stream(self, song: RelaySong) -> None:
        if not song.id:
            self.send_json({"error": "song.id is required."}, HTTPStatus.BAD_REQUEST)
            return

        range_header = clean_text(self.headers.get("Range"))
        cached = audio_cache_path(song.id)
        if not is_valid_audio_file(cached):
            restore_from_r2(song.id, cached)
        if range_header and is_valid_audio_file(cached):
            self.stream_cached_file(cached, range_header)
            return
        if not range_header and is_valid_audio_file(cached):
            self.stream_file(cached)
            return

        urls = candidate_urls(song)
        last_reason = "no-url"
        for attempt in range(2):
            if attempt:
                urls = unique((*refresh_urls_from_album(song), *urls))
                time.sleep(0.75 + random.random())
            for url in urls:
                try:
                    if self.try_stream_upstream(song, url, range_header, cached):
                        return
                    last_reason = "not-audio"
                except BrokenPipeError:
                    return
                except Exception as exc:
                    last_reason = exc.__class__.__name__
                    continue

        self.send_json({"error": "Upstream stream unavailable.", "reason": last_reason}, HTTPStatus.BAD_GATEWAY)

    def try_stream_upstream(self, song: RelaySong, url: str, range_header: str, cache_path: Path) -> bool:
        response = open_upstream(song, url, range_header)
        if not is_audio_response(response):
            response.close()
            return False
        iterator = response.iter_content(chunk_size=128 * 1024)
        first_chunk = next(iterator, b"")
        if not is_valid_audio_bytes(first_chunk):
            response.close()
            return False

        status, headers = stream_headers_from_response(response, first_chunk)
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()

        cache_handle = None
        temp_path = None
        bytes_written = 0
        should_cache = status == HTTPStatus.OK and not range_header
        try:
            if should_cache:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = cache_path.with_suffix(f".{os.getpid()}.part")
                cache_handle = temp_path.open("wb")
            if first_chunk:
                bytes_written += len(first_chunk)
                self.wfile.write(first_chunk)
                if cache_handle:
                    cache_handle.write(first_chunk)
            for chunk in iterator:
                if not chunk:
                    continue
                bytes_written += len(chunk)
                if bytes_written > MAX_AUDIO_BYTES:
                    break
                self.wfile.write(chunk)
                if cache_handle:
                    cache_handle.write(chunk)
            if cache_handle:
                cache_handle.close()
                cache_handle = None
                if is_valid_audio_file(temp_path):
                    os.replace(temp_path, cache_path)
                    upload_to_r2_background(song.id, cache_path)
                else:
                    temp_path.unlink(missing_ok=True)
        finally:
            if cache_handle:
                cache_handle.close()
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            response.close()
        return True

    def stream_file(self, path: Path) -> None:
        size = path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("X-Sruthi-Source", "python-relay-cache")
        self.end_headers()
        with path.open("rb") as handle:
            while chunk := handle.read(128 * 1024):
                self.wfile.write(chunk)

    def stream_cached_file(self, path: Path, range_header: str) -> None:
        size = path.stat().st_size
        match = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not match:
            self.stream_file(path)
            return
        start = int(match.group(1) or "0")
        end = int(match.group(2) or str(size - 1))
        start = max(0, min(start, size - 1))
        end = max(start, min(end, size - 1))
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("X-Sruthi-Source", "python-relay-cache")
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = handle.read(min(128 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                self.wfile.write(chunk)


def main() -> None:
    CACHE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), RelayHandler)
    print(f"Sruthi stream relay listening on {LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
