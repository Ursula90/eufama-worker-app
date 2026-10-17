/*
 * EUFAMA Connect — admin live map.
 *
 * Opened from the app (VIP/admin only) with ?token=... (a short-lived
 * map token from POST /admin/map-token, not the admin's real login
 * token). Polls GET /dispatch/shifts every few seconds and plots each
 * worker's last known GPS position with Leaflet over OpenStreetMap
 * tiles — no API key needed.
 */

const params = new URLSearchParams(location.search);
const token = params.get("token");
const statusText = document.getElementById("status-text");
const emptyEl = document.getElementById("empty");

const POLL_MS = 5000;
const STALE_AFTER_MS = 2 * 60 * 1000; // no ping in 2 min -> greyed out

const map = L.map("map").setView([38.5244, -8.8882], 12);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
  maxZoom: 19,
}).addTo(map);

/** @type {Map<string, {marker: L.Marker}>} */
const markers = new Map();
let hasCenteredOnce = false;

function pinIcon(className) {
  return L.divIcon({ className: "", html: `<div class="pin ${className}"></div>`, iconSize: [16, 16] });
}

function classify(entry) {
  if (entry.sos) return "sos";
  const lastPing = entry.last_ping ? Date.parse(entry.last_ping) : null;
  if (!lastPing || Date.now() - lastPing > STALE_AFTER_MS) return "stale";
  return "ok";
}

function popupHtml(workerId, entry) {
  const lastPing = entry.last_ping ? new Date(entry.last_ping).toLocaleTimeString("ro-RO") : "—";
  return `
    <b>${entry.display_name || workerId}</b><br>
    ID: ${workerId}<br>
    Status: ${entry.sos ? "🚨 SOS" : (entry.status || "OK")}<br>
    Baterie: ${entry.battery != null ? entry.battery + "%" : "—"}<br>
    Ultim semnal: ${lastPing}
  `;
}

async function poll() {
  if (!token) {
    statusText.textContent = "Link invalid — fără token.";
    return;
  }
  try {
    const resp = await fetch(`/dispatch/shifts?token=${encodeURIComponent(token)}`);
    if (!resp.ok) {
      statusText.textContent = resp.status === 401 ? "Token expirat — redeschide harta din aplicație." : `Eroare server (${resp.status})`;
      return;
    }
    const data = await resp.json();
    render(data);
    statusText.textContent = `Actualizat ${new Date().toLocaleTimeString("ro-RO")}`;
  } catch (e) {
    statusText.textContent = "Eroare de conexiune.";
  }
}

function render(data) {
  const entries = Object.entries(data).filter(([, e]) => e.lat != null && e.lon != null);
  emptyEl.hidden = entries.length > 0;

  const seen = new Set();
  for (const [workerId, entry] of entries) {
    seen.add(workerId);
    const latlng = [entry.lat, entry.lon];
    const icon = pinIcon(classify(entry));

    if (markers.has(workerId)) {
      const m = markers.get(workerId).marker;
      m.setLatLng(latlng);
      m.setIcon(icon);
      m.setPopupContent(popupHtml(workerId, entry));
    } else {
      const marker = L.marker(latlng, { icon }).addTo(map).bindPopup(popupHtml(workerId, entry));
      markers.set(workerId, { marker });
    }
  }

  for (const workerId of Array.from(markers.keys())) {
    if (!seen.has(workerId)) {
      markers.get(workerId).marker.remove();
      markers.delete(workerId);
    }
  }

  if (!hasCenteredOnce && entries.length > 0) {
    hasCenteredOnce = true;
    const bounds = L.latLngBounds(entries.map(([, e]) => [e.lat, e.lon]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
  }
}

poll();
setInterval(poll, POLL_MS);
