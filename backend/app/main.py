import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import MEDIA_DIR
from .database import Base, engine
from .routers import admin, broadcast, buzz, calls, conversations, messages, safety, users, ws
from .routers import auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="EUFAMA Connect")

# Internal company tool served over the plant/company network — CORS is
# left open so the call page (served from this same origin) and any
# future admin dashboard can talk to the API without extra config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(broadcast.router)
app.include_router(buzz.router)
app.include_router(calls.router)
app.include_router(safety.router)
app.include_router(ws.router)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "service": "eufama-connect"}
