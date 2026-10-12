# -*- coding: UTF-8 -*-
# SpotifyNVDA - auth.py
# Sign in with Spotify: OAuth 2.0 Authorization Code with PKCE (public client,
# no client secret). The browser comes back to http://127.0.0.1:PORT/callback,
# received by a small listener that accepts only that address.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import base64
import hashlib
import html
import json
import os
import re
import socket
import threading
import time
import urllib.parse
import urllib.request

from . import net
from .errors import SpotifyError

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"  # nosec B105 - public address, not a secret
#: Only what the add-on uses (RS-13).
SCOPES = (
	"user-read-private",
	"playlist-read-private",
	"playlist-read-collaborative",
	"playlist-modify-private",
	"playlist-modify-public",
	"user-read-playback-state",
	"user-modify-playback-state",
	"user-read-currently-playing",
	"user-read-recently-played",
)
DEFAULT_PORT = 8898
CALLBACK_PATH = "/callback"
SIGN_IN_TIMEOUT = 300
#: Access tokens are refreshed this many seconds before they expire.
REFRESH_MARGIN = 60
_CLIENT_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
SESSION_KEY = "session"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def b64url(data):
	return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def randomToken(nbytes=32):
	return b64url(os.urandom(nbytes))


def pkcePair():
	"""Returns (verifier, challenge) for PKCE with S256."""
	verifier = b64url(os.urandom(48))
	challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
	return verifier, challenge


def constantTimeEqual(a, b):
	"""Comparison that takes the same time wherever the first difference is
	(hmac.compare_digest without depending on the hmac module)."""
	if isinstance(a, str):
		a = a.encode("utf-8")
	if isinstance(b, str):
		b = b.encode("utf-8")
	result = len(a) ^ len(b)
	for x, y in zip(a, b if len(a) == len(b) else a):
		result |= x ^ y
	return result == 0


def normalizeClientId(clientId):
	return (clientId or "").strip()


def isValidClientId(clientId):
	return bool(_CLIENT_ID_RE.match(normalizeClientId(clientId)))


def redirectUri(port):
	return "http://127.0.0.1:%d%s" % (int(port), CALLBACK_PATH)


# ---------------------------------------------------------------------------
# Loopback receiver (http://127.0.0.1:PORT/callback)
# ---------------------------------------------------------------------------

_PAGE = (
	"<!DOCTYPE html><html lang=\"{lang}\"><head><meta charset=\"utf-8\">"
	"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
	"<title>{title}</title></head>"
	"<body><main><h1>{title}</h1><p>{text}</p></main></body></html>"
)
_REASONS = {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed"}
#: Biggest request accepted by the loopback listener.
MAX_REQUEST = 16 * 1024


class LoopbackReceiver:
	"""Waits for the browser to come back to http://127.0.0.1:PORT/callback.

	Written on plain sockets: NVDA ships only the parts of the Python standard
	library it uses itself, and http.server/socketserver are not guaranteed to
	be there. It listens only on 127.0.0.1 with an exclusive port (no other
	program can listen on the same port), answers only GET /callback with the
	right state, and never logs the address (it carries the authorization code)."""

	DEFAULT_PAGES = {
		"lang": "en",
		"title": "SpotifyNVDA",
		"done": "Signed in to Spotify. You can close this tab and go back to NVDA.",
		"error": "Sign-in was not completed. You can close this tab and go back to NVDA.",
		"invalid": "This address does not belong to the current sign-in.",
	}

	def __init__(self, state, port, pages=None):
		self.state = state
		self.pages = dict(self.DEFAULT_PAGES, **(pages or {}))
		self.result = None
		self._event = threading.Event()
		self._closed = False
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
			sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
		try:
			sock.bind(("127.0.0.1", int(port)))
			sock.listen(8)
		except OSError as e:
			sock.close()
			raise SpotifyError("portInUse", str(int(port))) from e
		sock.settimeout(0.3)
		self._sock = sock
		self.address = sock.getsockname()
		self._thread = threading.Thread(target=self._serve, name="SpotifyNVDA-signin", daemon=True)
		self._thread.start()

	@property
	def port(self):
		return self.address[1]

	@property
	def redirectUri(self):
		return redirectUri(self.port)

	def _serve(self):
		while not self._closed:
			try:
				conn, _peer = self._sock.accept()
			except socket.timeout:
				continue
			except OSError:
				break
			try:
				self._handle(conn)
			except Exception:  # a broken request never stops the sign-in
				pass
			finally:
				try:
					conn.close()
				except OSError:
					pass

	def _handle(self, conn):
		conn.settimeout(5)
		data = b""
		while b"\r\n\r\n" not in data and b"\n\n" not in data:
			chunk = conn.recv(4096)
			if not chunk:
				break
			data += chunk
			if len(data) > MAX_REQUEST:
				return self._reply(conn, 400, self.pages["invalid"])
		line = data.split(b"\n", 1)[0].decode("latin-1").strip()
		parts = line.split(" ")
		if len(parts) < 2:
			return self._reply(conn, 400, self.pages["invalid"])
		method, target = parts[0], parts[1]
		url = urllib.parse.urlsplit(target)
		if url.path != CALLBACK_PATH:
			return self._reply(conn, 404, self.pages["invalid"])
		if method != "GET":
			return self._reply(conn, 405, self.pages["invalid"])
		params = {k: v[0] for k, v in urllib.parse.parse_qs(url.query, keep_blank_values=True).items()}
		# A request with another state does not come from this sign-in: ignore it.
		if not constantTimeEqual(params.get("state", ""), self.state):
			return self._reply(conn, 400, self.pages["invalid"])
		self._reply(conn, 200, self.pages["error"] if params.get("error") or not params.get("code") else self.pages["done"])
		self._finish(params)

	def _reply(self, conn, status, text):
		body = _PAGE.format(
			lang=html.escape(self.pages["lang"]),
			title=html.escape(self.pages["title"]),
			text=html.escape(text),
		).encode("utf-8")
		head = (
			"HTTP/1.1 %d %s\r\n"
			"Content-Type: text/html; charset=utf-8\r\n"
			"Content-Length: %d\r\n"
			"Cache-Control: no-store\r\n"
			"Referrer-Policy: no-referrer\r\n"
			"X-Content-Type-Options: nosniff\r\n"
			"Content-Security-Policy: default-src 'none'\r\n"
			"Connection: close\r\n\r\n"
		) % (status, _REASONS.get(status, "Error"), len(body))
		conn.sendall(head.encode("ascii") + body)

	def _finish(self, params):
		if self.result is None:
			self.result = params
			self._event.set()

	def wait(self, timeout, cancelEvent=None):
		"""Returns the callback parameters. Raises SpotifyError timeout or cancelled."""
		deadline = time.monotonic() + timeout
		while True:
			if cancelEvent is not None and cancelEvent.is_set():
				raise SpotifyError("cancelled")
			if self._event.wait(0.2):
				return self.result
			if time.monotonic() >= deadline:
				raise SpotifyError("timeout", "sign-in")

	def close(self):
		self._closed = True
		try:
			self._sock.close()
		except OSError:
			pass
		if self._thread is not threading.current_thread():
			self._thread.join(2)


# ---------------------------------------------------------------------------
# accounts.spotify.com
# ---------------------------------------------------------------------------

class OAuthClient:
	def __init__(self, authorizeUrl=AUTHORIZE_URL, tokenUrl=TOKEN_URL, opener=None, timeout=net.DEFAULT_TIMEOUT):
		self.authorizeUrl = authorizeUrl
		self.tokenUrl = tokenUrl
		self.opener = opener or net.buildOpener()
		self.timeout = timeout

	def buildAuthorizeUrl(self, clientId, redirect, state, challenge, scopes=SCOPES):
		query = urllib.parse.urlencode({
			"client_id": clientId,
			"response_type": "code",
			"redirect_uri": redirect,
			"code_challenge_method": "S256",
			"code_challenge": challenge,
			"state": state,
			"scope": " ".join(scopes),
		})
		return "%s?%s" % (self.authorizeUrl, query)

	def _post(self, form):
		data = urllib.parse.urlencode(form).encode("ascii")
		req = urllib.request.Request(self.tokenUrl, data=data, method="POST", headers={
			"Content-Type": "application/x-www-form-urlencoded",
			"Accept": "application/json",
		})
		status, _headers, body = net.openRequest(self.opener, req, self.timeout)
		try:
			payload = json.loads(body.decode("utf-8")) if body else {}
		except ValueError:
			payload = {}
		if not isinstance(payload, dict):
			payload = {}
		if status >= 400:
			code = str(payload.get("error") or "")
			if code == "invalid_grant":
				raise SpotifyError("auth", code, status)
			if code in ("invalid_client", "unauthorized_client"):
				raise SpotifyError("invalidClientId", code, status)
			if status == 429:
				raise SpotifyError("rateLimited", code, status)
			if status >= 500:
				raise SpotifyError("server", code, status)
			raise SpotifyError("badRequest", code, status)
		if not payload.get("access_token"):
			raise SpotifyError("badResponse", "no access_token")
		return payload

	def exchangeCode(self, clientId, code, verifier, redirect):
		return self._post({
			"grant_type": "authorization_code",
			"code": code,
			"redirect_uri": redirect,
			"client_id": clientId,
			"code_verifier": verifier,
		})

	def refresh(self, clientId, refreshToken):
		return self._post({
			"grant_type": "refresh_token",
			"refresh_token": refreshToken,
			"client_id": clientId,
		})


# ---------------------------------------------------------------------------
# Session (kept signed in between NVDA restarts)
# ---------------------------------------------------------------------------

def _expiresIn(value):
	try:
		seconds = int(value)
	except (TypeError, ValueError):
		return 3600
	return min(max(seconds, 60), 24 * 3600)


class Session:
	"""The signed-in Spotify account. The refresh token is saved encrypted and
	the access token is renewed when needed, so the user stays signed in."""

	def __init__(self, store, oauth=None, clock=time.time):
		self.store = store
		self.oauth = oauth or OAuthClient()
		self.clock = clock
		self._lock = threading.RLock()

	def _data(self):
		data = self.store.get(SESSION_KEY)
		return data if isinstance(data, dict) and data.get("refreshToken") and data.get("clientId") else None

	@property
	def signedIn(self):
		return self._data() is not None

	@property
	def user(self):
		data = self._data()
		return dict(data.get("user") or {}) if data else {}

	def setUser(self, user):
		with self._lock:
			data = self._data()
			if data:
				data["user"] = {
					"id": str(user.get("id") or ""),
					"name": str(user.get("display_name") or user.get("id") or ""),
					"product": str(user.get("product") or ""),
				}
				self.store.set(SESSION_KEY, data)

	def signIn(self, clientId, port, openBrowser, cancelEvent=None, timeout=SIGN_IN_TIMEOUT, pages=None):
		"""Runs the whole sign-in. openBrowser(url) shows the Spotify login page.
		Blocks until the browser comes back; call it from a background thread."""
		clientId = normalizeClientId(clientId)
		if not clientId:
			raise SpotifyError("noClientId")
		if not isValidClientId(clientId):
			raise SpotifyError("invalidClientId", "format")
		verifier, challenge = pkcePair()
		state = randomToken()
		receiver = LoopbackReceiver(state, port, pages)
		try:
			redirect = receiver.redirectUri
			openBrowser(self.oauth.buildAuthorizeUrl(clientId, redirect, state, challenge))
			params = receiver.wait(timeout, cancelEvent)
		finally:
			receiver.close()
		error = params.get("error")
		if error == "access_denied":
			raise SpotifyError("denied")
		if error:
			raise SpotifyError("invalidClientId" if error in ("invalid_client", "unauthorized_client") else "auth", error)
		code = params.get("code")
		if not code:
			raise SpotifyError("badResponse", "no code")
		tokens = self.oauth.exchangeCode(clientId, code, verifier, redirect)
		if not tokens.get("refresh_token"):
			raise SpotifyError("badResponse", "no refresh_token")
		with self._lock:
			self.store.set(SESSION_KEY, {
				"clientId": clientId,
				"accessToken": tokens["access_token"],
				"refreshToken": tokens["refresh_token"],
				"expiresAt": self.clock() + _expiresIn(tokens.get("expires_in")),
				"scope": str(tokens.get("scope") or ""),
				"user": {},
			})

	def accessToken(self, force=False):
		with self._lock:
			data = self._data()
			if not data:
				raise SpotifyError("notSignedIn")
			if force or not data.get("accessToken") or data.get("expiresAt", 0) - REFRESH_MARGIN <= self.clock():
				data = self._refresh(data)
			return data["accessToken"]

	def _refresh(self, data):
		try:
			tokens = self.oauth.refresh(data["clientId"], data["refreshToken"])
		except SpotifyError as e:
			if e.kind in ("auth", "invalidClientId"):
				# Access revoked or the app was deleted: the saved session is useless.
				self.signOut()
				raise SpotifyError("auth", e.detail, e.status)
			raise
		data = dict(data)
		data["accessToken"] = tokens["access_token"]
		# Spotify may rotate the refresh token: always keep the newest one.
		data["refreshToken"] = tokens.get("refresh_token") or data["refreshToken"]
		data["expiresAt"] = self.clock() + _expiresIn(tokens.get("expires_in"))
		if tokens.get("scope"):
			data["scope"] = str(tokens["scope"])
		self.store.set(SESSION_KEY, data)
		return data

	def signOut(self):
		"""Forgets the session and every personal data kept by the add-on."""
		with self._lock:
			self.store.removeAll()
