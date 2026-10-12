# -*- coding: UTF-8 -*-
# SpotifyNVDA - api.py
# Client of the Spotify Web API (https://api.spotify.com/v1).
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import json
import re
import time
import urllib.parse
import urllib.request

from . import net
from .errors import SpotifyError

API_BASE = "https://api.spotify.com/v1"
#: Search pages are small: Spotify apps in development mode accept at most 10.
SEARCH_LIMIT = 10
MAX_QUERY = 200
MAX_PLAYLISTS = 500
#: Songs read from one playlist (pages of 50). 10,000 is the most a Spotify playlist can have.
MAX_PLAYLIST_ITEMS = 10000
#: While reading a big playlist, a "wait" from Spotify (429) up to this many seconds is respected.
MAX_PAGE_RETRY_AFTER = 30
#: Songs removed per request (Spotify limit).
MAX_REMOVE = 100
MAX_PLAYLIST_NAME = 100
MAX_PLAYLIST_DESCRIPTION = 300
#: Longest Retry-After (seconds) the client waits by itself, once.
MAX_AUTO_RETRY_AFTER = 3

_ID_RE = re.compile(r"^[A-Za-z0-9]{1,64}$")
_USER_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
_URI_RE = re.compile(r"^spotify:(track|episode):[A-Za-z0-9]{1,64}$")
_CONTEXT_RE = re.compile(r"^spotify:((playlist|album|artist|show):[A-Za-z0-9]{1,64}|user:[A-Za-z0-9._\-]{1,64}:collection)$")


def checkId(value):
	value = str(value or "")
	if not _ID_RE.match(value):
		raise SpotifyError("badRequest", "invalid id")
	return value


def isTrackUri(uri):
	return bool(_URI_RE.match(str(uri or "")))


def isContextUri(uri):
	return bool(_CONTEXT_RE.match(str(uri or "")))


def _text(value, limit=200):
	return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def simplifyTrack(t):
	if not isinstance(t, dict) or not isTrackUri(t.get("uri")):
		return None
	album = t.get("album") if isinstance(t.get("album"), dict) else {}
	return {
		"kind": "track",
		"id": str(t.get("id") or ""),
		"uri": t["uri"],
		"name": _text(t.get("name")),
		"artists": ", ".join(_text(a.get("name")) for a in (t.get("artists") or []) if isinstance(a, dict) and a.get("name")),
		"album": _text(album.get("name")),
		"durationMs": int(t.get("duration_ms") or 0),
	}


def _artists(obj):
	return ", ".join(_text(a.get("name")) for a in (obj.get("artists") or []) if isinstance(a, dict) and a.get("name"))


def simplifyEntry(entry, position):
	"""A song of a playlist (PlaylistTrackObject). Since 2026 the song is in
	"item"; before it was in "track". Local files and removed songs are kept
	(their position matters to save an order) but are not playable."""
	entry = entry if isinstance(entry, dict) else {}
	obj = entry.get("item") if isinstance(entry.get("item"), dict) else entry.get("track")
	track = simplifyTrack(obj)
	if track:
		track.update(position=position, addedAt=str(entry.get("added_at") or ""), playable=True, local=False)
		return track
	obj = obj if isinstance(obj, dict) else {}
	album = obj.get("album") if isinstance(obj.get("album"), dict) else {}
	return {
		"kind": "track",
		"id": "",
		"uri": "",
		"name": _text(obj.get("name")) or "?",
		"artists": _artists(obj),
		"album": _text(album.get("name")),
		"durationMs": int(obj.get("duration_ms") or 0),
		"position": position,
		"addedAt": str(entry.get("added_at") or ""),
		"playable": False,
		"local": bool(entry.get("is_local") or obj.get("is_local")),
	}


def simplifyPlaylist(p):
	if not isinstance(p, dict) or not isContextUri(p.get("uri")) or not _ID_RE.match(str(p.get("id") or "")):
		return None
	owner = p.get("owner") if isinstance(p.get("owner"), dict) else {}
	# The playlist object calls the track list "items" since 2026 and "tracks" before.
	items = p.get("items") if isinstance(p.get("items"), dict) else p.get("tracks")
	total = items.get("total") if isinstance(items, dict) else None
	return {
		"kind": "playlist",
		"id": p["id"],
		"uri": p["uri"],
		"name": _text(p.get("name")),
		"owner": _text(owner.get("display_name") or owner.get("id")),
		"ownerId": str(owner.get("id") or ""),
		"collaborative": bool(p.get("collaborative")),
		"total": int(total) if isinstance(total, int) else None,
	}


def _errorKind(status, payload):
	err = payload.get("error") if isinstance(payload, dict) else None
	reason = ""
	message = ""
	if isinstance(err, dict):
		reason = str(err.get("reason") or "")
		message = str(err.get("message") or "")
	elif isinstance(err, str):
		message = err
	text = (reason + " " + message).lower()
	if reason == "PREMIUM_REQUIRED" or "premium required" in text:
		return "premiumRequired", message
	if reason == "NO_ACTIVE_DEVICE" or "no active device" in text:
		return "noDevice", message
	if reason in ("VOLUME_CONTROL_DISALLOW", "UNKNOWN", "ALREADY_PAUSED", "NOT_PAUSED") or reason.endswith("_DISALLOW") or "restriction" in text:
		return "restricted", reason or message
	if status == 401:
		return "auth", message
	if status == 403:
		return "forbidden", message
	if status == 404:
		return "notFound", message
	if status == 429:
		return "rateLimited", message
	if status >= 500:
		return "server", message
	return "badRequest", message


class SpotifyClient:
	def __init__(self, session, opener=None, baseUrl=API_BASE, timeout=net.DEFAULT_TIMEOUT, sleep=time.sleep):
		self.session = session
		self.opener = opener or net.buildOpener()
		self.baseUrl = baseUrl.rstrip("/")
		self.timeout = timeout
		self.sleep = sleep

	# -- transport ---------------------------------------------------------------

	def request(self, method, path, query=None, body=None):
		return self._request(method, path, query, body, retriedAuth=False, retriedRate=False)

	def _request(self, method, path, query, body, retriedAuth, retriedRate):
		url = self.baseUrl + path
		if query:
			url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
		headers = {
			"Authorization": "Bearer " + self.session.accessToken(force=retriedAuth),
			"Accept": "application/json",
		}
		data = None
		if body is not None:
			data = json.dumps(body).encode("utf-8")
			headers["Content-Type"] = "application/json"
		elif method in ("PUT", "POST"):
			data = b""
		req = urllib.request.Request(url, data=data, method=method, headers=headers)
		status, respHeaders, raw = net.openRequest(self.opener, req, self.timeout)
		if status == 401 and not retriedAuth:
			return self._request(method, path, query, body, True, retriedRate)
		if status == 429:
			retryAfter = _retryAfter(respHeaders)
			if not retriedRate and retryAfter <= MAX_AUTO_RETRY_AFTER:
				self.sleep(retryAfter)
				return self._request(method, path, query, body, retriedAuth, True)
			raise SpotifyError("rateLimited", "", status, retryAfter)
		payload = None
		if raw:
			try:
				payload = json.loads(raw.decode("utf-8"))
			except ValueError:
				if status < 300:
					# Some player commands answer 200 with a snapshot id as plain text.
					payload = None
		if status >= 300:
			kind, detail = _errorKind(status, payload)
			raise SpotifyError(kind, detail, status)
		return payload

	# -- account -----------------------------------------------------------------

	def me(self):
		return self.request("GET", "/me") or {}

	# -- playlists ---------------------------------------------------------------

	def myPlaylists(self, maxItems=MAX_PLAYLISTS):
		out = []
		offset = 0
		while len(out) < maxItems:
			page = self.request("GET", "/me/playlists", {"limit": 50, "offset": offset}) or {}
			items = page.get("items") or []
			for p in items:
				s = simplifyPlaylist(p)
				if s:
					out.append(s)
			offset += len(items)
			if not items or not page.get("next"):
				break
		return out[:maxItems]

	def createPlaylist(self, name, description="", public=False):
		name = _text(name, MAX_PLAYLIST_NAME)
		if not name:
			raise SpotifyError("badRequest", "empty name")
		body = {"name": name, "description": _text(description, MAX_PLAYLIST_DESCRIPTION), "public": bool(public)}
		try:
			created = self.request("POST", "/me/playlists", body=body)
		except SpotifyError as e:
			if e.kind not in ("notFound", "badRequest") or e.status not in (404, 405):
				raise
			userId = str(self.me().get("id") or "")
			if not _USER_ID_RE.match(userId):
				raise SpotifyError("badResponse", "user id")
			created = self.request("POST", "/users/%s/playlists" % urllib.parse.quote(userId, safe=""), body=body)
		result = simplifyPlaylist(created)
		if not result:
			raise SpotifyError("badResponse", "playlist")
		return result

	def addToPlaylist(self, playlistId, uris):
		playlistId = checkId(playlistId)
		uris = [u for u in uris if isTrackUri(u)][:100]
		if not uris:
			raise SpotifyError("badRequest", "no tracks")
		try:
			return self.request("POST", "/playlists/%s/items" % playlistId, body={"uris": uris})
		except SpotifyError as e:
			if e.status not in (404, 405):
				raise
			return self.request("POST", "/playlists/%s/tracks" % playlistId, body={"uris": uris})

	def playlistItems(self, playlistId, maxItems=MAX_PLAYLIST_ITEMS, onTotal=None):
		"""All the songs of a playlist, in the playlist order. Spotify only shows the
		songs of playlists the user owns or collaborates on (403 for the others).
		onTotal(total) is called once, with the real number of songs, after the first page."""
		playlistId = checkId(playlistId)
		out = []
		offset = 0
		while len(out) < maxItems:
			page = self._page(playlistId, offset)
			if offset == 0 and onTotal is not None and isinstance(page.get("total"), int):
				onTotal(page["total"])
			items = page.get("items") or []
			for entry in items:
				out.append(simplifyEntry(entry, len(out)))
			offset += len(items)
			if not items or not page.get("next"):
				break
		return out[:maxItems]

	def _page(self, playlistId, offset):
		"""One page of 50 songs. Reading a big playlist makes many requests in a row:
		when Spotify asks to wait (429) a reasonable time, it waits and tries again."""
		for attempt in range(4):
			try:
				return self.request("GET", "/playlists/%s/items" % playlistId, {"limit": 50, "offset": offset, "additional_types": "track,episode"}) or {}
			except SpotifyError as e:
				if e.kind != "rateLimited" or attempt == 3 or (e.retryAfter or 0) > MAX_PAGE_RETRY_AFTER:
					raise
				self.sleep(max(1, e.retryAfter or 1))
		return {}

	def removeFromPlaylist(self, playlistId, uris, snapshotId=None):
		"""Removes songs from a playlist. Spotify removes every copy of each song."""
		playlistId = checkId(playlistId)
		uris = [u for u in uris if isTrackUri(u)][:MAX_REMOVE]
		if not uris:
			raise SpotifyError("badRequest", "no tracks")
		body = {"items": [{"uri": u} for u in uris]}
		if snapshotId:
			body["snapshot_id"] = str(snapshotId)[:200]
		try:
			result = self.request("DELETE", "/playlists/%s/items" % playlistId, body=body)
		except SpotifyError as e:
			if e.status not in (404, 405):
				raise
			old = {"tracks": body["items"]}
			if snapshotId:
				old["snapshot_id"] = body["snapshot_id"]
			result = self.request("DELETE", "/playlists/%s/tracks" % playlistId, body=old)
		return (result or {}).get("snapshot_id") if isinstance(result, dict) else None

	def reorder(self, playlistId, rangeStart, insertBefore, snapshotId=None):
		"""Moves one song (rangeStart) to before insertBefore. Returns the new snapshot id."""
		playlistId = checkId(playlistId)
		body = {"range_start": max(0, int(rangeStart)), "insert_before": max(0, int(insertBefore)), "range_length": 1}
		if snapshotId:
			body["snapshot_id"] = str(snapshotId)[:200]
		try:
			result = self.request("PUT", "/playlists/%s/items" % playlistId, body=body)
		except SpotifyError as e:
			if e.status not in (404, 405):
				raise
			result = self.request("PUT", "/playlists/%s/tracks" % playlistId, body=body)
		return (result or {}).get("snapshot_id") if isinstance(result, dict) else None

	def deletePlaylist(self, playlistId):
		"""Removes the playlist from the user's library. For a playlist of the user
		this is how Spotify deletes it (it can be recovered on the account page)."""
		playlistId = checkId(playlistId)
		try:
			return self.request("DELETE", "/me/library", {"uris": "spotify:playlist:" + playlistId})
		except SpotifyError as e:
			if e.status not in (404, 405):
				raise
			return self.request("DELETE", "/playlists/%s/followers" % playlistId)

	# -- search ------------------------------------------------------------------

	def search(self, text, kind, limit=SEARCH_LIMIT):
		if kind not in ("track", "playlist"):
			raise SpotifyError("badRequest", "kind")
		text = _text(text, MAX_QUERY)
		if not text:
			return []
		result = self.request("GET", "/search", {"q": text, "type": kind, "limit": max(1, min(int(limit), SEARCH_LIMIT))}) or {}
		block = result.get(kind + "s") or {}
		simplify = simplifyTrack if kind == "track" else simplifyPlaylist
		return [s for s in (simplify(i) for i in (block.get("items") or [])) if s]

	# -- player ------------------------------------------------------------------

	def playback(self):
		"""Current playback state, or None when nothing is playing on any device."""
		state = self.request("GET", "/me/player")
		return state if isinstance(state, dict) else None

	def devices(self):
		result = self.request("GET", "/me/player/devices") or {}
		return [d for d in (result.get("devices") or []) if isinstance(d, dict) and d.get("id")]

	def transfer(self, deviceId, play=False):
		return self.request("PUT", "/me/player", body={"device_ids": [_deviceId(deviceId)], "play": bool(play)})

	def play(self, deviceId=None, contextUri=None, uris=None, offsetUri=None, positionMs=None):
		body = {}
		if contextUri:
			if not isContextUri(contextUri):
				raise SpotifyError("badRequest", "context")
			body["context_uri"] = contextUri
			if offsetUri and isTrackUri(offsetUri):
				body["offset"] = {"uri": offsetUri}
		elif uris:
			body["uris"] = [u for u in uris if isTrackUri(u)][:100]
			if not body["uris"]:
				raise SpotifyError("badRequest", "uris")
		if positionMs:
			body["position_ms"] = max(0, int(positionMs))
		query = {"device_id": _deviceId(deviceId)} if deviceId else None
		return self.request("PUT", "/me/player/play", query, body if body else None)

	def pause(self, deviceId=None):
		return self.request("PUT", "/me/player/pause", {"device_id": _deviceId(deviceId)} if deviceId else None)

	def next(self, deviceId=None):
		return self.request("POST", "/me/player/next", {"device_id": _deviceId(deviceId)} if deviceId else None)

	def previous(self, deviceId=None):
		return self.request("POST", "/me/player/previous", {"device_id": _deviceId(deviceId)} if deviceId else None)

	def setVolume(self, percent, deviceId=None):
		query = {"volume_percent": max(0, min(100, int(percent)))}
		if deviceId:
			query["device_id"] = _deviceId(deviceId)
		return self.request("PUT", "/me/player/volume", query)

	def recentlyPlayed(self, limit=1):
		result = self.request("GET", "/me/player/recently-played", {"limit": max(1, min(int(limit), 50))}) or {}
		return [i for i in (result.get("items") or []) if isinstance(i, dict)]


_DEVICE_RE = re.compile(r"^[A-Za-z0-9._\-]{1,128}$")


def _deviceId(value):
	value = str(value or "")
	if not _DEVICE_RE.match(value):
		raise SpotifyError("badRequest", "device id")
	return value


def _retryAfter(headers):
	try:
		return max(0, int((headers or {}).get("Retry-After") or 1))
	except (TypeError, ValueError):
		return 1
