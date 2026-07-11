# TranscriberServer

Optional remote transcription server for Transkribator. The desktop app works fully offline on its own; this server is only useful if you want to offload transcription to another (faster) machine on your network.

## Run

```bash
pip install -r requirements.txt
set TRANSCRIBER_API_KEY=<generate-a-long-random-key>
python server.py
```

The server binds to `127.0.0.1:8000` by default. All endpoints except `/health` require the `X-API-Key` header.

## Client configuration

On the client machine set:

```bash
set TRANSKRIBATOR_SERVERS=http://<server-host>:8000
set TRANSCRIBER_API_KEY=<same-key>
```

## Security notes

- Traffic is plain HTTP: the API key and your audio are visible to anything on the path. Only expose the server over a trusted network — a Tailscale/WireGuard address is the recommended way to reach it remotely.
- Do NOT publish the port through public tunnel relays (serveo, ngrok and similar): the relay operator sees your key and audio, and binding to `127.0.0.1` gives no protection once a tunnel forwards the port.
- `uploads/` and `results/` may contain recorded speech and transcripts; they are gitignored — keep it that way.
