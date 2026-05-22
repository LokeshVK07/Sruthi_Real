# Sruthi Playback Relay

Cloudflare Workers can serve cached audio from R2, but they cannot use
`curl_cffi` browser impersonation when MassTamilan challenges uncached audio.
For uncached songs, deploy `tools/stream_relay.py` on a Python host and point
the Worker at it with `PYTHON_STREAM_ORIGIN`.

## Run Locally

```bash
python -m pip install -r requirements-relay.txt
PORT=8088 python tools/stream_relay.py
```

Health check:

```bash
curl http://127.0.0.1:8088/healthz
```

## Production Environment

Set these on the Python host:

```bash
PORT=8088
SRUTHI_RELAY_TOKEN=<strong-random-token>
SRUTHI_RELAY_AUDIO_CACHE=.cache/relay-audio
SRUTHI_DUCKDB_PATH=data/sruthi.duckdb
SRUTHI_SQLITE_PATH=data/sruthi.db
```

If R2 credentials are also configured on the Python host, the relay follows
the isaibox shared-cache flow directly:

```bash
R2_ACCOUNT_ID=<cloudflare-account-id>
R2_BUCKET_NAME=sruthi-audio-cache
R2_ACCESS_KEY_ID=<r2-access-key>
R2_SECRET_ACCESS_KEY=<r2-secret-key>
# Optional when you want to override the default endpoint:
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
```

Then set these on the Cloudflare Worker:

```bash
PYTHON_STREAM_ORIGIN=https://your-python-relay.example.com
PYTHON_STREAM_RELAY_TOKEN=<same-strong-random-token>
```

For the repository GitHub Action, use:

```text
Repository variable: SRUTHI_PYTHON_STREAM_ORIGIN=https://your-python-relay.example.com
Repository secret:   SRUTHI_PYTHON_STREAM_RELAY_TOKEN=<same-strong-random-token>
```

The Worker still uses this order:

```text
Edge cache -> R2 audio cache -> stored DB URL -> fresh album tokens -> Python relay
```

The relay itself uses this order:

```text
DuckDB/SQLite song lookup
-> local .cache/relay-audio/<song_id>.mp3
-> R2 audio/<song_id>.mp3 restore
-> upstream MassTamilan with curl_cffi Chrome impersonation
-> save local MP3
-> upload successful MP3 to R2 in the background
```

The Worker can still send song rows to `POST /api/relay/stream`, but the relay
also supports direct `GET /api/stream/<song_id>` lookups from DuckDB/SQLite.
