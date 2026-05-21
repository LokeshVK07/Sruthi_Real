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

The relay is only the final fallback. Successful full relay responses are saved
back into R2 by the Worker, so future plays avoid MassTamilan again.
