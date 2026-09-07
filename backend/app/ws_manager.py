"""
Two independent connection pools:

- `app` sockets: one per logged-in user (possibly several devices/tabs).
  Used to push chat messages, presence, buzz and incoming-call
  notifications in real time.
- `call` sockets: one per participant *inside a specific call room*.
  Used purely to relay WebRTC signaling (offer/answer/ICE) between the
  browser tabs taking part in that call — the server never looks at the
  media, only forwards small JSON envelopes.
"""

import asyncio
import json
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket


class AppConnectionManager:
    def __init__(self):
        self._by_user: Dict[int, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._by_user[user_id].add(ws)

    async def disconnect(self, user_id: int, ws: WebSocket):
        async with self._lock:
            self._by_user[user_id].discard(ws)
            if not self._by_user[user_id]:
                del self._by_user[user_id]

    def is_online(self, user_id: int) -> bool:
        return bool(self._by_user.get(user_id))

    async def send_to_user(self, user_id: int, payload: dict):
        dead = []
        for ws in list(self._by_user.get(user_id, ())):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)

    async def send_to_users(self, user_ids, payload: dict):
        for uid in user_ids:
            await self.send_to_user(uid, payload)


class CallConnectionManager:
    def __init__(self):
        # call_id -> { user_id -> websocket }
        self._rooms: Dict[str, Dict[int, WebSocket]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def join(self, call_id: str, user_id: int, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._rooms[call_id][user_id] = ws

    async def leave(self, call_id: str, user_id: int):
        async with self._lock:
            room = self._rooms.get(call_id)
            if room and user_id in room:
                del room[user_id]
            if room is not None and not room:
                del self._rooms[call_id]

    def participants(self, call_id: str):
        return list(self._rooms.get(call_id, {}).keys())

    async def relay(self, call_id: str, from_user: int, to_user: int, payload: dict):
        room = self._rooms.get(call_id, {})
        ws = room.get(to_user)
        if ws is None:
            return
        try:
            await ws.send_text(json.dumps({**payload, "from": from_user}))
        except Exception:
            pass

    async def broadcast(self, call_id: str, from_user: int, payload: dict):
        room = self._rooms.get(call_id, {})
        for uid, ws in list(room.items()):
            if uid == from_user:
                continue
            try:
                await ws.send_text(json.dumps({**payload, "from": from_user}))
            except Exception:
                pass


app_manager = AppConnectionManager()
call_manager = CallConnectionManager()
