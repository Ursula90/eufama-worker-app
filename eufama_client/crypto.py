"""End-to-end encryption for text messages (PyNaCl / libsodium bindings).

Each device generates its own X25519 keypair the first time it's needed
(see `ensure_keypair`). The private key never leaves the device — it's
kept in the same local config file the login token already lives in (see
README for the matching caveat: this is app-private storage, not an
OS keystore). The public key is uploaded to the server at login so other
clients can encrypt to it; the server only ever stores/relays ciphertext
for encrypted messages, never plaintext.

Trust model: trust-on-first-use. There's no "scan to verify" / safety
number UI yet (documented roadmap item), so this protects message
content from a passive server operator or network eavesdropper, but not
from an active attacker who controls the server at the moment two people
first exchange keys. That's the same starting point most messengers had
before they shipped key verification — called out here rather than
oversold as Signal-grade.

Two schemes, matching the backend's Message.enc_scheme:
  - "direct": nacl.public.Box between exactly two people. Box is
    symmetric in the Diffie-Hellman sense — Box(my_priv, their_pub) can
    decrypt anything either side encrypted with that same key pair — so
    the single "other member" of a direct conversation is all that's
    needed to decrypt any message in it, sent by either party.
  - "group": a random per-message key (nacl.secret.SecretBox) encrypts
    the text once; that key is then individually sealed
    (nacl.public.SealedBox) for every member's public key, including the
    sender's own, so everyone — and the sender, on re-fetching history —
    can unwrap their own copy and decrypt.
"""

import base64

from nacl.public import Box, PrivateKey, PublicKey, SealedBox
from nacl.secret import SecretBox
from nacl.utils import random as nacl_random

from .config import load_config, update_config


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text)


def ensure_keypair() -> str:
    """Returns this device's base64 public key, generating + persisting a
    keypair on first call."""
    cfg = load_config()
    if cfg.get("privkey") and cfg.get("pubkey"):
        return cfg["pubkey"]

    sk = PrivateKey.generate()
    update_config(privkey=_b64e(bytes(sk)), pubkey=_b64e(bytes(sk.public_key)))
    return _b64e(bytes(sk.public_key))


def my_public_key() -> str | None:
    return load_config().get("pubkey")


def _my_private_key() -> PrivateKey:
    privkey_b64 = load_config().get("privkey")
    if not privkey_b64:
        raise RuntimeError("no local keypair — call ensure_keypair() first")
    return PrivateKey(_b64d(privkey_b64))


def encrypt_direct(plaintext: str, their_pubkey_b64: str) -> str:
    box = Box(_my_private_key(), PublicKey(_b64d(their_pubkey_b64)))
    return _b64e(bytes(box.encrypt(plaintext.encode("utf-8"))))


def decrypt_direct(ciphertext_b64: str, other_pubkey_b64: str) -> str | None:
    try:
        box = Box(_my_private_key(), PublicKey(_b64d(other_pubkey_b64)))
        return box.decrypt(_b64d(ciphertext_b64)).decode("utf-8")
    except Exception:
        return None


def encrypt_group(plaintext: str, member_pubkeys: dict) -> tuple[str, dict]:
    """member_pubkeys: {user_id: base64_pubkey}, should include the
    sender's own id/pubkey so they can decrypt their own sent history.
    Returns (body_b64, {user_id: sealed_key_b64})."""
    key = nacl_random(SecretBox.KEY_SIZE)
    ciphertext = SecretBox(key).encrypt(plaintext.encode("utf-8"))
    body_b64 = _b64e(bytes(ciphertext))

    sealed_keys = {}
    for user_id, pubkey_b64 in member_pubkeys.items():
        sealed = SealedBox(PublicKey(_b64d(pubkey_b64))).encrypt(key)
        sealed_keys[str(user_id)] = _b64e(sealed)
    return body_b64, sealed_keys


def decrypt_group(body_b64: str, my_sealed_key_b64: str) -> str | None:
    try:
        key = SealedBox(_my_private_key()).decrypt(_b64d(my_sealed_key_b64))
        return SecretBox(key).decrypt(_b64d(body_b64)).decode("utf-8")
    except Exception:
        return None
