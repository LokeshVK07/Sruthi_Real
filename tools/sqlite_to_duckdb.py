#!/usr/bin/env python3
"""Build the canonical Sruthi DuckDB catalog from the local SQLite catalog."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = ROOT / "data" / "sruthi.db"
DEFAULT_DUCKDB = ROOT / "data" / "sruthi.duckdb"
TABLES = ("app_meta", "albums", "songs", "download_links")
BATCH_SIZE = 2_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Sruthi SQLite catalog to DuckDB.")
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--duckdb", type=Path, default=DEFAULT_DUCKDB)
    parser.add_argument("--manifest", type=Path, default=None)
    return parser.parse_args()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def duckdb_type(sqlite_type: str) -> str:
    normalized = (sqlite_type or "").strip().upper()
    if "INT" in normalized:
        return "BIGINT"
    if any(token in normalized for token in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE"
    if "BLOB" in normalized:
        return "BLOB"
    if any(token in normalized for token in ("NUM", "DEC", "BOOL")):
        return "DOUBLE"
    return "VARCHAR"


def table_columns(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    rows = connection.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
    if not rows:
        raise RuntimeError(f"Missing required SQLite table: {table}")
    return rows


def create_duckdb_table(connection: duckdb.DuckDBPyConnection, table: str, columns: list[sqlite3.Row]) -> None:
    definitions = []
    for column in columns:
        name = quote_identifier(column["name"])
        definitions.append(f"{name} {duckdb_type(column['type'])}")
    connection.execute(f"CREATE TABLE {quote_identifier(table)} ({', '.join(definitions)})")


def copy_table(sqlite_connection: sqlite3.Connection, duck_connection: duckdb.DuckDBPyConnection, table: str) -> int:
    columns = table_columns(sqlite_connection, table)
    create_duckdb_table(duck_connection, table, columns)

    column_names = [column["name"] for column in columns]
    select_columns = ", ".join(quote_identifier(column) for column in column_names)
    insert_columns = ", ".join(quote_identifier(column) for column in column_names)
    placeholders = ", ".join("?" for _ in column_names)
    cursor = sqlite_connection.execute(f"SELECT {select_columns} FROM {quote_identifier(table)}")

    total = 0
    while True:
        batch = cursor.fetchmany(BATCH_SIZE)
        if not batch:
            break
        duck_connection.executemany(
            f"INSERT INTO {quote_identifier(table)} ({insert_columns}) VALUES ({placeholders})",
            [tuple(row) for row in batch],
        )
        total += len(batch)
    return total


def create_indexes(connection: duckdb.DuckDBPyConnection) -> None:
    statements = (
        "CREATE INDEX idx_duckdb_albums_url ON albums(url)",
        "CREATE INDEX idx_duckdb_songs_id ON songs(id)",
        "CREATE INDEX idx_duckdb_songs_album_url ON songs(album_url)",
        "CREATE INDEX idx_duckdb_songs_movie_title ON songs(movie, title)",
        "CREATE INDEX idx_duckdb_songs_year ON songs(year)",
        "CREATE INDEX idx_duckdb_songs_link_status ON songs(link_status)",
    )
    for statement in statements:
        try:
            connection.execute(statement)
        except Exception:
            # Indexes are an optimization only; keep the catalog build resilient.
            pass


def convert(sqlite_path: Path, duckdb_path: Path) -> dict:
    if not sqlite_path.exists():
        raise RuntimeError(f"SQLite catalog not found: {sqlite_path}")
    if sqlite_path.stat().st_size < 4096:
        raise RuntimeError(f"SQLite catalog is unexpectedly small: {sqlite_path}")

    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    if duckdb_path.exists():
        duckdb_path.unlink()

    sqlite_connection = sqlite3.connect(sqlite_path)
    sqlite_connection.row_factory = sqlite3.Row
    try:
        quick_check = sqlite_connection.execute("PRAGMA quick_check").fetchone()
        if quick_check and quick_check[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {quick_check[0]}")

        duck_connection = duckdb.connect(str(duckdb_path))
        try:
            counts = {}
            for table in TABLES:
                counts[table] = copy_table(sqlite_connection, duck_connection, table)
            create_indexes(duck_connection)
            duck_connection.execute(
                """
                CREATE OR REPLACE VIEW playable_songs AS
                SELECT *
                FROM songs
                WHERE COALESCE(NULLIF(audio_128_url, ''), NULLIF(remote_audio_128_url, ''),
                               NULLIF(audio_320_url, ''), NULLIF(remote_audio_320_url, ''),
                               NULLIF(audio_url, ''), '') <> ''
                """
            )
            duck_connection.execute("CHECKPOINT")
        finally:
            duck_connection.close()
    finally:
        sqlite_connection.close()

    if not duckdb_path.exists() or duckdb_path.stat().st_size < 4096:
        raise RuntimeError(f"DuckDB catalog was not created correctly: {duckdb_path}")

    return {
        "sqlite": str(sqlite_path),
        "duckdb": str(duckdb_path),
        "duckdbBytes": duckdb_path.stat().st_size,
        "counts": counts,
    }


def main() -> int:
    args = parse_args()
    manifest = convert(args.sqlite.resolve(), args.duckdb.resolve())
    manifest_path = args.manifest
    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, **manifest}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
