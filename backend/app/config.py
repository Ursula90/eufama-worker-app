"""
EUFAMA Connect — backend configuration.

All values are overridable via environment variables so the same code
runs unmodified in dev and in production (systemd/docker/etc).
"""

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./eufama.db")

# Used to derive token hashes (HMAC) and short-lived call tokens.
# MUST be overridden in production via the SECRET_KEY env var.
SECRET_KEY = os.environ.get("SECRET_KEY", "eufama-dev-secret-change-me")

# Master key required to call the /admin/* provisioning endpoints
# (create worker accounts, issue tokens, promote to VIP/admin).
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "eufama-admin-change-me")

MEDIA_DIR = os.environ.get(
    "MEDIA_DIR", os.path.join(os.path.dirname(__file__), "..", "media")
)
os.makedirs(MEDIA_DIR, exist_ok=True)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))

# Base URL the server is reachable at from workers' phones — used to build
# the link opened in the browser for audio/video calls.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8765")

# Small groups only: full-mesh WebRTC (every participant connects directly
# to every other one) does not scale past a handful of people. Beyond this
# a proper SFU (e.g. mediasoup/LiveKit) is needed — see README roadmap.
MAX_MESH_CALL_PARTICIPANTS = int(os.environ.get("MAX_MESH_CALL_PARTICIPANTS", "6"))

CALL_TOKEN_TTL_SECONDS = 60 * 60 * 4  # 4h, enough for a work shift

# Minimum seconds between two buzzes sent to the same person (anti-spam).
BUZZ_COOLDOWN_SECONDS = int(os.environ.get("BUZZ_COOLDOWN_SECONDS", "5"))
