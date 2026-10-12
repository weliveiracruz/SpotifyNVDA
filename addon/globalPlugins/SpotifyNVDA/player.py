# -*- coding: UTF-8 -*-
# SpotifyNVDA - player.py
# Playback rules: which device plays, play/pause, volume, next/previous and
# "continue the last song". No user interface here: every method returns data
# and raises SpotifyError; the plugin turns them into speech.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import time

from .api import isContextUri, isTrackUri, simplifyTrack
from .errors import SpotifyError

LAST_PLAYED_KEY = "lastPlayed"
#: Seconds to wait for the Spotify app to show up as a device after opening it.
DEVICE_WAIT = 15
#: Seconds between a next/previous command and reading the new song.
TRACK_CHANGE_DELAY = 0.6


def _isoToEpoch(text):
	"""'2026-10-11T12:34:56.789Z' -> seconds since the epoch (0 when unknown)."""
	try:
		import calendar

		text = str(text or "")
		return calendar.timegm(time.strptime(text[:19], "%Y-%m-%dT%H:%M:%S"))
	except (ValueError, OverflowError):
		return 0


class Player:
	def __init__(self, client, store, launchApp=None, sleep=time.sleep, clock=time.time, deviceWait=DEVICE_WAIT):
		self.client = client
		self.store = store
		self.launchApp = launchApp
		self.sleep = sleep
		self.clock = clock
		self.deviceWait = deviceWait

	# -- last played -----------------------------------------------------------------

	def remember(self, state):
		"""Keeps the song, its context and position, to continue it later."""
		if not isinstance(state, dict):
			return None
		track = simplifyTrack(state.get("item"))
		if not track:
			return None
		context = state.get("context") if isinstance(state.get("context"), dict) else {}
		contextUri = context.get("uri") if isContextUri(context.get("uri")) else None
		data = {
			"trackUri": track["uri"],
			"name": track["name"],
			"artists": track["artists"],
			"contextUri": contextUri,
			"positionMs": max(0, int(state.get("progress_ms") or 0)),
			"savedAt": self.clock(),
		}
		self.store.set(LAST_PLAYED_KEY, data)
		return data

	def lastPlayed(self):
		data = self.store.get(LAST_PLAYED_KEY)
		if isinstance(data, dict) and isTrackUri(data.get("trackUri")):
			return data
		return None

	# -- devices ---------------------------------------------------------------------

	@staticmethod
	def _pick(devices):
		usable = [d for d in devices if not d.get("is_restricted")]
		if not usable:
			return None
		for d in usable:
			if d.get("is_active"):
				return d
		for d in usable:
			if str(d.get("type") or "").lower() == "computer":
				return d
		return usable[0]

	def ensureDevice(self):
		"""Returns (deviceId, wasActive). Opens the Spotify app when there is no device."""
		device = self._pick(self.client.devices())
		if device is None and self.launchApp is not None:
			self.launchApp()
			waited = 0.0
			while device is None and waited < self.deviceWait:
				self.sleep(1)
				waited += 1
				device = self._pick(self.client.devices())
		if device is None:
			raise SpotifyError("noDevice")
		return device["id"], bool(device.get("is_active"))

	# -- commands --------------------------------------------------------------------

	def nowPlaying(self):
		"""Returns {'track': ..., 'isPlaying': bool, 'device': name} or None."""
		state = self.client.playback()
		if not state or not state.get("item"):
			return None
		self.remember(state)
		device = state.get("device") if isinstance(state.get("device"), dict) else {}
		return {
			"track": simplifyTrack(state.get("item")),
			"isPlaying": bool(state.get("is_playing")),
			"device": str(device.get("name") or ""),
		}

	def playPause(self):
		"""Returns 'paused', 'playing' or the track continued by resumeLast()."""
		state = self.client.playback()
		if state and state.get("device") and state.get("is_playing"):
			self.remember(state)
			self.client.pause()
			return "paused"
		if state and state.get("device") and state.get("item"):
			self.client.play()
			self.remember(state)
			return "playing"
		return self.resumeLast()

	def _changeTrack(self, command):
		try:
			command()
		except SpotifyError as e:
			if e.kind != "noDevice":
				raise
			deviceId, _active = self.ensureDevice()
			self.client.transfer(deviceId, play=True)
			self.sleep(TRACK_CHANGE_DELAY)
			command()
		self.sleep(TRACK_CHANGE_DELAY)
		info = self.nowPlaying()
		return info["track"] if info else None

	def next(self):
		return self._changeTrack(self.client.next)

	def previous(self):
		return self._changeTrack(self.client.previous)

	def changeVolume(self, delta):
		state = self.client.playback()
		device = state.get("device") if state else None
		if not isinstance(device, dict) or not device.get("id"):
			raise SpotifyError("noDevice")
		if device.get("supports_volume") is False or device.get("volume_percent") is None:
			raise SpotifyError("restricted", "volume")
		volume = max(0, min(100, int(device["volume_percent"]) + int(delta)))
		self.client.setVolume(volume, device["id"])
		return volume

	def playItem(self, item):
		"""Plays a simplified track or playlist (from search or the user playlists)."""
		deviceId = self._activeOrAnyDevice()
		if item.get("kind") == "playlist":
			self.client.play(deviceId, contextUri=item["uri"])
		else:
			self.client.play(deviceId, uris=[item["uri"]])
		return item

	def playInContext(self, contextUri, trackUri):
		"""Plays a playlist starting at one of its songs."""
		deviceId = self._activeOrAnyDevice()
		self.client.play(deviceId, contextUri=contextUri, offsetUri=trackUri)

	def _activeOrAnyDevice(self):
		deviceId, _active = self.ensureDevice()
		return deviceId

	def resumeLast(self):
		"""Continues the last song played on the account (RF-10).
		Returns the simplified track (dict with name and artists)."""
		state = self.client.playback()
		if state and state.get("device") and state.get("item"):
			if not state.get("is_playing"):
				self.client.play(state["device"].get("id") or None)
			self.remember(state)
			return simplifyTrack(state["item"])
		candidate = self._resumeCandidate()
		if candidate is None:
			raise SpotifyError("nothingToResume")
		deviceId = self._activeOrAnyDevice()
		trackUri = candidate["trackUri"]
		position = candidate.get("positionMs") or None
		contextUri = candidate.get("contextUri")
		played = False
		if contextUri:
			try:
				self.client.play(deviceId, contextUri=contextUri, offsetUri=trackUri, positionMs=position)
				played = True
			except SpotifyError as e:
				# The song may no longer be in that playlist, or the context is not playable.
				if e.kind not in ("badRequest", "notFound", "restricted"):
					raise
		if not played:
			self.client.play(deviceId, uris=[trackUri], positionMs=position)
		self.store.set(LAST_PLAYED_KEY, dict(candidate, savedAt=self.clock()))
		return {"kind": "track", "uri": trackUri, "name": candidate.get("name") or "", "artists": candidate.get("artists") or ""}

	def _resumeCandidate(self):
		local = self.lastPlayed()
		recent = None
		try:
			items = self.client.recentlyPlayed(1)
		except SpotifyError as e:
			if e.kind in ("notSignedIn", "auth", "network", "timeout"):
				raise
			items = []
		if items:
			item = items[0]
			track = simplifyTrack(item.get("track"))
			if track:
				context = item.get("context") if isinstance(item.get("context"), dict) else {}
				recent = {
					"trackUri": track["uri"],
					"name": track["name"],
					"artists": track["artists"],
					"contextUri": context.get("uri") if isContextUri(context.get("uri")) else None,
					"positionMs": 0,
					"savedAt": _isoToEpoch(item.get("played_at")),
				}
		if local and recent:
			if local["trackUri"] == recent["trackUri"]:
				return local
			# recently-played registers a song when it ends or after 30 s; the local copy
			# knows the position. Use whichever is newer.
			return local if local.get("savedAt", 0) >= recent["savedAt"] else recent
		return local or recent
