/*
 * EUFAMA Connect — browser calling client.
 *
 * Opened from the phone app (or desktop) with ?call_id=&token=&name=&type=.
 * Talks to /ws/call/{call_id} purely to exchange WebRTC offers/answers/ICE
 * candidates with the other participants; media never touches the server.
 *
 * Mesh topology: every participant connects directly to every other one.
 * That's simple and works great for 1:1 and small groups, but bandwidth
 * and CPU cost grow with the square of the participant count — see the
 * README for the documented cap and the SFU upgrade path for larger calls.
 */

const params = new URLSearchParams(location.search);
const callId = params.get("call_id");
const token = params.get("token");
const myName = params.get("name") || "EUFAMA";
const callType = params.get("type") === "video" ? "video" : "audio";

const statusText = document.getElementById("status-text");
const centerMsg = document.getElementById("center-msg");
const stage = document.getElementById("stage");
const localPreview = document.getElementById("local-preview");
const localVideoEl = document.getElementById("local-video");
const btnMic = document.getElementById("btn-mic");
const btnCam = document.getElementById("btn-cam");
const btnHangup = document.getElementById("btn-hangup");

const ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];

let localStream = null;
let ws = null;
/** @type {Map<number, RTCPeerConnection>} */
const peers = new Map();
let micOn = true;
let camOn = callType === "video";

function setStatus(text) { statusText.textContent = text; }

function wsUrl() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/ws/call/${callId}?token=${encodeURIComponent(token)}`;
}

function tileFor(userId) {
  let tile = document.getElementById(`tile-${userId}`);
  if (tile) return tile;

  tile = document.createElement("div");
  tile.className = "tile";
  tile.id = `tile-${userId}`;

  if (callType === "video") {
    const video = document.createElement("video");
    video.autoplay = true;
    video.playsInline = true;
    video.id = `video-${userId}`;
    tile.appendChild(video);
  } else {
    const avatar = document.createElement("div");
    avatar.className = "avatar-circle audio-pulse";
    avatar.textContent = "👤";
    tile.appendChild(avatar);
  }

  const label = document.createElement("div");
  label.className = "label";
  label.textContent = `#${userId}`;
  tile.appendChild(label);

  stage.appendChild(tile);
  return tile;
}

function removeTile(userId) {
  const tile = document.getElementById(`tile-${userId}`);
  if (tile) tile.remove();
}

function attachRemoteStream(userId, stream) {
  if (callType === "video") {
    const video = document.getElementById(`video-${userId}`);
    if (video) video.srcObject = stream;
  }
}

function newPeerConnection(userId) {
  const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

  if (localStream) {
    for (const track of localStream.getTracks()) pc.addTrack(track, localStream);
  }

  pc.onicecandidate = (evt) => {
    if (evt.candidate) {
      send({ type: "candidate", to: userId, payload: evt.candidate });
    }
  };

  pc.ontrack = (evt) => {
    tileFor(userId);
    attachRemoteStream(userId, evt.streams[0]);
  };

  pc.onconnectionstatechange = () => {
    if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
      // Let the explicit peer-left signal (or a later reconnect) handle cleanup.
    }
  };

  peers.set(userId, pc);
  return pc;
}

async function offerTo(userId) {
  const pc = newPeerConnection(userId);
  tileFor(userId);
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  send({ type: "offer", to: userId, payload: offer });
}

async function handleOffer(fromId, payload) {
  const pc = peers.get(fromId) || newPeerConnection(fromId);
  tileFor(fromId);
  await pc.setRemoteDescription(new RTCSessionDescription(payload));
  const answer = await pc.createAnswer();
  await pc.setLocalDescription(answer);
  send({ type: "answer", to: fromId, payload: answer });
}

async function handleAnswer(fromId, payload) {
  const pc = peers.get(fromId);
  if (pc) await pc.setRemoteDescription(new RTCSessionDescription(payload));
}

async function handleCandidate(fromId, payload) {
  const pc = peers.get(fromId);
  if (pc) {
    try { await pc.addIceCandidate(payload); } catch (e) { /* ignore late candidates */ }
  }
}

function handlePeerLeft(userId) {
  const pc = peers.get(userId);
  if (pc) { pc.close(); peers.delete(userId); }
  removeTile(userId);
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

async function start() {
  if (!callId || !token) {
    setStatus("Link de apel invalid.");
    return;
  }

  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: callType === "video" ? { facingMode: "user" } : false,
    });
  } catch (err) {
    setStatus("Nu am acces la microfon/cameră.");
    return;
  }

  if (callType === "video") {
    localVideoEl.srcObject = localStream;
    localPreview.hidden = false;
  }

  ws = new WebSocket(wsUrl());

  ws.onopen = () => setStatus(`Conectat — ${myName}`);
  ws.onclose = () => setStatus("Apel încheiat.");
  ws.onerror = () => setStatus("Eroare de conexiune.");

  ws.onmessage = async (evt) => {
    const data = JSON.parse(evt.data);
    centerMsg.classList.add("hidden");

    switch (data.type) {
      case "joined":
        for (const uid of data.participants) await offerTo(uid);
        break;
      case "peer-joined":
        setStatus(`${data.user_id} s-a alăturat apelului`);
        break;
      case "offer":
        await handleOffer(data.from, data.payload);
        break;
      case "answer":
        await handleAnswer(data.from, data.payload);
        break;
      case "candidate":
        await handleCandidate(data.from, data.payload);
        break;
      case "peer-left":
        handlePeerLeft(data.user_id);
        break;
    }

    if (peers.size === 0) centerMsg.classList.remove("hidden");
  };
}

btnMic.onclick = () => {
  micOn = !micOn;
  if (localStream) localStream.getAudioTracks().forEach((t) => (t.enabled = micOn));
  btnMic.classList.toggle("off", !micOn);
  btnMic.textContent = micOn ? "🎤" : "🔇";
};

btnCam.onclick = () => {
  if (callType !== "video") return;
  camOn = !camOn;
  if (localStream) localStream.getVideoTracks().forEach((t) => (t.enabled = camOn));
  btnCam.classList.toggle("off", !camOn);
};

btnHangup.onclick = () => {
  send({ type: "leave" });
  for (const pc of peers.values()) pc.close();
  peers.clear();
  if (localStream) localStream.getTracks().forEach((t) => t.stop());
  if (ws) ws.close();
  setStatus("Ai închis apelul.");
  centerMsg.textContent = "Ai închis apelul. Poți închide această filă.";
  centerMsg.classList.remove("hidden");
};

if (callType !== "video") {
  btnCam.disabled = true;
  btnCam.style.opacity = 0.3;
}

start();
