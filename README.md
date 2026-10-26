# EUFAMA Connect

A WhatsApp-style messaging app for EUFAMA Holding: 1:1 and group chat
(end-to-end encrypted text), photos/files, voice notes, audio/video calls, a
"Buzz" nudge (same idea as the old Yahoo! Messenger buzz), a VIP
broadcast-to-everyone feature, local notifications for messages/buzzes/calls
arriving while the app is backgrounded, and a live admin map of every
worker's GPS position — plus the original EUFAMA Worker safety features
(shift/GPS tracking, panic button, photo incident reports).

## Quick demo setup

Getting a working beta in front of someone in one sitting:

1. **Start the backend** on your laptop (Option A below) — note the LAN IP
   you used for `PUBLIC_BASE_URL`.
2. **Provision demo accounts** — the fastest way is the included script:
   ```bash
   cd backend
   ADMIN_API_KEY=<same value you ran docker compose with> BASE_URL=http://<your-LAN-IP>:8765 ./provision_demo.sh
   ```
   It creates one VIP account ("Valy") and two workers ("Ion Popescu",
   "Maria Ionescu") and prints each one's `worker_id` + `token`. Save
   them — tokens are shown once. (To provision a single custom account
   instead, see "Provisioning a worker" below.)
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
│   ├── crypto.py          # PyNaCl E2E encryption (direct Box + group SecretBox/SealedBox)
│   ├── notifications.py   # local notifications for messages/buzz/calls while backgrounded
│   ├── effects.py         # Buzz: vibration + screen shake + sound
│   └── media_helpers.py   # camera, voice recording, opening the call/map pages in the browser
├── buildozer.spec         # Android APK build config
├── .github/workflows/     # CI: builds the APK on every push (buildozer android debug)
└── backend/                # FastAPI server — chat, calls signaling, safety endpoints
    ├── app/
    │   ├── models.py, schemas.py, database.py
    │   ├── call_tokens.py, admin_tokens.py  # short-lived tokens for the call/map browser pages
    │   ├── routers/        # auth, admin, users, conversations, messages, broadcast, buzz, calls, safety, ws
    │   └── static/         # call.html/js (WebRTC) + map.html/js (live admin map)
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

### End-to-end encryption (text messages)

Each device generates its own X25519 keypair on first login (`eufama_client/crypto.py`)
and uploads only the *public* key; the private key never leaves the phone.
The server stores/relays ciphertext for encrypted messages and never sees
the plaintext:

- **Direct chats** use `nacl.public.Box` between the two participants.
- **Group chats and VIP broadcasts** use a random per-message key
  (`nacl.secret.SecretBox`) to encrypt the text once, then that key is
  individually sealed (`nacl.public.SealedBox`) to every member's public
  key — including the sender's own, so they can still read their sent
  history after re-fetching it.

If any participant hasn't logged in since this feature shipped (no public
key on file yet), the client falls back to sending that one message in
plaintext rather than failing to send — the UI doesn't currently flag this
fallback to the user, which is a documented gap, not a silent trap: the
message still only goes to the same people it always would.

**Trust model — read this before calling it "WhatsApp-grade":** this is
trust-on-first-use, with no safety-number/key-verification UI yet. It stops
a passive server operator or network eavesdropper from reading message
content, which is the main thing asked for, but not an active attacker who
controls the server at the exact moment two people first exchange keys.
Photos, files and voice notes are **not** encrypted in this pass — see
Roadmap.

### Local notifications

While the app is backgrounded (another app in front, screen off but the
process still alive), incoming messages, buzzes, calls and SOS alerts post
a local Android notification (`eufama_client/notifications.py`, via
`plyer.notification`). Encrypted message previews show "🔒 Mesaj criptat"
rather than the decrypted text, matching most messengers' lock-screen
behavior. See Roadmap for what this does and doesn't cover.

### Admin live map

VIP/admin accounts get a "📍 Hartă live" button (on the Broadcast tab) that
opens a browser page plotting every worker's last known GPS position —
OpenStreetMap tiles via Leaflet, no API key needed. It polls the existing
`/dispatch/shifts` read-model, now gated behind a short-lived map token
(`POST /admin/map-token`) instead of being open to anyone who finds the
URL, since it leaks live GPS positions. SOS workers show as a pulsing red
marker.

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
| E2E encrypted text (direct, group, broadcast) | `eufama_client/crypto.py` (PyNaCl); server stores/relays ciphertext only |
| Local notifications while backgrounded | `eufama_client/notifications.py`, driven by `App.on_pause`/`on_resume` |
| Admin live map (GPS of every worker) | `POST /admin/map-token` → browser page at `/static/map.html`, polls `/dispatch/shifts` |
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
- **E2E encryption covers text only.** Photos, files and voice notes are
  uploaded and stored unencrypted. Encrypting them means the client
  encrypting the file bytes with the same per-message/per-conversation key
  before upload and decrypting after download — a real change to
  `media_helpers.py`, `chat_detail.py`'s upload/render paths, and the
  `/media` static serving (which currently just serves plain files).
- **No key verification UI.** There's no "scan to verify" / safety-number
  screen, so the trust model is trust-on-first-use (see above) rather than
  verified end-to-end security. Worth adding before relying on this
  against a genuinely adversarial network operator.
- **Private keys live in the same app-private config file as the login
  token** (`eufama_client/config.py`), not an OS keystore. Consistent with
  this project's existing token-storage posture, called out again here
  since it's now protecting message content too.
- **Local notifications only, not Firebase Cloud Messaging.** They fire
  while the EUFAMA Connect process is still alive in the background —
  typically true right after the user switches apps or the screen turns
  off. They will **not** wake the app from a fully killed or doze-
  suspended state; that needs real push (FCM), which requires a Firebase
  project only the account holder (not this assistant) can create. Once
  you have one, the integration point is `eufama_client/notifications.py`
  plus a `services =` entry in `buildozer.spec` for a background p4a
  service.
- **No in-app "other chat" banner.** Local notifications are suppressed
  whenever the app is in the foreground (`EufamaConnectApp.in_foreground`),
  including for messages in a *different* conversation than the one
  currently open — there's no lightweight in-app toast for that case yet,
  so such messages are only visible once you open that chat or the Chats
  tab refreshes.
- **Deploy behind HTTPS/WSS.** `getUserMedia` (mic/camera access) is only
  allowed by browsers on secure origins. Put the backend behind a
  reverse proxy (nginx/Caddy) with TLS before relying on calls outside a
  trusted LAN, and update `PUBLIC_BASE_URL` accordingly.
- **Voice notes on Android** use `plyer.audio`, which records to
  `.3gp`. It's device-dependent — test on the actual target phones before
  wide rollout.
