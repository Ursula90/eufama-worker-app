"""REST client for the EUFAMA Connect backend.

Kept dependency-free (stdlib urllib only, like the original app) except
for multipart uploads, which are hand-rolled below for the same reason —
adding `requests` just to build one multipart body isn't worth the extra
recipe weight in a buildozer/p4a build.
"""

import io
import json
import mimetypes
import os
import uuid
import urllib.error
import urllib.request

from .config import load_config


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"[{status}] {message}")


def base_url(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    return f"http://{cfg.get('server_ip')}:{cfg.get('server_port', 8765)}"


def _auth_headers(cfg: dict) -> dict:
    return {"X-Worker-Id": cfg.get("worker_id", ""), "X-Worker-Token": cfg.get("token", "")}


def _read_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode()
        return json.loads(body).get("detail", body)
    except Exception:
        return str(exc)


def request(method: str, path: str, json_body=None, timeout: int = 10, auth: bool = True):
    cfg = load_config()
    url = base_url(cfg) + path
    data = json.dumps(json_body).encode() if json_body is not None else None
    headers = {"Content-Type": "application/json"}
    if auth:
        headers.update(_auth_headers(cfg))
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, _read_error(e))
    except urllib.error.URLError as e:
        raise ApiError(0, str(e.reason))


def get(path: str, **kw):
    return request("GET", path, **kw)


def post(path: str, json_body=None, **kw):
    return request("POST", path, json_body=json_body, **kw)


def post_multipart(path: str, fields: dict, file_path: str | None = None,
                    file_name: str | None = None, mime: str | None = None,
                    timeout: int = 60):
    cfg = load_config()
    url = base_url(cfg) + path
    boundary = uuid.uuid4().hex
    buf = io.BytesIO()

    def field(name, value):
        buf.write(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
        )

    for k, v in fields.items():
        if v is not None:
            field(k, v)

    if file_path:
        mime = mime or mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        fname = file_name or os.path.basename(file_path)
        buf.write(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
            f'Content-Type: {mime}\r\n\r\n'.encode("utf-8")
        )
        with open(file_path, "rb") as f:
            buf.write(f.read())
        buf.write(b"\r\n")

    buf.write(f"--{boundary}--\r\n".encode("utf-8"))
    body = buf.getvalue()

    headers = _auth_headers(cfg)
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, _read_error(e))
    except urllib.error.URLError as e:
        raise ApiError(0, str(e.reason))
