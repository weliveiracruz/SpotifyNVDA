# -*- coding: UTF-8 -*-
"""Unit tests of the add-on core (FUN-xx of docs/SDD-TESTES.md), against the
Spotify mock. No wxPython needed: runs on Python 3.11 (NVDA 2024/2025) and 3.13 (NVDA 2026).

Run:  python tests/_run_unittest.py"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse

import _helpers
import mock_spotify
import nvda_stubs
from mock_spotify import MOCK, CLIENT_ID, TRACKS

nvda_stubs.install(withGui=False)
core = _helpers.loadCore()
BASE = _helpers.startMock()
SpotifyError = core.errors.SpotifyError


def lastRequest(method, path):
	for r in reversed(MOCK.requests):
		if r["method"] == method and r["path"] == path:
			return r
	return None


class Base(unittest.TestCase):
	def setUp(self):
		MOCK.reset()
		self.launches = []
		self.svc = _helpers.makeService(core, launchApp=self._launch)

	def _launch(self):
		self.launches.append(1)
		MOCK.devicesHidden = False

	def signedIn(self):
		_helpers.signIn(self.svc)
		return self.svc


class SignIn(Base):
	def test_FUN01_signInFlow(self):
		user, browser = _helpers.signIn(self.svc)
		self.assertEqual(user["name"], "Wellington")
		self.assertTrue(self.svc.signedIn)
		url = urllib.parse.urlsplit(browser.urls[0])
		params = dict(urllib.parse.parse_qsl(url.query))
		self.assertEqual(params["response_type"], "code")
		self.assertEqual(params["client_id"], CLIENT_ID)
		self.assertEqual(params["code_challenge_method"], "S256")
		self.assertRegex(params["redirect_uri"], r"^http://127\.0\.0\.1:\d+/callback$")
		self.assertIn("playlist-modify-private", params["scope"].split())
		self.assertIn("user-modify-playback-state", params["scope"].split())
		status, page = browser.callbackStatus[0]
		self.assertEqual(status, 200)
		self.assertIn("Signed in to Spotify", page)

	def test_FUN01_noClientId(self):
		with self.assertRaises(SpotifyError) as cm:
			self.svc.signIn("", _helpers.freePort(), lambda url: None)
		self.assertEqual(cm.exception.kind, "noClientId")

	def test_FUN01_badClientIdFormat(self):
		with self.assertRaises(SpotifyError) as cm:
			self.svc.signIn("abc", _helpers.freePort(), lambda url: None)
		self.assertEqual(cm.exception.kind, "invalidClientId")

	def test_FUN01_userDenies(self):
		with self.assertRaises(SpotifyError) as cm:
			_helpers.signIn(self.svc, mode="deny")
		self.assertEqual(cm.exception.kind, "denied")
		self.assertFalse(self.svc.signedIn)

	def test_FUN01_cancel(self):
		cancel = threading.Event()
		threading.Timer(0.3, cancel.set).start()
		with self.assertRaises(SpotifyError) as cm:
			_helpers.signIn(self.svc, mode="nothing", cancelEvent=cancel)
		self.assertEqual(cm.exception.kind, "cancelled")

	def test_FUN01_timeout(self):
		with self.assertRaises(SpotifyError) as cm:
			_helpers.signIn(self.svc, mode="nothing", timeout=0.5)
		self.assertEqual(cm.exception.kind, "timeout")

	def test_FUN01_portInUse(self):
		import socket

		busy = socket.socket()
		busy.bind(("127.0.0.1", 0))
		busy.listen(1)
		try:
			with self.assertRaises(SpotifyError) as cm:
				_helpers.signIn(self.svc, port=busy.getsockname()[1])
			self.assertEqual(cm.exception.kind, "portInUse")
			self.assertEqual(cm.exception.detail, str(busy.getsockname()[1]))
		finally:
			busy.close()

	def test_FUN01_portFreedAfterSignIn(self):
		port = _helpers.freePort()
		_helpers.signIn(self.svc, port=port)
		self.svc.signOut()
		_helpers.signIn(self.svc, port=port)  # same port again: the listener was closed
		self.assertTrue(self.svc.signedIn)

	def test_FUN01_unregisteredUserInDevelopmentMode(self):
		MOCK.registered = False
		with self.assertRaises(SpotifyError) as cm:
			_helpers.signIn(self.svc)
		self.assertEqual(cm.exception.kind, "forbidden")
		self.assertFalse(self.svc.signedIn)


class StaySignedIn(Base):
	def test_FUN02_sessionSurvivesRestart(self):
		self.signedIn()
		again = _helpers.makeService(core, configPath=os.path.dirname(self.svc.store.path))
		self.assertTrue(again.signedIn)
		self.assertEqual(again.session.user["name"], "Wellington")
		self.assertEqual(again.client.me()["id"], mock_spotify.USER_ID)

	def test_FUN02_expiredAccessTokenIsRefreshed(self):
		self.signedIn()
		data = self.svc.store.get("session")
		oldRefresh = data["refreshToken"]
		data["expiresAt"] = time.time() - 10
		self.svc.store.set("session", data)
		self.svc.client.me()
		self.assertIsNotNone(lastRequest("POST", "/api/token"))
		newData = self.svc.store.get("session")
		self.assertNotEqual(newData["refreshToken"], oldRefresh, "rotated refresh token must be saved")
		self.assertGreater(newData["expiresAt"], time.time() + 3000)

	def test_FUN02_refreshWithoutRotationKeepsToken(self):
		self.signedIn()
		MOCK.rotateRefresh = False
		old = self.svc.store.get("session")["refreshToken"]
		self.svc.session.accessToken(force=True)
		self.assertEqual(self.svc.store.get("session")["refreshToken"], old)

	def test_FUN02_401RefreshesAndRetries(self):
		self.signedIn()
		MOCK.expireAll()
		self.assertEqual(self.svc.client.me()["id"], mock_spotify.USER_ID)

	def test_FUN02_revokedRefreshTokenEndsSession(self):
		self.signedIn()
		MOCK.refreshTokens.clear()
		MOCK.expireAll()
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.me()
		self.assertEqual(cm.exception.kind, "auth")
		self.assertFalse(self.svc.signedIn)

	def test_FUN02_networkErrorKeepsSession(self):
		self.signedIn()
		MOCK.tokenFailure = (503, {"error": "server_error"})
		with self.assertRaises(SpotifyError) as cm:
			self.svc.session.accessToken(force=True)
		self.assertEqual(cm.exception.kind, "server")
		self.assertTrue(self.svc.signedIn)

	def test_FUN02_notSignedIn(self):
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.me()
		self.assertEqual(cm.exception.kind, "notSignedIn")

	def test_FUN02_damagedFileMeansSignedOut(self):
		self.signedIn()
		with open(self.svc.store.path, "w", encoding="utf-8") as f:
			f.write("{not json")
		fresh = _helpers.makeService(core, configPath=os.path.dirname(self.svc.store.path))
		self.assertFalse(fresh.signedIn)


class Playlists(Base):
	def test_FUN03_listAllPlaylistsWithPaging(self):
		self.signedIn()
		items = self.svc.client.myPlaylists()
		self.assertEqual(len(items), 55)
		self.assertEqual(items[0]["name"], "Playlist 1")
		self.assertEqual(items[0]["total"], 1)
		self.assertEqual(items[4]["ownerId"], "someone")
		limits = [r["query"]["limit"] for r in MOCK.requests if r["path"] == "/v1/me/playlists"]
		self.assertTrue(all(int(x) <= 50 for x in limits))

	def test_FUN03_oldTracksFieldStillRead(self):
		simplified = core.api.simplifyPlaylist({"id": "abc", "uri": "spotify:playlist:abc", "name": "X", "owner": {"id": "u"}, "tracks": {"total": 7}})
		self.assertEqual(simplified["total"], 7)

	def test_FUN06_createPlaylist(self):
		self.signedIn()
		p = self.svc.client.createPlaylist("  Minha lista ", "desc", public=False)
		self.assertEqual(p["name"], "Minha lista")
		body = json.loads(lastRequest("POST", "/v1/me/playlists")["body"])
		self.assertEqual(body, {"name": "Minha lista", "description": "desc", "public": False})

	def test_FUN06_createPlaylistOldEndpoint(self):
		self.signedIn()
		MOCK.newEndpoints = False
		p = self.svc.client.createPlaylist("Antiga")
		self.assertEqual(p["name"], "Antiga")
		self.assertIsNotNone(lastRequest("POST", "/v1/users/%s/playlists" % mock_spotify.USER_ID))

	def test_FUN06_emptyNameRefused(self):
		self.signedIn()
		with self.assertRaises(SpotifyError):
			self.svc.client.createPlaylist("   ")

	def test_FUN06_addToPlaylist(self):
		self.signedIn()
		self.svc.client.addToPlaylist("p0000001", [TRACKS[0]["uri"]])
		self.assertEqual(MOCK.playlists[0]["tracks_added"], [TRACKS[0]["uri"]])
		MOCK.newEndpoints = False
		self.svc.client.addToPlaylist("p0000002", [TRACKS[1]["uri"]])
		self.assertEqual(MOCK.playlists[1]["tracks_added"], [TRACKS[1]["uri"]])


class Search(Base):
	def test_FUN07_searchTracks(self):
		self.signedIn()
		items = self.svc.client.search("ipanema", "track")
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["name"], "Garota de Ipanema")
		self.assertEqual(items[0]["artists"], "Tom Jobim")
		self.assertEqual(items[0]["kind"], "track")

	def test_FUN07_emptySearch(self):
		self.signedIn()
		self.assertEqual(self.svc.client.search("   ", "track"), [])
		self.assertEqual(self.svc.client.search("zzzz", "track"), [])

	def test_FUN08_searchPlaylistsSkipsNull(self):
		self.signedIn()
		items = self.svc.client.search("Playlist 1", "playlist")
		self.assertEqual(len(items), 10)
		self.assertTrue(all(i["kind"] == "playlist" for i in items))

	def test_FUN08_limitAtMost10(self):
		self.signedIn()
		self.svc.client.search("a", "track", limit=50)
		self.assertEqual(lastRequest("GET", "/v1/search")["query"]["limit"], "10")


class Playback(Base):
	def test_FUN04_playTrackPrefersComputer(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		self.assertEqual(MOCK.activeDevice()["id"], "dev-computer")
		self.assertEqual(MOCK.player["item"]["id"], TRACKS[0]["id"])

	def test_FUN04_playPlaylist(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "playlist", "uri": "spotify:playlist:p0000003", "name": "x"})
		self.assertEqual(MOCK.player["context"]["uri"], "spotify:playlist:p0000003")

	def test_FUN04_opensSpotifyAppWhenNoDevice(self):
		self.signedIn()
		MOCK.devicesHidden = True
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[1]["uri"], "name": "x"})
		self.assertEqual(len(self.launches), 1)
		self.assertTrue(MOCK.player["is_playing"])

	def test_FUN04_noDeviceAtAll(self):
		self.signedIn()
		MOCK.devicesHidden = True
		self.svc.player.launchApp = lambda: None
		with self.assertRaises(SpotifyError) as cm:
			self.svc.player.playItem({"kind": "track", "uri": TRACKS[1]["uri"], "name": "x"})
		self.assertEqual(cm.exception.kind, "noDevice")

	def test_FUN05_playPause(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		self.assertEqual(self.svc.player.playPause(), "paused")
		self.assertFalse(MOCK.player["is_playing"])
		self.assertEqual(self.svc.player.playPause(), "playing")
		self.assertTrue(MOCK.player["is_playing"])

	def test_FUN05_nextPrevious(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		track = self.svc.player.next()
		self.assertEqual(track["name"], TRACKS[1]["name"])
		track = self.svc.player.previous()
		self.assertEqual(track["name"], TRACKS[0]["name"])

	def test_FUN05_nextWithoutActiveDeviceTransfers(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		MOCK.activate("none")
		track = self.svc.player.next()
		self.assertEqual(track["name"], TRACKS[1]["name"])

	def test_FUN05_volume(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		self.assertEqual(self.svc.player.changeVolume(10), 60)
		self.assertEqual(self.svc.player.changeVolume(-25), 35)
		self.assertEqual(self.svc.player.changeVolume(500), 100)
		self.assertEqual(self.svc.player.changeVolume(-500), 0)

	def test_FUN05_volumeNotSupported(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		MOCK.devices[0]["supports_volume"] = False
		with self.assertRaises(SpotifyError) as cm:
			self.svc.player.changeVolume(10)
		self.assertEqual(cm.exception.kind, "restricted")

	def test_FUN05_volumeWithoutDevice(self):
		self.signedIn()
		with self.assertRaises(SpotifyError) as cm:
			self.svc.player.changeVolume(10)
		self.assertEqual(cm.exception.kind, "noDevice")

	def test_FUN05_premiumRequired(self):
		self.signedIn()
		MOCK.product = "free"
		with self.assertRaises(SpotifyError) as cm:
			self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		self.assertEqual(cm.exception.kind, "premiumRequired")

	def test_FUN11_nowPlaying(self):
		self.signedIn()
		self.assertIsNone(self.svc.player.nowPlaying())
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[2]["uri"], "name": "x"})
		info = self.svc.player.nowPlaying()
		self.assertEqual(info["track"]["name"], "Mas que nada")
		self.assertTrue(info["isPlaying"])
		self.assertEqual(info["device"], "MEU-PC")


class Resume(Base):
	def test_FUN10_resumePausedPlayback(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[2]["uri"], "name": "x"})
		self.svc.player.playPause()
		track = self.svc.player.resumeLast()
		self.assertEqual(track["name"], "Mas que nada")
		self.assertTrue(MOCK.player["is_playing"])

	def test_FUN10_resumeFromAccountHistory(self):
		self.signedIn()
		track = self.svc.player.resumeLast()
		self.assertEqual(track["name"], TRACKS[3]["name"])
		self.assertEqual(MOCK.player["context"]["uri"], "spotify:playlist:p0000001")
		self.assertEqual(MOCK.player["item"]["id"], TRACKS[3]["id"])

	def test_FUN10_resumeLocalWithPosition(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "playlist", "uri": "spotify:playlist:p0000002", "name": "x"})
		MOCK.player["progress_ms"] = 61000
		self.svc.player.nowPlaying()  # remembers song, context and position
		MOCK.player = None
		MOCK.activate("none")
		track = self.svc.player.resumeLast()
		self.assertEqual(track["name"], TRACKS[0]["name"])
		self.assertEqual(MOCK.player["progress_ms"], 61000)
		self.assertEqual(MOCK.player["context"]["uri"], "spotify:playlist:p0000002")

	def test_FUN10_sessionAfterRestartStillResumes(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[4]["uri"], "name": "x"})
		self.svc.player.nowPlaying()
		MOCK.player = None
		MOCK.activate("none")
		MOCK.recent = []
		again = _helpers.makeService(core, configPath=os.path.dirname(self.svc.store.path))
		self.assertEqual(again.player.resumeLast()["name"], TRACKS[4]["name"])

	def test_FUN10_invalidContextFallsBackToSong(self):
		self.signedIn()
		MOCK.recent[0]["context"] = {"uri": "spotify:playlist:gone0000"}
		track = self.svc.player.resumeLast()
		self.assertEqual(track["name"], TRACKS[3]["name"])
		self.assertIsNone(MOCK.player["context"])

	def test_FUN10_nothingToResume(self):
		self.signedIn()
		MOCK.recent = []
		with self.assertRaises(SpotifyError) as cm:
			self.svc.player.resumeLast()
		self.assertEqual(cm.exception.kind, "nothingToResume")

	def test_FUN10_newerOfLocalAndHistory(self):
		self.signedIn()
		self.svc.store.set("lastPlayed", {"trackUri": TRACKS[5]["uri"], "name": "old", "artists": "", "contextUri": None, "positionMs": 5, "savedAt": 1000})
		track = self.svc.player.resumeLast()
		self.assertEqual(track["name"], TRACKS[3]["name"], "history (2026) is newer than the local copy (1970)")


class SignOut(Base):
	def test_FUN09_signOutDeletesEverything(self):
		self.signedIn()
		self.svc.player.playItem({"kind": "track", "uri": TRACKS[0]["uri"], "name": "x"})
		self.svc.player.nowPlaying()
		self.assertTrue(os.path.exists(self.svc.store.path))
		self.svc.signOut()
		self.assertFalse(self.svc.signedIn)
		self.assertFalse(os.path.exists(self.svc.store.path))
		self.assertIsNone(self.svc.store.get("lastPlayed"))
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.me()
		self.assertEqual(cm.exception.kind, "notSignedIn")


class Errors(Base):
	def test_FUN12_rateLimitShortIsRetried(self):
		self.signedIn()
		MOCK.fail("GET", "/v1/me", 429, {"error": {"status": 429}}, {"Retry-After": "1"})
		self.assertEqual(self.svc.client.me()["id"], mock_spotify.USER_ID)

	def test_FUN12_rateLimitLong(self):
		self.signedIn()
		MOCK.fail("GET", "/v1/me", 429, {"error": {"status": 429}}, {"Retry-After": "120"})
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.me()
		self.assertEqual(cm.exception.kind, "rateLimited")
		self.assertEqual(cm.exception.retryAfter, 120)

	def test_FUN12_serverError(self):
		self.signedIn()
		MOCK.fail("GET", "/v1/me", 503, {"error": {"status": 503, "message": "Service unavailable"}})
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.me()
		self.assertEqual(cm.exception.kind, "server")

	def test_FUN12_networkDown(self):
		self.signedIn()
		self.svc.client.baseUrl = "http://127.0.0.1:%d/v1" % _helpers.freePort()
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.me()
		self.assertEqual(cm.exception.kind, "network")

	def test_FUN12_everyErrorHasAMessage(self):
		import importlib

		messages = importlib.import_module("SpotifyNVDA.messages")
		for kind in core.errors.KINDS:
			text = messages.errorMessage(SpotifyError(kind, "1234"))
			self.assertTrue(text and len(text) < 300, kind)
		self.assertIn("User Management", messages.errorMessage(SpotifyError("forbidden", "User not registered in the Developer Dashboard")))


class Compatibility(unittest.TestCase):
	def test_FUN16_everyAddonFileCompilesOnThisPython(self):
		errors = []
		for folder, dirs, files in os.walk(os.path.join(_helpers.ROOT, "addon")):
			for name in files:
				if name.endswith(".py"):
					path = os.path.join(folder, name)
					with open(path, encoding="utf-8") as f:
						try:
							compile(f.read(), path, "exec")
						except SyntaxError as e:
							errors.append("%s: %s" % (path, e))
		self.assertEqual(errors, [])


class Format2026(Base):
	"""Spotify Web API in development mode after the February 2026 changes."""

	def test_FUN18_meWithoutProduct(self):
		import importlib

		messages = importlib.import_module("SpotifyNVDA.messages")
		user, _browser = _helpers.signIn(self.svc)
		self.assertEqual(user["product"], "")
		self.assertEqual(messages.statusText(True, user), "Signed in as Wellington")
		self.assertEqual(messages.statusText(True, {"name": "W", "product": "premium"}), "Signed in as W (Premium)")
		self.assertIn("free account", messages.statusText(True, {"name": "W", "product": "free"}))

	def test_FUN18_playlistOfOthersWithoutItems(self):
		import importlib

		messages = importlib.import_module("SpotifyNVDA.messages")
		self.signedIn()
		other = self.svc.client.myPlaylists()[4]
		self.assertEqual(other["ownerId"], "someone")
		self.assertIsNone(other["total"])
		self.assertEqual(messages.itemText(other), "Playlist 5 - Someone")

	def test_FUN18_newEndpointsUsedFirst(self):
		self.signedIn()
		self.svc.client.createPlaylist("Nova")
		self.svc.client.addToPlaylist("p0000001", [TRACKS[0]["uri"]])
		paths = [r["path"] for r in MOCK.requests if r["method"] == "POST" and r["path"].startswith("/v1/")]
		self.assertEqual(paths, ["/v1/me/playlists", "/v1/playlists/p0000001/items"])


class FakeWin:
	"""Fake Windows: windows are (hwnd, pid); pid 100 is spotify.exe once started."""

	def __init__(self, running=False, stealFocus=False, startOk=True):
		self.windows = [(1, 10), (2, 20)]  # other programs (NVDA, the browser)
		self.names = {10: "nvda.exe", 20: "msedge.exe"}
		self.visible = {1: True, 2: True}
		self.fg = 1
		self.executed = []
		self.hidden = []
		self.foregroundSet = []
		self.stealFocus = stealFocus
		self.startOk = startOk
		if running:
			self._spotify()

	def _spotify(self):
		self.windows += [(50, 100), (51, 100)]
		self.names[100] = "spotify.exe"
		self.visible.update({50: True, 51: False})
		if self.stealFocus:
			self.fg = 50

	def topWindows(self):
		return list(self.windows)

	def processName(self, pid):
		return self.names.get(pid, "")

	def isVisible(self, hwnd):
		return self.visible.get(hwnd, False)

	def isMinimized(self, hwnd):
		return True

	def hide(self, hwnd):
		self.hidden.append(hwnd)
		self.visible[hwnd] = False

	def foreground(self):
		return self.fg

	def setForeground(self, hwnd):
		self.foregroundSet.append(hwnd)
		self.fg = hwnd

	def shellExecute(self, path, arguments):
		self.executed.append((path, arguments))
		if self.startOk:
			self._spotify()
		return self.startOk


class Background(unittest.TestCase):
	def launcher(self, win, exe="C:/Users/x/AppData/Local/Microsoft/WindowsApps/Spotify.exe", startfile=None):
		ticks = iter(range(1000))
		return core.background.BackgroundLauncher(win=win, findExe=lambda: exe, startfile=startfile, sleep=lambda s: None, clock=lambda: next(ticks))

	def test_FUN19_startsMinimizedWithoutFocus(self):
		win = FakeWin()
		bl = self.launcher(win)
		self.assertEqual(bl.launch(hide=True), "started")
		bl._hider.join(5)
		self.assertEqual(win.executed, [("C:/Users/x/AppData/Local/Microsoft/WindowsApps/Spotify.exe", "--autostart --minimized")])
		self.assertEqual(core.background.SW_SHOWMINNOACTIVE, 7)

	def test_FUN19_hidesOnlySpotifyWindows(self):
		win = FakeWin()
		bl = self.launcher(win)
		bl.launch(hide=True)
		bl._hider.join(5)
		self.assertIn(50, win.hidden)
		self.assertNotIn(1, win.hidden)
		self.assertNotIn(2, win.hidden)
		self.assertTrue(win.visible[1] and win.visible[2])

	def test_FUN19_givesTheFocusBack(self):
		win = FakeWin(stealFocus=True)
		bl = self.launcher(win)
		bl.launch(hide=True)
		bl._hider.join(5)
		self.assertEqual(win.foregroundSet[:1], [1])
		self.assertEqual(win.fg, 1)

	def test_FUN19_alreadyRunningIsNotTouched(self):
		win = FakeWin(running=True)
		bl = self.launcher(win)
		self.assertEqual(bl.launch(hide=True), "running")
		self.assertEqual(win.executed, [])
		self.assertEqual(win.hidden, [])

	def test_FUN19_optionOffDoesNotHide(self):
		win = FakeWin()
		bl = self.launcher(win)
		bl.launch(hide=False)
		self.assertIsNone(bl._hider)
		self.assertEqual(win.hidden, [])
		self.assertEqual(win.executed[0][1], "--autostart --minimized")

	def test_FUN19_unknownInstallationUsesProtocol(self):
		opened = []
		win = FakeWin()
		bl = self.launcher(win, exe=None, startfile=opened.append)
		self.assertEqual(bl.launch(hide=False), "started")
		self.assertEqual(opened, ["spotify:"])
		self.assertEqual(win.executed, [])

	def test_FUN19_notInstalled(self):
		def fail(uri):
			raise OSError("no association")

		bl = self.launcher(FakeWin(), exe=None, startfile=fail)
		self.assertEqual(bl.launch(), "unavailable")

	def test_FUN19_executableSearchOrder(self):
		env = {"APPDATA": "A", "LOCALAPPDATA": "L"}
		paths = core.background.candidateExecutables(env)
		self.assertEqual(paths, [os.path.join("A", "Spotify", "Spotify.exe"), os.path.join("L", "Microsoft", "WindowsApps", "Spotify.exe")])
		self.assertEqual(core.background.findExecutable(exists=lambda p: p == paths[1], env=env), paths[1])
		self.assertIsNone(core.background.findExecutable(exists=lambda p: False, env=env))

	@unittest.skipUnless(sys.platform == "win32", "Windows only")
	def test_FUN19_realWindowsFunctions(self):
		win = core.background.Win32()
		self.assertIn(win.processName(os.getpid()), ("python.exe", "pythonw.exe"))
		windows = win.topWindows()
		self.assertTrue(windows and all(isinstance(p, int) for _h, p in windows))
		bl = core.background.BackgroundLauncher(win=win)
		mine = [h for h, p in windows if p == os.getpid()]
		self.assertTrue(all(h not in bl.spotifyWindows() for h in mine))


def playlistById(pid):
	return [p for p in MOCK.playlists if p["id"] == pid][0]


class PlaylistSongs(Base):
	def test_FUN20_songsInOrderWithFields(self):
		self.signedIn()
		entries = self.svc.client.playlistItems("p0000003")
		expected = [e["item"]["name"] for e in playlistById("p0000003")["entries"]]
		self.assertEqual([e["name"] for e in entries], expected)
		self.assertEqual([e["position"] for e in entries], [0, 1, 2])
		self.assertTrue(all(e["playable"] and e["addedAt"].startswith("2026-01-") for e in entries))
		req = lastRequest("GET", "/v1/playlists/p0000003/items")
		self.assertEqual(req["query"]["limit"], "50")

	def test_FUN20_paging(self):
		self.signedIn()
		p = playlistById("p0000006")
		p["entries"] = [{"added_at": "2026-01-01T00:00:00Z", "is_local": False, "item": TRACKS[i % 6]} for i in range(123)]
		entries = self.svc.client.playlistItems("p0000006")
		self.assertEqual(len(entries), 123)
		self.assertEqual(entries[-1]["position"], 122)

	def test_FUN20_oldTrackFieldAndLocalFile(self):
		old = core.api.simplifyEntry({"added_at": "x", "track": TRACKS[0]}, 7)
		self.assertEqual((old["name"], old["position"], old["playable"]), ("Garota de Ipanema", 7, True))
		local = core.api.simplifyEntry({"is_local": True, "item": {"name": "Demo", "uri": "spotify:local:a:b:c:1", "artists": [{"name": "Eu"}]}}, 3)
		self.assertEqual((local["name"], local["artists"], local["playable"], local["local"], local["uri"]), ("Demo", "Eu", False, True, ""))
		removed = core.api.simplifyEntry({"item": None}, 0)
		self.assertFalse(removed["playable"])

	def test_FUN20_someoneElsesPlaylistIsForbidden(self):
		self.signedIn()
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.playlistItems("p0000005")
		self.assertEqual(cm.exception.kind, "forbidden")

	def test_FUN20_playInContext(self):
		self.signedIn()
		self.svc.player.playInContext("spotify:playlist:p0000003", TRACKS[4]["uri"])
		self.assertEqual(MOCK.player["context"]["uri"], "spotify:playlist:p0000003")
		self.assertEqual(MOCK.player["item"]["id"], TRACKS[4]["id"])

	def test_FUN20_cache(self):
		self.signedIn()
		lib = self.svc.library
		lib.items("p0000003")
		lib.items("p0000003")
		self.assertEqual(len([r for r in MOCK.requests if r["path"] == "/v1/playlists/p0000003/items"]), 1)
		lib.items("p0000003", refresh=True)
		self.assertEqual(len([r for r in MOCK.requests if r["path"] == "/v1/playlists/p0000003/items"]), 2)
		self.svc.signOut()
		self.assertIsNone(lib.cached("p0000003"))


class SortAndSearch(unittest.TestCase):
	E = [
		{"name": "Chega de Saudade", "artists": "João Gilberto", "album": "B", "addedAt": "2026-01-03", "durationMs": 300, "position": 0},
		{"name": "Águas de Março", "artists": "Elis Regina", "album": "a", "addedAt": "2026-01-01", "durationMs": 100, "position": 1},
		{"name": "evidências", "artists": "Chitãozinho", "album": "C", "addedAt": "2026-01-02", "durationMs": 200, "position": 2},
	]

	def names(self, key, desc=False):
		return [e["name"] for e in core.library.sortEntries(self.E, key, desc)]

	def test_FUN22_sortKeys(self):
		self.assertEqual(self.names("name"), ["Águas de Março", "Chega de Saudade", "evidências"])
		self.assertEqual(self.names("name", True), ["evidências", "Chega de Saudade", "Águas de Março"])
		self.assertEqual(self.names("artists"), ["evidências", "Águas de Março", "Chega de Saudade"])
		self.assertEqual(self.names("album"), ["Águas de Março", "Chega de Saudade", "evidências"])
		self.assertEqual(self.names("addedAt"), ["Águas de Março", "evidências", "Chega de Saudade"])
		self.assertEqual(self.names("durationMs", True), ["Chega de Saudade", "evidências", "Águas de Março"])
		self.assertEqual(self.names("position"), ["Chega de Saudade", "Águas de Março", "evidências"])
		self.assertEqual(self.names("bogus"), self.names("position"))

	def test_FUN22_stableForEqualKeys(self):
		same = [dict(e, name="X") for e in self.E]
		self.assertEqual([e["position"] for e in core.library.sortEntries(same, "name")], [0, 1, 2])

	def test_FUN21_matchingIgnoresAccentsAndCase(self):
		words = core.library.normalize("AGUAS marco").split()
		self.assertEqual([e["name"] for e in self.E if core.library.matches(e, words)], ["Águas de Março"])
		self.assertTrue(core.library.matches(self.E[0], ["joao"]))
		self.assertFalse(core.library.matches(self.E[0], ["joao", "elis"]))

	def test_FUN22_planMovesReachesEveryOrder(self):
		import itertools
		import random

		rng = random.Random(7)
		orders = [list(p) for p in itertools.permutations(range(5))] + [rng.sample(range(40), 40) for _ in range(30)]
		for order in orders:
			current = list(range(len(order)))
			for start, before in core.library.planMoves(order):
				item = current.pop(start)
				current.insert(before if before < start else before - 1, item)
			self.assertEqual(current, order)
			self.assertLessEqual(len(core.library.planMoves(order)), max(0, len(order) - 1))
		self.assertEqual(core.library.planMoves([0, 1, 2]), [])
		with self.assertRaises(ValueError):
			core.library.planMoves([0, 0, 1])


class SaveOrderAndDelete(Base):
	def test_FUN22_saveOrderOnSpotify(self):
		self.signedIn()
		pid = "p0000006"
		moves = self.svc.library.saveOrder(pid, "name", False)
		names = [e["item"]["name"] for e in playlistById(pid)["entries"]]
		self.assertEqual(names, sorted(names, key=core.library.normalize))
		self.assertEqual(len(MOCK.reorders), moves)
		self.assertTrue(all(r[3] == ("snap-%d" % i if i else None) for i, r in enumerate(MOCK.reorders)))
		body = json.loads([r for r in MOCK.requests if r["method"] == "PUT" and r["path"] == "/v1/playlists/%s/items" % pid][0]["body"])
		self.assertEqual(set(body), {"range_start", "insert_before", "range_length"})

	def test_FUN22_saveOrderKeepsLocalFilesAndCount(self):
		self.signedIn()
		before = list(playlistById("p0000002")["entries"])
		self.svc.library.saveOrder("p0000002", "name", True)
		after = playlistById("p0000002")["entries"]
		self.assertEqual(len(after), len(before))
		self.assertEqual(sorted(id(e) for e in after), sorted(id(e) for e in before))

	def test_FUN22_saveOrderTooBig(self):
		self.signedIn()
		saved = core.library.MAX_MOVES
		core.library.MAX_MOVES = 1
		try:
			with self.assertRaises(SpotifyError) as cm:
				self.svc.library.saveOrder("p0000006", "name", True)
			self.assertEqual(cm.exception.kind, "tooManyChanges")
			self.assertEqual(MOCK.reorders, [])
		finally:
			core.library.MAX_MOVES = saved

	def test_FUN22_saveOrderNotAllowedOnSomeoneElses(self):
		self.signedIn()
		with self.assertRaises(SpotifyError) as cm:
			self.svc.library.saveOrder("p0000005", "name", False)
		self.assertEqual(cm.exception.kind, "forbidden")

	def test_FUN22_reorderFallsBackToOldPath(self):
		self.signedIn()
		MOCK.fail("PUT", "/v1/playlists/p0000003/items", 404, {"error": {"status": 404}})
		MOCK.newEndpoints = True
		try:
			self.svc.client.reorder("p0000003", 2, 0)
		except SpotifyError:
			pass
		self.assertIsNotNone(lastRequest("PUT", "/v1/playlists/p0000003/tracks"))

	def test_FUN22_sortPreferencePerPlaylist(self):
		self.signedIn()
		lib = self.svc.library
		lib.setSortPref("p0000003", "artists", True)
		self.assertEqual(lib.sortPref("p0000003"), ("artists", True))
		self.assertEqual(lib.sortPref("p0000006"), ("position", False))
		again = _helpers.makeService(core, configPath=os.path.dirname(self.svc.store.path))
		self.assertEqual(again.library.sortPref("p0000003"), ("artists", True))
		lib.setSortPref("p0000003", "position", False)
		self.assertNotIn("p0000003", self.svc.store.get("sortPrefs") or {})

	def test_FUN23_deletePlaylist(self):
		self.signedIn()
		self.svc.client.deletePlaylist("p0000007")
		req = lastRequest("DELETE", "/v1/me/library")
		self.assertEqual(req["query"]["uris"], "spotify:playlist:p0000007")
		self.assertNotIn("p0000007", [p["id"] for p in MOCK.playlists])

	def test_FUN23_deleteFallsBackToFollowers(self):
		self.signedIn()
		MOCK.fail("DELETE", "/v1/me/library", 404, {"error": {"status": 404}})
		try:
			self.svc.client.deletePlaylist("p0000007")
		except SpotifyError:
			pass
		self.assertIsNotNone(lastRequest("DELETE", "/v1/playlists/p0000007/followers"))

	def test_FUN21_searchSkipsForbidden(self):
		self.signedIn()
		playlists = self.svc.client.myPlaylists()[:6]
		found, skipped = self.svc.library.search("ipanema", playlists)
		self.assertEqual(skipped, 1)  # Playlist 5 belongs to someone else
		self.assertTrue(found)
		self.assertTrue(all(all(e["name"] == "Garota de Ipanema" for e in hits) for _p, hits in found))
		self.assertEqual(self.svc.library.search("   ", playlists), ([], 0))


class BigPlaylistsAndRemove(Base):
	def big(self, pid="p0000006", count=2500):
		p = playlistById(pid)
		p["entries"] = [{"added_at": "2026-01-01T00:00:00Z", "is_local": False, "item": TRACKS[i % 6]} for i in range(count)]
		return p

	def test_FUN24_wholePlaylistIsRead(self):
		self.signedIn()
		self.big()
		totals = []
		entries = self.svc.client.playlistItems("p0000006", onTotal=totals.append)
		self.assertEqual(len(entries), 2500)
		self.assertEqual(totals, [2500])
		self.assertEqual([e["position"] for e in entries], list(range(2500)))

	def test_FUN24_limitIsSpotifyMaximum(self):
		self.assertEqual(core.api.MAX_PLAYLIST_ITEMS, 10000)

	def test_FUN24_waitsWhenSpotifyAsksDuringPaging(self):
		self.signedIn()
		self.big(count=300)
		MOCK.pageRateLimit = (150, 12)
		slept = []
		self.svc.client.sleep = slept.append
		entries = self.svc.client.playlistItems("p0000006")
		self.assertEqual(len(entries), 300)
		self.assertEqual(slept, [12])

	def test_FUN24_tooLongWaitIsAnError(self):
		self.signedIn()
		self.big(count=300)
		MOCK.pageRateLimit = (100, 120)
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.playlistItems("p0000006")
		self.assertEqual(cm.exception.kind, "rateLimited")

	def test_FUN25_removeSong(self):
		self.signedIn()
		entries = self.svc.library.items("p0000003")
		target = entries[1]
		copies = self.svc.library.removeSong("p0000003", target)
		self.assertEqual(copies, 1)
		self.assertNotIn(target["uri"], [e["item"]["uri"] for e in playlistById("p0000003")["entries"]])
		req = lastRequest("DELETE", "/v1/playlists/p0000003/items")
		self.assertEqual(json.loads(req["body"]), {"items": [{"uri": target["uri"]}]})
		self.assertIsNone(self.svc.library.cached("p0000003"), "cache is dropped after a change")

	def test_FUN25_duplicatesAreCountedAndAllRemoved(self):
		self.signedIn()
		p = playlistById("p0000006")
		p["entries"] = [{"added_at": "x", "is_local": False, "item": t} for t in (TRACKS[0], TRACKS[1], TRACKS[0])]
		entries = self.svc.library.items("p0000006")
		self.assertEqual(self.svc.library.copies("p0000006", TRACKS[0]["uri"]), 2)
		self.assertEqual(self.svc.library.removeSong("p0000006", entries[0]), 2)
		self.assertEqual([e["item"]["uri"] for e in p["entries"]], [TRACKS[1]["uri"]])

	def test_FUN25_localFileCannotBeRemoved(self):
		self.signedIn()
		local = self.svc.library.items("p0000002")[-1]
		before = len(MOCK.requests)
		with self.assertRaises(SpotifyError) as cm:
			self.svc.library.removeSong("p0000002", local)
		self.assertEqual(cm.exception.kind, "restricted")
		self.assertEqual(len(MOCK.requests), before)

	def test_FUN25_removeFallsBackToOldPath(self):
		self.signedIn()
		MOCK.fail("DELETE", "/v1/playlists/p0000003/items", 404, {"error": {"status": 404}})
		self.svc.client.removeFromPlaylist("p0000003", [TRACKS[3]["uri"]])
		req = lastRequest("DELETE", "/v1/playlists/p0000003/tracks")
		self.assertEqual(json.loads(req["body"]), {"tracks": [{"uri": TRACKS[3]["uri"]}]})

	def test_FUN25_someoneElsesPlaylistIsRefused(self):
		self.signedIn()
		with self.assertRaises(SpotifyError) as cm:
			self.svc.client.removeFromPlaylist("p0000005", [TRACKS[0]["uri"]])
		self.assertEqual(cm.exception.kind, "forbidden")


class Helpers(unittest.TestCase):
	def test_FUN01_clientIdValidation(self):
		self.assertTrue(core.auth.isValidClientId(" 0123456789abcdef0123456789ABCDEF "))
		self.assertFalse(core.auth.isValidClientId("0123456789abcdef0123456789abcde"))
		self.assertFalse(core.auth.isValidClientId("0123456789abcdef0123456789abcdeg"))

	def test_FUN10_isoDate(self):
		self.assertEqual(core.player._isoToEpoch("1970-01-01T00:01:00.000Z"), 60)
		self.assertEqual(core.player._isoToEpoch("garbage"), 0)


if __name__ == "__main__":
	unittest.main()
