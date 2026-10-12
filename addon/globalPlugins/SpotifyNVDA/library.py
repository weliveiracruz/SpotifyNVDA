# -*- coding: UTF-8 -*-
# SpotifyNVDA - library.py
# Songs inside the playlists: loading (with a cache), searching, sorting and
# saving a new order on Spotify. No user interface here.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import threading
import unicodedata

from .errors import SpotifyError

SORT_PREFS_KEY = "sortPrefs"
#: Keys a playlist can be sorted by. "position" is the order saved on Spotify.
SORT_KEYS = ("position", "name", "artists", "album", "addedAt", "durationMs")
#: Saving an order moves one song per request: bigger changes are refused.
MAX_MOVES = 500


def normalize(text):
	"""Text for comparing and sorting: no accents, no case ("Água" == "agua")."""
	text = unicodedata.normalize("NFKD", str(text or ""))
	return "".join(c for c in text if not unicodedata.combining(c)).casefold().strip()


def sortEntries(entries, key="position", descending=False):
	if key not in SORT_KEYS:
		key = "position"
	if key in ("position", "durationMs"):
		def sortKey(e):
			return (int(e.get(key) or 0), e.get("position", 0))
	else:
		def sortKey(e):
			return (normalize(e.get(key)), e.get("position", 0))
	return sorted(entries, key=sortKey, reverse=bool(descending))


def matches(entry, words):
	text = normalize(" ".join((entry.get("name") or "", entry.get("artists") or "", entry.get("album") or "")))
	return all(w in text for w in words)


def planMoves(order):
	"""order: the current positions, listed in the wanted order. Returns the
	[(rangeStart, insertBefore)] moves that turn the playlist into that order,
	one song at a time (never removes anything, so an interruption loses nothing)."""
	n = len(order)
	if sorted(order) != list(range(n)):
		raise ValueError("not a permutation")
	current = list(range(n))
	moves = []
	for i, want in enumerate(order):
		j = current.index(want, i)
		if j != i:
			moves.append((j, i))
			current.insert(i, current.pop(j))
	return moves


class Library:
	def __init__(self, client, store=None):
		self.client = client
		self.store = store
		self._items = {}
		self._lock = threading.RLock()

	# -- songs of a playlist ---------------------------------------------------------

	def items(self, playlistId, refresh=False):
		with self._lock:
			if not refresh and playlistId in self._items:
				return list(self._items[playlistId])
		entries = self.client.playlistItems(playlistId)
		with self._lock:
			self._items[playlistId] = entries
		return list(entries)

	def cached(self, playlistId):
		with self._lock:
			entries = self._items.get(playlistId)
			return list(entries) if entries is not None else None

	def forget(self, playlistId=None):
		with self._lock:
			if playlistId is None:
				self._items.clear()
			else:
				self._items.pop(playlistId, None)

	# -- sort preferences (per playlist, kept with the session) -----------------------

	def sortPref(self, playlistId):
		prefs = (self.store.get(SORT_PREFS_KEY) if self.store else None) or {}
		key, descending = (prefs.get(playlistId) or ("position", False))[:2]
		return (key if key in SORT_KEYS else "position", bool(descending))

	def setSortPref(self, playlistId, key, descending):
		if not self.store:
			return
		prefs = self.store.get(SORT_PREFS_KEY) or {}
		if key == "position" and not descending:
			prefs.pop(playlistId, None)
		else:
			prefs[playlistId] = [key, bool(descending)]
		self.store.set(SORT_PREFS_KEY, prefs)

	def sorted(self, playlistId, entries=None):
		entries = self.cached(playlistId) if entries is None else entries
		key, descending = self.sortPref(playlistId)
		return sortEntries(entries or [], key, descending)

	# -- search inside the playlists ----------------------------------------------------

	def search(self, text, playlists, progress=None):
		"""Returns ([(playlist, [matching entries])], skipped). Playlists whose songs
		Spotify does not show (not owned, not collaborative) are skipped."""
		words = normalize(text).split()
		if not words:
			return [], 0
		found = []
		skipped = 0
		for n, playlist in enumerate(playlists):
			if progress:
				progress(n, len(playlists))
			try:
				entries = self.items(playlist["id"])
			except SpotifyError as e:
				if e.kind in ("forbidden", "notFound"):
					skipped += 1
					continue
				raise
			hits = [e for e in entries if matches(e, words)]
			if hits:
				found.append((playlist, hits))
		return found, skipped

	# -- save an order on Spotify --------------------------------------------------------

	def saveOrder(self, playlistId, key, descending):
		"""Changes the order of the playlist on Spotify. Re-reads the playlist first
		and moves the songs one by one. Returns the number of moves."""
		entries = self.items(playlistId, refresh=True)
		order = [e["position"] for e in sortEntries(entries, key, descending)]
		moves = planMoves(order)
		if len(moves) > MAX_MOVES:
			raise SpotifyError("tooManyChanges", str(len(moves)))
		snapshot = None
		for rangeStart, insertBefore in moves:
			snapshot = self.client.reorder(playlistId, rangeStart, insertBefore, snapshot)
		self.forget(playlistId)
		if self.store:
			self.setSortPref(playlistId, "position", False)
		return len(moves)
