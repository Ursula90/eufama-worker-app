"""Quick manual smoke test for the EUFAMA Connect backend — not part of
the app, just a throwaway script to exercise the main REST flows plus
one WebSocket round trip before committing. Run with the venv active:

    python smoke_test.py
"""

import json
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
os.environ["ADMIN_API_KEY"] = "test-admin-key"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
ADMIN = {"X-Admin-Key": "test-admin-key"}


def check(label, cond):
    print(("OK  " if cond else "FAIL"), label)
    assert cond, label


# 1. provision two workers + one VIP
r = client.post("/admin/users", json={"worker_id": "w1", "display_name": "Ion Popescu", "role": "worker"}, headers=ADMIN)
check("create worker w1", r.status_code == 200)
w1_token = r.json()["token"]

r = client.post("/admin/users", json={"worker_id": "w2", "display_name": "Maria Ionescu", "role": "worker"}, headers=ADMIN)
check("create worker w2", r.status_code == 200)
w2_token = r.json()["token"]

r = client.post("/admin/users", json={"worker_id": "boss", "display_name": "Valy", "role": "vip"}, headers=ADMIN)
check("create VIP", r.status_code == 200)
boss_token = r.json()["token"]

H1 = {"X-Worker-Id": "w1", "X-Worker-Token": w1_token}
H2 = {"X-Worker-Id": "w2", "X-Worker-Token": w2_token}
HB = {"X-Worker-Id": "boss", "X-Worker-Token": boss_token}

# 2. login
r = client.post("/auth/login", json={"worker_id": "w1", "token": w1_token})
check("login w1", r.status_code == 200 and r.json()["user"]["worker_id"] == "w1")

r = client.post("/auth/login", json={"worker_id": "w1", "token": "wrong-token"})
check("login rejects bad token", r.status_code == 401)

# 3. contacts
r = client.get("/users", headers=H1)
check("w1 sees 2 contacts", r.status_code == 200 and len(r.json()) == 2)
w2_id = next(u["id"] for u in r.json() if u["worker_id"] == "w2")
w1_id = client.get("/users/me", headers=H1).json()["id"]
boss_id = client.get("/users/me", headers=HB).json()["id"]

# 4. direct conversation + text message
r = client.post("/conversations", json={"type": "direct", "member_ids": [w2_id]}, headers=H1)
check("create direct convo", r.status_code == 200)
convo_id = r.json()["id"]

r2 = client.post("/conversations", json={"type": "direct", "member_ids": [w1_id]}, headers=H2)
check("direct convo is deduped both ways", r2.json()["id"] == convo_id)

r = client.post(f"/conversations/{convo_id}/messages", data={"type": "text", "body": "Salut, ma auzi?"}, headers=H1)
check("send text message", r.status_code == 200 and r.json()["body"] == "Salut, ma auzi?")

r = client.get(f"/conversations/{convo_id}/messages", headers=H2)
check("w2 can read the message", r.status_code == 200 and len(r.json()) == 1)

# 5. image upload message
r = client.post(
    f"/conversations/{convo_id}/messages",
    data={"type": "image"},
    files={"file": ("photo.jpg", b"\xff\xd8\xff fake jpeg bytes", "image/jpeg")},
    headers=H1,
)
check("send image message", r.status_code == 200 and r.json()["media_url"] is not None)

# 6. group chat
r = client.post("/conversations", json={"type": "group", "member_ids": [w2_id, boss_id], "name": "Santier A"}, headers=H1)
check("create group", r.status_code == 200 and len(r.json()["member_ids"]) == 3)
group_id = r.json()["id"]
r = client.post(f"/conversations/{group_id}/messages", data={"type": "text", "body": "Grup activ"}, headers=H2)
check("post to group", r.status_code == 200)

# 7. buzz
r = client.post("/buzz", json={"conversation_id": convo_id}, headers=H1)
check("buzz sent", r.status_code == 200 and w2_id in r.json()["sent_to"])
r = client.post("/buzz", json={"conversation_id": convo_id}, headers=H1)
check("buzz cooldown throttles immediate repeat", r.status_code == 200 and w2_id in r.json()["throttled"])

# 8. VIP broadcast
r = client.post("/broadcast", json={"body": "Mesaj important pentru toata echipa"}, headers=HB)
check("broadcast fanned out to 2 workers", r.status_code == 200 and len(r.json()) == 2)

r = client.post("/broadcast", json={"body": "nu am voie"}, headers=H1)
check("non-VIP cannot broadcast", r.status_code == 403)

# 9. calls
r = client.post(f"/conversations/{convo_id}/calls", json={"call_type": "video"}, headers=H1)
check("start call", r.status_code == 200 and "join_url" in r.json())
call_id = r.json()["call_id"]

r = client.post(f"/conversations/{convo_id}/calls/{call_id}/end", headers=H1)
check("end call", r.status_code == 200)

# 10. safety endpoints (legacy client contract: worker_id/token in JSON body)
r = client.post("/shift/start", json={"worker_id": "w1", "token": w1_token, "lat": 38.5, "lon": -8.8})
check("shift start", r.status_code == 200)
r = client.post("/ping", json={"worker_id": "w1", "token": w1_token, "lat": 38.5, "lon": -8.8, "battery": 90})
check("gps ping", r.status_code == 200)
r = client.post("/sos", json={"worker_id": "w1", "token": w1_token, "lat": 38.5, "lon": -8.8})
check("sos trigger", r.status_code == 200)

r = client.get("/dispatch/shifts")
check("dispatch requires a token (query param missing)", r.status_code == 422)
r = client.get("/dispatch/shifts?token=garbage")
check("dispatch rejects invalid token", r.status_code == 401)
r = client.post("/admin/map-token", headers=H1)
check("worker cannot mint a map token", r.status_code == 403)
r = client.post("/admin/map-token", headers=HB)
check("VIP can mint a map token", r.status_code == 200 and "map_url" in r.json())
map_token = r.json()["token"]
r = client.get(f"/dispatch/shifts?token={map_token}")
check("dispatch view (with valid admin token) shows sos", r.status_code == 200 and r.json()["w1"]["sos"] is True)

# 11. websocket round trip: w2 gets pushed the message w1 sends live
with client.websocket_connect(f"/ws/app?worker_id=w2&token={w2_token}") as ws2:
    r = client.post(f"/conversations/{convo_id}/messages", data={"type": "text", "body": "live push test"}, headers=H1)
    check("send while w2 connected", r.status_code == 200)
    event = ws2.receive_json()
    check("w2 received live push", event["type"] == "message" and event["message"]["body"] == "live push test")

# 12. end-to-end encryption plumbing (server never decrypts — just stores/relays opaque blobs)
r = client.post("/auth/login", json={"worker_id": "w1", "token": w1_token, "public_key": "fake-base64-pubkey-w1"})
check("login uploads public key", r.status_code == 200 and r.json()["user"]["public_key"] == "fake-base64-pubkey-w1")
r = client.get("/users", headers=H2)
check("contacts expose public_key", any(u["public_key"] == "fake-base64-pubkey-w1" for u in r.json()))

r = client.post(
    f"/conversations/{convo_id}/messages",
    data={"type": "text", "body": "ZmFrZS1jaXBoZXJ0ZXh0", "encrypted": "true", "enc_scheme": "direct"},
    headers=H1,
)
check("send direct-encrypted message", r.status_code == 200 and r.json()["encrypted"] is True)

r = client.post(
    f"/conversations/{group_id}/messages",
    data={
        "type": "text", "body": "ZmFrZS1ncm91cC1jaXBoZXJ0ZXh0", "encrypted": "true", "enc_scheme": "group",
        "enc_keys": json.dumps({str(w2_id): "sealed-for-w2", str(boss_id): "sealed-for-boss"}),
    },
    headers=H1,
)
check("send group-encrypted message", r.status_code == 200 and r.json()["enc_keys"][str(w2_id)] == "sealed-for-w2")

r = client.post(
    f"/conversations/{convo_id}/messages",
    data={"type": "text", "encrypted": "true", "enc_scheme": "group"},  # missing enc_keys
    headers=H1,
)
check("group-encrypted message without enc_keys is rejected", r.status_code == 400)

r = client.post(
    "/broadcast",
    json={"encrypted": True, "recipients": [
        {"user_id": w1_id, "body": "cipher-for-w1"},
        {"user_id": w2_id, "body": "cipher-for-w2"},
    ]},
    headers=HB,
)
check("encrypted broadcast fans out per-recipient ciphertexts", r.status_code == 200 and len(r.json()) == 2
      and {m["sender_id"] for m in r.json()} == {boss_id})

print("\nAll smoke checks passed.")
