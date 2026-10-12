# -*- coding: UTF-8 -*-
"""Local server that imitates accounts.spotify.com (authorize + token, PKCE) and
api.spotify.com/v1 (the endpoints used by SpotifyNVDA), with a fake browser.

It checks what the real services check: PKCE verifier against the challenge,
redirect URI, client id, bearer token, Premium for playback, active device.
Every request is recorded in SpotifyMock.requests (tests read them)."""

import base64
import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLIENT_ID = "0123456789abcdef0123456789abcdef"
USER_ID = "wellington"


def b64url(data):
	return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _track(n, name, artist, album="Album %d"):
	tid = "t%07d" % n
	return {
		"id": tid,
		"uri": "spotify:track:" + tid,
		"name": name,
		"artists": [{"name": artist}],
		"album": {"name": album % n if "%d" in album else album},
		"duration_ms": 200000 + n,
	}


TRACKS = [
	_track(1, "Garota de Ipanema", "Tom Jobim", "Getz/Gilberto"),
	_track(2, "Aquarela do Brasil", "Ary Barroso"),
	_track(3, "Mas que nada", "Jorge Ben"),
	_track(4, "Chega de Saudade", "João Gilberto"),
	_track(5, "Águas de Março", "Elis Regina"),
	_track(6, "Evidências", "Chitãozinho & Xororó"),
]


class SpotifyMock:
	def __init__(self):
		self.lock = threading.RLock()
		self.requests = []
		self.reset()

	def reset(self):
		with self.lock:
			self.requests = []
			self.codes = {}
			self.accessTokens = {}
			self.refreshTokens = set()
			self.rotateRefresh = True
			self.accessLifetime = 3600
			self.product = "premium"
			#: Since February 2026 apps in development mode no longer get "product" in GET /me.
			self.meHasProduct = False
			self.registered = True
			self.failures = {}  # (method, path) -> list of (status, payload, headers), consumed in order
			self.newEndpoints = True  # /me/playlists POST and /playlists/{id}/items
			self.tokenFailure = None
			self.playlists = []
			for i in range(1, 56):
				owner = USER_ID if i % 5 else "someone"
				entries = [
					{"added_at": "2026-01-%02dT10:00:00Z" % (20 - k), "is_local": False, "item": TRACKS[(i + k) % len(TRACKS)]}
					for k in range(min(i, len(TRACKS)))
				]
				if i == 2:
					entries.append({"added_at": "2026-02-01T10:00:00Z", "is_local": True, "item": {"name": "Gravação caseira", "uri": "spotify:local:::Gravacao+caseira:120", "artists": [{"name": "Eu"}], "duration_ms": 1000, "is_local": True}})
				self.playlists.append({
					"id": "p%07d" % i,
					"uri": "spotify:playlist:p%07d" % i,
					"name": "Playlist %d" % i,
					"owner": {"id": owner, "display_name": owner.title()},
					"items": {"total": len(entries)},
					"entries": entries,
					"collaborative": False,
					"tracks_added": [],
				})
				if owner != USER_ID:
					# Since February 2026 "items" is absent for playlists the user does not own.
					del self.playlists[-1]["items"]
			self.devices = [
				{"id": "dev-computer", "name": "MEU-PC", "type": "Computer", "is_active": False, "is_restricted": False, "volume_percent": 50, "supports_volume": True},
				{"id": "dev-phone", "name": "Celular", "type": "Smartphone", "is_active": False, "is_restricted": False, "volume_percent": 70, "supports_volume": True},
			]
			self.devicesHidden = False  # simulates the Spotify app being closed
			self.player = None  # dict with device_id, item, context, is_playing, progress_ms
			self.recent = [{
				"track": TRACKS[3],
				"played_at": "2026-10-10T20:00:00.000Z",
				"context": {"uri": "spotify:playlist:p0000001", "type": "playlist"},
			}]
			self.launches = 0
			self.reorders = []
			self.deleted = []
			self.browserOpened = []

	# -- helpers -----------------------------------------------------------------

	def newAccess(self):
		token = "AT-" + b64url(os.urandom(12))
		self.accessTokens[token] = time.time() + self.accessLifetime
		return token

	def newRefresh(self):
		token = "RT-" + b64url(os.urandom(12))
		self.refreshTokens.add(token)
		return token

	def expireAll(self):
		with self.lock:
			for t in self.accessTokens:
				self.accessTokens[t] = 0

	def fail(self, method, path, status, payload=None, headers=None, times=1):
		with self.lock:
			self.failures.setdefault((method, path), []).extend([(status, payload, headers or {})] * times)

	def device(self, deviceId):
		for d in self.visibleDevices():
			if d["id"] == deviceId:
				return d
		return None

	def visibleDevices(self):
		return [] if self.devicesHidden else self.devices

	def activeDevice(self):
		for d in self.visibleDevices():
			if d["is_active"]:
				return d
		return None

	def activate(self, deviceId):
		for d in self.devices:
			d["is_active"] = d["id"] == deviceId

	def authorize(self, params):
		"""What accounts.spotify.com/authorize does after the user agrees."""
		with self.lock:
			code = "CODE-" + b64url(os.urandom(9))
			self.codes[code] = {
				"challenge": params["code_challenge"],
				"redirect": params["redirect_uri"],
				"clientId": params["client_id"],
				"scope": params.get("scope", ""),
			}
			return code


MOCK = SpotifyMock()


def _public(p):
	"""The playlist as Spotify sends it (without the mock's own fields)."""
	out = {k: v for k, v in p.items() if k not in ("tracks_added", "entries")}
	if "items" in out:
		out["items"] = {"total": len(p.get("entries", []))}
	if "tracks" in out:
		out["tracks"] = {"total": len(p.get("entries", []))}
	return out


def _trackById(tid):
	for t in TRACKS:
		if t["id"] == tid:
			return t
	return None


class Handler(BaseHTTPRequestHandler):
	protocol_version = "HTTP/1.1"

	def log_message(self, *a):
		pass

	def _send(self, status, payload=None, headers=None, raw=None):
		body = raw if raw is not None else (json.dumps(payload).encode("utf-8") if payload is not None else b"")
		self.send_response(status)
		if body:
			self.send_header("Content-Type", "application/json")
		for k, v in (headers or {}).items():
			self.send_header(k, str(v))
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		if body:
			self.wfile.write(body)

	def _body(self):
		n = int(self.headers.get("Content-Length") or 0)
		return self.rfile.read(n) if n else b""

	def do_GET(self):
		self._dispatch("GET")

	def do_POST(self):
		self._dispatch("POST")

	def do_PUT(self):
		self._dispatch("PUT")

	def do_DELETE(self):
		self._dispatch("DELETE")

	def _dispatch(self, method):
		url = urllib.parse.urlsplit(self.path)
		query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
		raw = self._body()
		with MOCK.lock:
			MOCK.requests.append({"method": method, "path": url.path, "query": query, "headers": dict(self.headers), "body": raw})
			queued = MOCK.failures.get((method, url.path))
			if queued:
				status, payload, headers = queued.pop(0)
				return self._send(status, payload, headers)
		if url.path == "/api/token":
			return self._token(raw)
		if url.path == "/redirect-me":
			return self._send(302, None, {"Location": "http://127.0.0.1:1/stolen"})
		if url.path == "/huge":
			return self._send(200, raw=b"[" + b"1," * (3 * 1024 * 1024) + b"1]")
		if url.path.startswith("/v1/"):
			auth = self.headers.get("Authorization", "")
			token = auth[7:] if auth.startswith("Bearer ") else ""
			with MOCK.lock:
				exp = MOCK.accessTokens.get(token)
			if exp is None or exp < time.time():
				return self._send(401, {"error": {"status": 401, "message": "The access token expired"}})
			return self._api(method, url.path[3:], query, raw)
		return self._send(404, {"error": "not found"})

	# -- accounts --------------------------------------------------------------------

	def _token(self, raw):
		form = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode("ascii")).items()}
		with MOCK.lock:
			if MOCK.tokenFailure:
				status, payload = MOCK.tokenFailure
				return self._send(status, payload)
			if form.get("client_id") != CLIENT_ID:
				return self._send(400, {"error": "invalid_client", "error_description": "Invalid client"})
			if "client_secret" in form:
				return self._send(400, {"error": "invalid_request", "error_description": "secret not expected"})
			grant = form.get("grant_type")
			if grant == "authorization_code":
				info = MOCK.codes.pop(form.get("code", ""), None)
				if not info:
					return self._send(400, {"error": "invalid_grant", "error_description": "Invalid authorization code"})
				if info["redirect"] != form.get("redirect_uri"):
					return self._send(400, {"error": "invalid_grant", "error_description": "Invalid redirect URI"})
				verifier = form.get("code_verifier", "")
				if b64url(hashlib.sha256(verifier.encode("ascii")).digest()) != info["challenge"]:
					return self._send(400, {"error": "invalid_grant", "error_description": "code_verifier was incorrect"})
				return self._send(200, {
					"access_token": MOCK.newAccess(),
					"token_type": "Bearer",
					"expires_in": MOCK.accessLifetime,
					"refresh_token": MOCK.newRefresh(),
					"scope": info["scope"],
				})
			if grant == "refresh_token":
				rt = form.get("refresh_token", "")
				if rt not in MOCK.refreshTokens:
					return self._send(400, {"error": "invalid_grant", "error_description": "Refresh token revoked"})
				payload = {"access_token": MOCK.newAccess(), "token_type": "Bearer", "expires_in": MOCK.accessLifetime}
				if MOCK.rotateRefresh:
					MOCK.refreshTokens.discard(rt)
					payload["refresh_token"] = MOCK.newRefresh()
				return self._send(200, payload)
			return self._send(400, {"error": "unsupported_grant_type"})

	# -- web api ---------------------------------------------------------------------

	def _api(self, method, path, query, raw):
		body = json.loads(raw.decode("utf-8")) if raw else {}
		M = MOCK
		with M.lock:
			if not M.registered:
				return self._send(403, {"error": {"status": 403, "message": "User not registered in the Developer Dashboard"}})
			if path == "/me" and method == "GET":
				me = {"id": USER_ID, "display_name": "Wellington"}
				if M.meHasProduct:
					me["product"] = M.product
				return self._send(200, me)
			if path == "/me/playlists" and method == "GET":
				limit = int(query.get("limit", 20))
				offset = int(query.get("offset", 0))
				if limit > 50:
					return self._send(400, {"error": {"status": 400, "message": "Invalid limit"}})
				page = M.playlists[offset:offset + limit]
				nxt = "next" if offset + limit < len(M.playlists) else None
				return self._send(200, {"items": [_public(p) for p in page], "next": nxt, "total": len(M.playlists)})
			if path == "/me/playlists" and method == "POST":
				if not M.newEndpoints:
					return self._send(404, {"error": {"status": 404, "message": "Not found"}})
				return self._create(body)
			if path == "/users/%s/playlists" % USER_ID and method == "POST":
				return self._create(body, old=True)
			if path.startswith("/playlists/") and method in ("POST", "GET", "PUT"):
				parts = path.split("/")
				pid, what = parts[2], parts[3]
				if what == "items" and not M.newEndpoints:
					return self._send(404, {"error": {"status": 404, "message": "Not found"}})
				if what == "tracks" and method == "GET":
					return self._send(403, {"error": {"status": 403, "message": "Forbidden"}})
				p = next((x for x in M.playlists if x["id"] == pid), None)
				if p is None:
					return self._send(404, {"error": {"status": 404, "message": "Invalid playlist Id"}})
				mine = p["owner"]["id"] == USER_ID or p.get("collaborative")
				if method == "POST":
					p["tracks_added"].extend(body.get("uris", []))
					for uri in body.get("uris", []):
						t = _trackById(uri.split(":")[-1])
						p["entries"].append({"added_at": "2026-03-01T10:00:00Z", "is_local": False, "item": t})
					return self._send(201, {"snapshot_id": "snap"})
				if not mine:
					# Since 2026, only playlists the user owns or collaborates on show their songs.
					return self._send(403, {"error": {"status": 403, "message": "Forbidden"}})
				if method == "GET":
					limit = int(query.get("limit", 20))
					offset = int(query.get("offset", 0))
					if limit > 50:
						return self._send(400, {"error": {"status": 400, "message": "Invalid limit"}})
					page = p["entries"][offset:offset + limit]
					nxt = "next" if offset + limit < len(p["entries"]) else None
					return self._send(200, {"items": page, "next": nxt, "total": len(p["entries"]), "offset": offset, "limit": limit})
				# PUT: reorder one range
				start = int(body["range_start"])
				before = int(body["insert_before"])
				length = int(body.get("range_length", 1))
				entries = p["entries"]
				if start < 0 or start + length > len(entries) or before < 0 or before > len(entries):
					return self._send(400, {"error": {"status": 400, "message": "Index out of bounds"}})
				moving = entries[start:start + length]
				del entries[start:start + length]
				if before > start:
					before -= length
				entries[before:before] = moving
				M.reorders.append((pid, int(body["range_start"]), int(body["insert_before"]), body.get("snapshot_id")))
				return self._send(200, {"snapshot_id": "snap-%d" % len(M.reorders)})
			if path == "/me/library" and method == "DELETE":
				uris = [u for u in query.get("uris", "").split(",") if u]
				if not uris or len(uris) > 40:
					return self._send(400, {"error": {"status": 400, "message": "Invalid uris"}})
				for uri in uris:
					if uri.startswith("spotify:playlist:"):
						pid = uri.split(":")[-1]
						M.playlists = [p for p in M.playlists if p["id"] != pid]
						M.deleted.append(pid)
				return self._send(200)
			if path == "/search":
				q = query.get("q", "").lower()
				limit = int(query.get("limit", 20))
				if limit > 10:
					return self._send(400, {"error": {"status": 400, "message": "Invalid limit"}})
				if query.get("type") == "track":
					items = [t for t in TRACKS if q in t["name"].lower() or q in t["artists"][0]["name"].lower()][:limit]
					return self._send(200, {"tracks": {"items": items}})
				items = [p for p in M.playlists if q in p["name"].lower()][:limit]
				# Real Spotify sometimes returns null entries in playlist searches.
				return self._send(200, {"playlists": {"items": [None] + [_public(p) for p in items]}})
			if path == "/me/player/devices":
				return self._send(200, {"devices": M.visibleDevices()})
			if path == "/me/player/recently-played":
				return self._send(200, {"items": M.recent[: int(query.get("limit", 20))]})
			if path == "/me/player" and method == "GET":
				active = M.activeDevice()
				if not active or not M.player:
					return self._send(204)
				return self._send(200, {
					"device": active,
					"is_playing": M.player["is_playing"],
					"progress_ms": M.player["progress_ms"],
					"item": M.player["item"],
					"context": M.player["context"],
				})
			if path.startswith("/me/player"):
				if M.product != "premium":
					return self._send(403, {"error": {"status": 403, "message": "Player command failed: Premium required", "reason": "PREMIUM_REQUIRED"}})
				return self._player(method, path, query, body)
		return self._send(404, {"error": {"status": 404, "message": "Service not found"}})

	def _create(self, body, old=False):
		M = MOCK
		pid = "n%07d" % (len(M.playlists) + 1)
		p = {
			"id": pid,
			"uri": "spotify:playlist:" + pid,
			"name": body.get("name"),
			"description": body.get("description"),
			"public": body.get("public"),
			"owner": {"id": USER_ID, "display_name": "Wellington"},
			("tracks" if old else "items"): {"total": 0},
			"entries": [],
			"tracks_added": [],
		}
		M.playlists.insert(0, p)
		return self._send(201, _public(p))

	def _player(self, method, path, query, body):
		M = MOCK
		deviceId = query.get("device_id")
		if deviceId:
			device = M.device(deviceId)
			if not device:
				return self._send(404, {"error": {"status": 404, "message": "Device not found"}})
		else:
			device = M.activeDevice()
		noDevice = (404, {"error": {"status": 404, "message": "Player command failed: No active device found", "reason": "NO_ACTIVE_DEVICE"}})
		if path == "/me/player" and method == "PUT":
			d = M.device(body["device_ids"][0])
			if not d:
				return self._send(404, {"error": {"status": 404, "message": "Device not found"}})
			M.activate(d["id"])
			if M.player:
				M.player["is_playing"] = bool(body.get("play")) or M.player["is_playing"]
			return self._send(204)
		if device is None:
			return self._send(*noDevice)
		if path == "/me/player/play":
			M.activate(device["id"])
			if body.get("context_uri"):
				ctx = body["context_uri"]
				if not any(p["uri"] == ctx for p in M.playlists):
					return self._send(404, {"error": {"status": 404, "message": "Context not found"}})
				offset = (body.get("offset") or {}).get("uri")
				item = _trackById(offset.split(":")[-1]) if offset else TRACKS[0]
				if offset and item is None:
					return self._send(400, {"error": {"status": 400, "message": "Can't have offset for context"}})
				M.player = {"item": item, "context": {"uri": ctx, "type": "playlist"}, "is_playing": True, "progress_ms": body.get("position_ms", 0)}
			elif body.get("uris"):
				item = _trackById(body["uris"][0].split(":")[-1])
				if item is None:
					return self._send(400, {"error": {"status": 400, "message": "Invalid track uri"}})
				M.player = {"item": item, "context": None, "is_playing": True, "progress_ms": body.get("position_ms", 0)}
			else:
				if not M.player:
					return self._send(*noDevice)
				M.player["is_playing"] = True
			return self._send(204)
		if not M.player:
			return self._send(*noDevice)
		if path == "/me/player/pause":
			if not M.player["is_playing"]:
				return self._send(403, {"error": {"status": 403, "message": "Player command failed: Restriction violated", "reason": "UNKNOWN"}})
			M.player["is_playing"] = False
			return self._send(204)
		if path in ("/me/player/next", "/me/player/previous") and method == "POST":
			i = TRACKS.index(M.player["item"]) if M.player["item"] in TRACKS else 0
			i = (i + (1 if path.endswith("next") else -1)) % len(TRACKS)
			M.player.update(item=TRACKS[i], progress_ms=0, is_playing=True)
			return self._send(204)
		if path == "/me/player/volume":
			if not device.get("supports_volume"):
				return self._send(403, {"error": {"status": 403, "message": "Cannot control device volume", "reason": "VOLUME_CONTROL_DISALLOW"}})
			device["volume_percent"] = int(query["volume_percent"])
			return self._send(204)
		return self._send(404, {"error": {"status": 404, "message": "Service not found"}})


def start():
	server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
	server.daemon_threads = True
	threading.Thread(target=server.serve_forever, daemon=True).start()
	return server, "http://127.0.0.1:%d" % server.server_address[1]


class FakeBrowser:
	"""Plays the user in the browser: checks the authorize address, then lets
	Spotify redirect to the add-on's 127.0.0.1 listener."""

	def __init__(self, base, mode="agree", delay=0.05):
		self.base = base
		self.mode = mode  # agree | deny | wrongState | nothing
		self.delay = delay
		self.urls = []
		self.callbackStatus = []

	def __call__(self, url):
		self.urls.append(url)
		MOCK.browserOpened.append(url)
		parts = urllib.parse.urlsplit(url)
		params = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}
		if self.mode == "nothing":
			return
		threading.Thread(target=self._comeBack, args=(params,), daemon=True).start()

	def _comeBack(self, params):
		time.sleep(self.delay)
		redirect = params["redirect_uri"]
		if self.mode == "deny":
			query = {"error": "access_denied", "state": params["state"]}
		elif self.mode == "wrongState":
			query = {"code": MOCK.authorize(params), "state": "attacker-state"}
		else:
			query = {"code": MOCK.authorize(params), "state": params["state"]}
		try:
			with urllib.request.urlopen(redirect + "?" + urllib.parse.urlencode(query), timeout=5) as r:  # nosec B310 - test
				self.callbackStatus.append((r.status, r.read().decode("utf-8")))
		except urllib.error.HTTPError as e:
			self.callbackStatus.append((e.code, e.read().decode("utf-8")))
		except Exception as e:  # noqa: BLE001
			self.callbackStatus.append((0, repr(e)))
