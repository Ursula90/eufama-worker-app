# EUFAMA Connect

A WhatsApp-style messaging app for EUFAMA Holding: 1:1 and group chat,
photos/files, voice notes, audio/video calls, a "Buzz" nudge (same idea as
the old Yahoo! Messenger buzz), and a VIP broadcast-to-everyone feature —
plus the original EUFAMA Worker safety features (shift/GPS tracking, panic
button, photo incident reports).

## Quick demo setup

Getting a working beta in front of someone in one sitting:

1. **Start the backend** on your laptop (Option A below) — note the LAN IP
   you used for `PUBLIC_BASE_URL`.
2. **Provision 2-3 demo accounts** (one `vip`, the rest `worker`) — see
   "Provisioning a worker" below. Save each `worker_id` + `token`.
3. **Get the APK**: GitHub → this repo → **Actions** tab → the latest
   green **"Build EUFAMA Worker APK"** run → **Artifacts** section at the
   bottom → download `eufama-worker-apk`, unzip, install the `.apk` on an
   Android phone (enable "install unknown apps" for whichever app you
   transfer it through).
4. **On the phone**: open the app, tap the "EUFAMA" logo 5× fast on the
   login screen → the hidden admin screen appears → enter your laptop's
   LAN IP and port `8765` → Save. Back on the login screen, enter one
   demo account's `worker_id` + `token` → Login.
5. Repeat step 4 on a second phone (or the same phone logged out/back in
   with a different account) so there's someone to chat with.

A natural order to show someone: log in on two phones → send a text (note
it's end-to-end encrypted, not just "in transit") → send a photo → send a
voice note → hit "zzZ" (Buzz) and watch the other phone shake/vibrate →
start a video call (opens the system browser on both ends) → from the VIP
account, send a broadcast and open the live map → switch to the Safety tab
and show Start Shift / Panic.

## Architecture

```
eufama-worker-app/
├── main.py                # Kivy app entry point
├── eufama_client/         # Android client (Kivy/Python)
│   ├── screens/           # login, admin, home (tabs), chat, contacts, groups, broadcast, safety
│   ├── netclient.py       # REST client (stdlib urllib, hand-rolled multipart upload)
│   ├── ws_client.py       # background WebSocket client (chat push, presence, buzz, calls)
│   ├── effects.py         # Buzz: vibration + screen shake + sound
│   └── media_helpers.py   # camera, voice recording, opening the call page in the browser
├── buildozer.spec         # Android APK build config
├── .github/workflows/     # CI: builds the APK on every push (buildozer android debug)
└── backend/                # FastAPI server — chat, calls signaling, safety endpoints
    ├── app/
    │   ├── models.py, schemas.py, database.py
    │   ├── routers/        # auth, admin, users, conversations, messages, broadcast, buzz, calls, safety, ws
    │   └── static/         # call.html + call.js — the WebRTC calling client
    └── requirements.txt
```

### Why calls open in the browser, not inside the app

Kivy has no mature WebRTC binding. Rather than half-implement audio/video
calling natively (and ship something unreliable), the "📞"/"🎥" buttons ask
the backend to start a call session and then open a link to
`backend/app/static/call.html` in the system browser — Chrome's WebRTC
stack is what actually carries the audio/video. The backend only relays
signaling (SDP offers/answers, ICE candidates) over a WebSocket; media
never touches the server. This is a standard, robust pattern and avoids
depending on unmaintained Kivy WebRTC bindings.

Group calls use a full mesh (every participant connects directly to
every other one). That's simple and works well for small groups but its
bandwidth/CPU cost grows with the square of the participant count — see
**Roadmap** below for the cap and the upgrade path.

## Running the backend

### Option A — Docker (fastest for a demo)

```bash
cd backend
PUBLIC_BASE_URL="http://<your-machine's-LAN-IP>:8765" docker compose up -d --build
```

`<your-machine's-LAN-IP>` must be an address phones on the same network can
actually reach (e.g. `192.168.1.42`) — not `localhost`, since the APK runs
on a different device than the backend. Find yours with `ipconfig getifaddr en0`
(macOS) or `hostname -I` (Linux). Data persists in a Docker volume across
restarts. Stop with `docker compose down` (add `-v` to also wipe the data).

### Option B — plain Python venv

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export ADMIN_API_KEY="choose-a-strong-key"
export SECRET_KEY="choose-a-strong-random-key"
export PUBLIC_BASE_URL="http://<server-ip>:8765"   # must be reachable from workers' phones

uvicorn app.main:app --host 0.0.0.0 --port 8765
```

A quick end-to-end check (creates test users, sends messages, buzzes,
broadcasts, starts a call, exercises the safety endpoints and a live
WebSocket push) lives in `backend/smoke_test.py`:

```bash
python smoke_test.py
```

### Provisioning a worker (done once per phone, from a trusted machine)

```bash
curl -X POST http://<server-ip>:8765/admin/users \
  -H "X-Admin-Key: $ADMIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"worker_id": "ion1", "display_name": "Ion Popescu", "role": "worker"}'
```

The response includes a `token` — shown once. Enter it, together with the
`worker_id`, on the phone's login screen (server IP/port are set first via
the hidden admin screen: tap the EUFAMA logo 5× on the login screen).

Use `"role": "vip"` (or `"admin"`) for accounts that should see the
⭐ Broadcast tab and be able to message every worker at once.

## Building the APK

Unchanged from the original project — push to `main`/`master` and the
GitHub Action in `.github/workflows/build.yml` runs `buildozer android
debug` and uploads the APK as a build artifact. Locally: `buildozer
android debug` from the repo root (requires the Android SDK/NDK; buildozer
downloads them on first run).

## Feature summary

| Feature | Where |
|---|---|
| 1:1 and group text chat | `POST/GET /conversations`, `POST/GET /conversations/{id}/messages` |
| Photos, files, voice notes | same messages endpoint, multipart upload, served from `/media` |
| Presence (online/last seen) | `/ws/app` connection tracking |
| Buzz (Yahoo-style nudge) | `POST /buzz` → `/ws/app` event → vibration + shake + sound |
| VIP broadcast to everyone | `POST /broadcast`, VIP/admin-only |
| Audio/video calls | `POST /conversations/{id}/calls` → browser page at `/static/call.html`, signaled over `/ws/call/{id}` |
| Shift tracking, GPS ping, panic, incident report | `/shift/*`, `/ping`, `/sos`, `/resolve`, `/incident` (unchanged client contract from the original app) |

## Roadmap / known limitations

- **Group call scale.** Mesh WebRTC is capped at `MAX_MESH_CALL_PARTICIPANTS`
  (default 6, see `backend/app/config.py`). Beyond that, a proper SFU
  (e.g. [LiveKit](https://livekit.io) or
  [mediasoup](https://mediasoup.org)) is needed — the signaling design
  here (one JSON envelope per offer/answer/candidate) carries over to an
  SFU with moderate changes to `ws.py` and `call.js`.
- **NAT traversal.** `call.js` only configures a public Google STUN
  server. On networks with symmetric NAT/restrictive firewalls, add a
  TURN server (e.g. [coturn](https://github.com/coturn/coturn)) to
  `ICE_SERVERS` in `backend/app/static/call.js`.
- **Token hashing.** Uses HMAC-SHA256 with a server secret, consistent
  with the project's existing dependency-light style. For a larger
  deployment, moving to bcrypt/argon2 (via `passlib`) is a small,
  contained change in `backend/app/auth.py`.
- **End-to-end encryption.** Messages are encrypted in transit (once
  deployed behind HTTPS/WSS — see below) but not end-to-end encrypted at
  rest the way WhatsApp's Signal protocol is. Out of scope for this pass;
  flagging so it's a conscious decision, not an oversight.
- **Deploy behind HTTPS/WSS.** `getUserMedia` (mic/camera access) is only
  allowed by browsers on secure origins. Put the backend behind a
  reverse proxy (nginx/Caddy) with TLS before relying on calls outside a
  trusted LAN, and update `PUBLIC_BASE_URL` accordingly.
- **Voice notes on Android** use `plyer.audio`, which records to
  `.3gp`. It's device-dependent — test on the actual target phones before
  wide rollout.
