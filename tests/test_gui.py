# -*- coding: UTF-8 -*-
"""Interface tests (FUN-xx of docs/SDD-TESTES.md): the Spotify window, the
settings panel and the shortcuts, with real wxPython and the Spotify mock.

Run:  python tests/test_gui.py"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _guiapp import (  # noqa: E402
	MOCK, RECORD, VK_LEFT, VK_RIGHT, SpotifyNVDA, activate, childNodes, childTexts, click, closeWindow, config,
	findTop, gui, mainDialog, nativeKey, newPlugin, pump, settingsPanel, signInThroughWindow, spokenSince,
	topTexts, useBrowser, waitSpoken, wx,
)
import _helpers  # noqa: E402
import nvda_stubs  # noqa: E402
from _results import Recorder  # noqa: E402
import mock_spotify  # noqa: E402
from mock_spotify import TRACKS  # noqa: E402

R = Recorder("interface (test_gui)")


class FakeChoice:
	"""Replaces wx.SingleChoiceDialog (modal) during the tests."""
	answer = wx.ID_OK
	selection = 0
	shown = []

	def __init__(self, parent, message, caption, choices):
		FakeChoice.shown.append((message, caption, list(choices)))

	def ShowModal(self):
		return FakeChoice.answer

	def GetSelection(self):
		return FakeChoice.selection

	def Destroy(self):
		pass


def run():
	plugin = newPlugin()

	# -- window before signing in ------------------------------------------------------
	plugin.openWindow()
	dlg = mainDialog.SpotifyDialog._instance
	R.check("FUN-13 NVDA+Alt+P / Tools menu opens the Spotify window", dlg is not None and dlg.IsShown())
	R.check("FUN-13 status says not signed in", dlg.statusEdit.GetValue().startswith("Not signed in"), dlg.statusEdit.GetValue())
	R.check("FUN-13 sign in shown, sign out hidden", dlg.signInButton.IsShown() and not dlg.signOutButton.IsShown())
	R.check("FUN-13 search and actions disabled without account", not dlg.searchEdit.IsEnabled() and not dlg.resumeButton.IsEnabled())
	plugin.openWindow()
	R.check("FUN-13 opening again reuses the same window", mainDialog.SpotifyDialog._instance is dlg)

	# -- no Client ID ------------------------------------------------------------------
	config.conf["SpotifyNVDA"]["clientId"] = ""
	nBoxes = len(RECORD["messageBoxes"])
	nSettings = len(RECORD["settingsOpened"])
	dlg.onSignIn(None)
	R.check("FUN-01 without Client ID explains and opens the settings", len(RECORD["messageBoxes"]) == nBoxes + 1 and "Client ID" in RECORD["messageBoxes"][-1] and len(RECORD["settingsOpened"]) == nSettings + 1)
	config.conf["SpotifyNVDA"]["clientId"] = mock_spotify.CLIENT_ID

	# -- denied --------------------------------------------------------------------------
	useBrowser("deny")
	n = len(nvda_stubs.spoken())
	dlg.onSignIn(None)
	R.check("FUN-01 denied sign-in is announced", waitSpoken(n, lambda s: "did not authorize" in s), spokenSince(n))
	pump(lambda: dlg._signInCancel is None)
	R.check("FUN-01 still signed out after denying", not plugin.service.signedIn)

	# -- cancel ----------------------------------------------------------------------------
	useBrowser("nothing")
	n = len(nvda_stubs.spoken())
	dlg.onSignIn(None)
	R.check("FUN-01 sign-in button becomes Cancel sign-in while waiting", dlg.signInButton.GetLabel() == "Cancel sign-&in", dlg.signInButton.GetLabel())
	R.check("FUN-01 waiting state in the status", dlg.statusEdit.GetValue().startswith("Waiting for the sign-in"), dlg.statusEdit.GetValue())
	dlg.onSignIn(None)  # cancel
	R.check("FUN-01 cancelling is announced", waitSpoken(n, lambda s: s == "Sign-in cancelled."), spokenSince(n))
	pump(lambda: dlg._signInCancel is None)
	R.check("FUN-01 button back to Sign in after cancelling", dlg.signInButton.GetLabel() == "Sign &in with Spotify", dlg.signInButton.GetLabel())
	closeWindow()

	# -- sign in -----------------------------------------------------------------------------
	dlg = signInThroughWindow(plugin)
	R.check("FUN-01 signed in through the window", plugin.service.signedIn)
	R.check("FUN-01 sign-in announced with the user name", "Signed in to Spotify as Wellington" in nvda_stubs.spoken(), nvda_stubs.spoken()[-3:])
	R.check("FUN-01 status shows the user name", dlg.statusEdit.GetValue() == "Signed in as Wellington", dlg.statusEdit.GetValue())
	R.check("RF-09 sign out shown after signing in", dlg.signOutButton.IsShown() and not dlg.signInButton.IsShown())
	R.check("FUN-03 my playlists listed after signing in", dlg.listKind == "myPlaylists" and len(topTexts(dlg)) == 55, len(topTexts(dlg)))
	R.check("FUN-03 list label says what and how many", dlg.resultsLabel.GetLabel() == "&Results: my playlists (55)", dlg.resultsLabel.GetLabel())
	R.check("FUN-03 playlist line has name, owner and songs", topTexts(dlg)[0] == "Playlist 1 - Wellington, 1 songs", topTexts(dlg)[:1])
	R.check("FUN-06 Add to playlist disabled for playlists", not dlg.addButton.IsEnabled())

	# -- stays signed in (new plugin = NVDA restarted) -------------------------------------------
	closeWindow()
	store = plugin.service.store
	plugin2 = SpotifyNVDA.GlobalPlugin()
	plugin2.service = _helpers.makeService(_helpers.loadCore(), configPath=os.path.dirname(store.path))
	R.check("FUN-02 still signed in after restarting NVDA", plugin2.service.signedIn)
	plugin2.openWindow()
	d2 = mainDialog.SpotifyDialog._instance
	pump(lambda: d2.listKind == "myPlaylists")
	R.check("FUN-02 window opens signed in, with the playlists", d2.statusEdit.GetValue().startswith("Signed in as") and len(topTexts(d2)) == 55)
	closeWindow()
	plugin2.terminate()
	R.check("FUN-15 terminate releases the settings panel", settingsPanel.SpotifySettingsPanel.plugin is None)
	# In NVDA there is a single plugin; here the first one is still in use.
	settingsPanel.SpotifySettingsPanel.plugin = plugin
	plugin.openWindow()
	dlg = mainDialog.SpotifyDialog._instance
	pump(lambda: dlg.listKind == "myPlaylists")

	# -- search songs and play --------------------------------------------------------------------
	dlg.searchEdit.SetValue("")
	n = len(nvda_stubs.spoken())
	dlg.onSearch(None)
	R.check("FUN-07 empty search asks what to search", spokenSince(n) == ["Type what you want to search for."], spokenSince(n))
	dlg.searchEdit.SetValue("ipanema")
	dlg.kindChoice.SetSelection(mainDialog.KIND_TRACK)
	n = len(nvda_stubs.spoken())
	dlg.onSearch(None)
	pump(lambda: dlg.listKind == "tracks")
	R.check("FUN-07 song search fills the list", topTexts(dlg) == ["Garota de Ipanema, by Tom Jobim, album Getz/Gilberto"], topTexts(dlg))
	R.check("FUN-07 result count announced", waitSpoken(n, lambda s: s == "Results: songs found (1)"), spokenSince(n))
	R.check("FUN-06 Add to playlist enabled for a song", dlg.addButton.IsEnabled())
	n = len(nvda_stubs.spoken())
	dlg.searchEdit.SetValue("nothing-like-this")
	dlg.onSearch(None)
	R.check("FUN-07 nothing found announced", waitSpoken(n, lambda s: s == "Nothing found."), spokenSince(n))
	dlg.searchEdit.SetValue("ipanema")
	dlg.onSearch(None)
	pump(lambda: len(topTexts(dlg)) == 1)

	n = len(nvda_stubs.spoken())
	activate(dlg)
	R.check("FUN-04 Enter on a song plays it", waitSpoken(n, lambda s: s == "Playing Garota de Ipanema") and MOCK.player and MOCK.player["item"]["id"] == TRACKS[0]["id"], spokenSince(n))
	R.check("FUN-04 plays on the computer", MOCK.activeDevice() and MOCK.activeDevice()["id"] == "dev-computer")

	# -- play/pause button ----------------------------------------------------------------------
	n = len(nvda_stubs.spoken())
	click(dlg.playPauseButton)
	R.check("FUN-05 Play/pause button pauses", waitSpoken(n, lambda s: s == "Paused") and not MOCK.player["is_playing"], spokenSince(n))
	n = len(nvda_stubs.spoken())
	click(dlg.playPauseButton)
	R.check("FUN-05 Play/pause button plays again", waitSpoken(n, lambda s: s == "Playing") and MOCK.player["is_playing"], spokenSince(n))

	# -- add to playlist -------------------------------------------------------------------------
	original = mainDialog.wx.SingleChoiceDialog
	mainDialog.wx.SingleChoiceDialog = FakeChoice
	try:
		FakeChoice.shown.clear()
		FakeChoice.selection = 0
		n = len(nvda_stubs.spoken())
		click(dlg.addButton)
		ok = waitSpoken(n, lambda s: s == "Garota de Ipanema added to Playlist 1")
		R.check("FUN-06 Add to playlist adds the song", ok and TRACKS[0]["uri"] in MOCK.playlists[0]["tracks_added"], spokenSince(n))
		R.check("FUN-06 only the user's own playlists are offered", FakeChoice.shown and "Playlist 5" not in FakeChoice.shown[0][2] and "Playlist 4" in FakeChoice.shown[0][2])
		FakeChoice.answer = wx.ID_CANCEL
		before = list(MOCK.playlists[0]["tracks_added"])
		click(dlg.addButton)
		pump(timeout=0.5)
		R.check("FUN-06 cancelling the choice adds nothing", MOCK.playlists[0]["tracks_added"] == before)
		FakeChoice.answer = wx.ID_OK
	finally:
		mainDialog.wx.SingleChoiceDialog = original

	# -- new playlist ----------------------------------------------------------------------------
	npd = mainDialog.NewPlaylistDialog(dlg, "Garota de Ipanema, by Tom Jobim")
	nBoxes = len(RECORD["messageBoxes"])
	npd.onOk(wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_OK))
	R.check("FUN-06 empty playlist name is refused", len(RECORD["messageBoxes"]) == nBoxes + 1 and "name" in RECORD["messageBoxes"][-1])
	R.check("FUN-06 new playlist offers to add the selected song (checked)", npd.addSongCheck is not None and npd.addSongCheck.GetValue())
	npd.Destroy()

	def fakeShowModal(self):
		self.nameEdit.SetValue("Bossa NVDA")
		self.descriptionEdit.SetValue("criada pelo teste")
		self.publicCheck.SetValue(True)
		return wx.ID_OK

	originalShow = mainDialog.NewPlaylistDialog.ShowModal
	mainDialog.NewPlaylistDialog.ShowModal = fakeShowModal
	try:
		n = len(nvda_stubs.spoken())
		click(dlg.newPlaylistButton)
		ok = waitSpoken(n, lambda s: s == "Playlist Bossa NVDA created")
		created = [p for p in MOCK.playlists if p["name"] == "Bossa NVDA"]
		R.check("FUN-06 New playlist creates it", ok and created and created[0]["public"] is True and created[0]["description"] == "criada pelo teste", spokenSince(n))
		R.check("FUN-06 selected song added to the new playlist", created and created[0]["tracks_added"] == [TRACKS[0]["uri"]])
	finally:
		mainDialog.NewPlaylistDialog.ShowModal = originalShow

	# -- search playlists and play -------------------------------------------------------------------
	dlg.searchEdit.SetValue("Playlist 3")
	dlg.kindChoice.SetSelection(mainDialog.KIND_PLAYLIST)
	dlg.onSearch(None)
	pump(lambda: dlg.listKind == "playlists")
	R.check("FUN-08 playlist search fills the list", topTexts(dlg) and topTexts(dlg)[0].startswith("Playlist 3"), topTexts(dlg)[:3])
	n = len(nvda_stubs.spoken())
	click(dlg.playButton)
	R.check("FUN-04 Play button plays the playlist", waitSpoken(n, lambda s: s == "Playing Playlist 3") and MOCK.player["context"]["uri"] == "spotify:playlist:p0000003", spokenSince(n))
	n = len(nvda_stubs.spoken())
	click(dlg.myPlaylistsButton)
	R.check("FUN-03 My playlists button lists them again", waitSpoken(n, lambda s: s.startswith("Results: my playlists")) and dlg.listKind == "myPlaylists", spokenSince(n))

	# -- tree: songs inside the playlists (1.2.0) ----------------------------------------------------
	tree = dlg.resultsTree
	pump(lambda: dlg.listKind == "myPlaylists" and len(topTexts(dlg)) >= 55)
	p3 = findTop(dlg, "Playlist 3 ")
	R.check("FUN-20 playlists are expandable branches", p3 is not None and tree.ItemHasChildren(p3) and not tree.IsExpanded(p3))
	tree.SelectItem(p3)
	n = len(nvda_stubs.spoken())
	nativeKey(dlg, VK_RIGHT)
	ok = pump(lambda: tree.GetItemData(p3).get("loaded"))
	expectedP3 = ["%s, by %s, album %s" % (t["name"], t["artists"][0]["name"], t["album"]["name"]) for t in (e["item"] for e in MOCK.playlists[[p["id"] for p in MOCK.playlists].index("p0000003")]["entries"])]
	R.check("FUN-20 Right arrow opens the playlist and shows its songs in order", ok and tree.IsExpanded(p3) and childTexts(dlg, p3) == expectedP3, childTexts(dlg, p3))
	R.check("FUN-20 number of songs announced", waitSpoken(n, lambda s: s == "3 songs"), spokenSince(n))
	nativeKey(dlg, VK_LEFT)
	R.check("FUN-20 Left arrow closes the playlist", not tree.IsExpanded(p3))
	tree.Expand(p3)
	first = childNodes(dlg, p3)[0]
	tree.SelectItem(first)
	R.check("FUN-20 a song in a playlist can be played, added, sorted; not deleted", dlg.playButton.IsEnabled() and dlg.addButton.IsEnabled() and dlg.sortButton.IsEnabled() and not dlg.deleteButton.IsEnabled())
	n = len(nvda_stubs.spoken())
	activate(dlg)
	song = tree.GetItemData(first)["item"]
	R.check("FUN-20 Enter on a song plays the playlist from that song", waitSpoken(n, lambda s: s == "Playing " + song["name"]) and MOCK.player["context"]["uri"] == "spotify:playlist:p0000003" and MOCK.player["item"]["uri"] == song["uri"], (spokenSince(n), MOCK.player))
	requestsBefore = len([r for r in MOCK.requests if r["path"] == "/v1/playlists/p0000003/items"])
	tree.Collapse(p3)
	tree.Expand(p3)
	pump(timeout=0.3)
	R.check("FUN-20 songs are read once (cache)", len([r for r in MOCK.requests if r["path"] == "/v1/playlists/p0000003/items"]) == requestsBefore)

	p2 = findTop(dlg, "Playlist 2 ")
	tree.SelectItem(p2)
	tree.Expand(p2)
	pump(lambda: tree.GetItemData(p2).get("loaded"))
	local = childNodes(dlg, p2)[-1]
	R.check("FUN-20 local file shown as not available", tree.GetItemText(local) == "Gravação caseira, by Eu (not available to play)", tree.GetItemText(local))
	tree.SelectItem(local)
	R.check("FUN-20 Play and Add disabled on a song that cannot be played", not dlg.playButton.IsEnabled() and not dlg.addButton.IsEnabled())
	n = len(nvda_stubs.spoken())
	activate(dlg)
	R.check("FUN-20 Enter on it explains", waitSpoken(n, lambda s: s == "This song is not available to play."), spokenSince(n))

	p5 = findTop(dlg, "Playlist 5 ")
	R.check("FUN-20 playlist of someone else shows no song count", tree.GetItemText(p5) == "Playlist 5 - Someone", tree.GetItemText(p5))
	tree.SelectItem(p5)
	n = len(nvda_stubs.spoken())
	tree.Expand(p5)
	pump(lambda: tree.GetItemData(p5).get("loaded"))
	R.check("FUN-20 songs of someone else's playlist: explained, not an error", childTexts(dlg, p5) == ["Spotify only shows the songs of playlists that are yours or that you collaborate on."] and waitSpoken(n, lambda s: s.startswith("Spotify only shows")), (childTexts(dlg, p5), spokenSince(n)))

	# add a song to an open playlist: it is read again
	tree.SelectItem(first)
	original = mainDialog.wx.SingleChoiceDialog
	mainDialog.wx.SingleChoiceDialog = FakeChoice
	try:
		FakeChoice.answer = wx.ID_OK
		FakeChoice.selection = [p["name"] for p in dlg._editablePlaylists()].index("Playlist 3")
		click(dlg.addButton)
		ok = pump(lambda: len(childTexts(dlg, p3)) == 4)
		R.check("FUN-20 adding a song refreshes the open playlist", ok, childTexts(dlg, p3))
	finally:
		mainDialog.wx.SingleChoiceDialog = original

	# -- sort ------------------------------------------------------------------------------------------
	def norm(text):
		import unicodedata

		return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()

	class SortAnswer:
		values = {"key": "name", "descending": False, "save": False}
		canSave = []

	def fakeSortModal(self):
		SortAnswer.canSave.append(self.saveCheck is not None)
		v = SortAnswer.values
		self.keyChoice.SetSelection(mainDialog.SORT_KEYS.index(v["key"]))
		self.directionChoice.SetSelection(1 if v["descending"] else 0)
		if self.saveCheck is not None:
			self.saveCheck.SetValue(v["save"])
		return wx.ID_OK

	originalSort = mainDialog.SortDialog.ShowModal
	mainDialog.SortDialog.ShowModal = fakeSortModal
	try:
		tree.SelectItem(p3)
		n = len(nvda_stubs.spoken())
		click(dlg.sortButton)
		names = [tree.GetItemData(c)["item"]["name"] for c in childNodes(dlg, p3)]
		R.check("FUN-22 sort by title (accents ignored: Águas before Chega)", names == sorted(names, key=norm) and waitSpoken(n, lambda s: s == "Playlist 3 sorted by Title"), (names, spokenSince(n)))
		R.check("FUN-22 the playlist stays selected after sorting", tree.GetSelection() == p3)
		SortAnswer.values = {"key": "artists", "descending": True, "save": False}
		click(dlg.sortButton)
		artists = [tree.GetItemData(c)["item"]["artists"] for c in childNodes(dlg, p3)]
		R.check("FUN-22 sort by artist, descending", artists == sorted(artists, key=norm, reverse=True), artists)
		R.check("FUN-22 sort only changes this window (Spotify untouched)", not MOCK.reorders)
		R.check("FUN-22 the chosen order is remembered for the playlist", plugin.service.library.sortPref("p0000003") == ("artists", True))
		R.check("FUN-22 Save on Spotify offered for the user's own playlist", SortAnswer.canSave[-1] is True)
		tree.SelectItem(p5)
		click(dlg.sortButton)
		R.check("FUN-22 Save on Spotify not offered for someone else's playlist", SortAnswer.canSave[-1] is False)

		# save the order on Spotify
		tree.SelectItem(p3)
		SortAnswer.values = {"key": "name", "descending": False, "save": True}
		nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.NO
		click(dlg.sortButton)
		pump(timeout=0.3)
		R.check("FUN-22 answering No does not change Spotify", not MOCK.reorders)
		nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
		n = len(nvda_stubs.spoken())
		click(dlg.sortButton)
		ok = waitSpoken(n, lambda s: s == "New order of Playlist 3 saved on Spotify")
		entries = [p for p in MOCK.playlists if p["id"] == "p0000003"][0]["entries"]
		saved = [e["item"]["name"] for e in entries]
		R.check("FUN-22 order saved on Spotify, song by song", ok and saved == sorted(saved, key=norm) and MOCK.reorders, (saved, spokenSince(n)))
		R.check("FUN-22 each move uses the snapshot of the previous one", all(r[3] == "snap-%d" % i for i, r in enumerate(MOCK.reorders[1:], 1)) and MOCK.reorders[0][3] is None, MOCK.reorders)
		pump(lambda: tree.GetItemData(p3).get("loaded"))
		R.check("FUN-22 the playlist is read again after saving", [tree.GetItemData(c)["item"]["name"] for c in childNodes(dlg, p3)] == saved)
		R.check("FUN-22 after saving, the view follows Spotify's order", plugin.service.library.sortPref("p0000003") == ("position", False))
		nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.OK
	finally:
		mainDialog.SortDialog.ShowModal = originalSort
	sd = mainDialog.SortDialog(dlg, "Playlist 3", "addedAt", True, canSave=True)
	R.check("FUN-22 sort dialog starts with the current choice", sd.values() == {"key": "addedAt", "descending": True, "save": False}, sd.values())
	sd.Destroy()

	# -- delete ------------------------------------------------------------------------------------------
	p4 = findTop(dlg, "Playlist 4 ")
	tree.SelectItem(p4)
	R.check("FUN-23 Delete playlist enabled on a playlist", dlg.deleteButton.IsEnabled())
	countBefore = len(topTexts(dlg))
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.NO
	nBoxes = len(RECORD["messageBoxes"])
	click(dlg.deleteButton)
	R.check("FUN-23 deleting asks first; No keeps it", len(RECORD["messageBoxes"]) == nBoxes + 1 and "Recover playlists" in RECORD["messageBoxes"][-1] and not MOCK.deleted)
	nativeKey(dlg, 0x2E)  # Delete
	pump(timeout=0.3)
	R.check("FUN-23 Delete key on a playlist also asks", len(RECORD["messageBoxes"]) == nBoxes + 2)
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	n = len(nvda_stubs.spoken())
	click(dlg.deleteButton)
	ok = waitSpoken(n, lambda s: s == "Playlist Playlist 4 deleted")
	R.check("FUN-23 playlist deleted on Spotify (removed from the library)", ok and MOCK.deleted == ["p0000004"] and not any(p["id"] == "p0000004" for p in MOCK.playlists), spokenSince(n))
	req = [r for r in MOCK.requests if r["method"] == "DELETE"][-1]
	R.check("FUN-23 uses DELETE /me/library with the playlist URI", req["path"] == "/v1/me/library" and req["query"]["uris"] == "spotify:playlist:p0000004", req)
	R.check("FUN-23 removed from the tree and the count updated", findTop(dlg, "Playlist 4 ") is None and len(topTexts(dlg)) == countBefore - 1 and dlg.resultsLabel.GetLabel().endswith("(%d)" % (countBefore - 1)))
	R.check("FUN-23 selection moves to the next playlist", tree.GetSelection().IsOk() and tree.GetItemText(tree.GetSelection()).startswith("Playlist 5"), tree.GetItemText(tree.GetSelection()))
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.OK

	# -- search inside my playlists ---------------------------------------------------------------------
	dlg.kindChoice.SetSelection(mainDialog.KIND_IN_PLAYLISTS)
	dlg.searchEdit.SetValue("AGUAS de marco")
	n = len(nvda_stubs.spoken())
	plugin.service.library.forget()
	requestsBefore = len(MOCK.requests)
	dlg.onSearch(None)
	pump(lambda: dlg.listKind == "inPlaylists", 15)
	mine = [p for p in MOCK.playlists if p["owner"]["id"] == mock_spotify.USER_ID]
	expected = [p["name"] for p in mine if any(e["item"].get("name") == "Águas de Março" for e in p["entries"])]
	shown = [t.split(" - ")[0] for t in topTexts(dlg)]
	R.check("FUN-21 search inside the playlists ignores accents and case", shown == expected and expected, (shown, expected))
	R.check("FUN-21 each playlist found is open with only the matching songs", all(tree.IsExpanded(nd) and childTexts(dlg, nd) and all(c.startswith("Águas de Março") for c in childTexts(dlg, nd)) for nd in [findTop(dlg, x + " ") for x in shown]))
	total = sum(len(childTexts(dlg, findTop(dlg, x + " "))) for x in shown)
	R.check("FUN-21 result announced with songs and playlists", waitSpoken(n, lambda s: s == "%d songs found in %d playlists" % (total, len(shown))), spokenSince(n))
	R.check("FUN-21 list name says how many songs", dlg.resultsLabel.GetLabel() == "&Results: songs in my playlists (%d)" % total, dlg.resultsLabel.GetLabel())
	others = {"/v1/playlists/%s/items" % p["id"] for p in MOCK.playlists if p["owner"]["id"] != mock_spotify.USER_ID}
	asked = [r["path"] for r in MOCK.requests[requestsBefore:] if r["method"] == "GET" and r["path"].startswith("/v1/playlists/")]
	R.check("FUN-21 only the user's playlists are searched (others never requested)", asked and not (set(asked) & others), sorted(set(asked) & others))
	first = childNodes(dlg, findTop(dlg, shown[0] + " "))[0]
	tree.SelectItem(first)
	n = len(nvda_stubs.spoken())
	activate(dlg)
	R.check("FUN-21 a song found plays inside its playlist", waitSpoken(n, lambda s: s == "Playing Águas de Março") and MOCK.player["context"]["uri"].endswith(":" + [p["id"] for p in mine if p["name"] == shown[0]][0]), spokenSince(n))
	dlg.searchEdit.SetValue("xyz-nada")
	n = len(nvda_stubs.spoken())
	dlg.onSearch(None)
	R.check("FUN-21 nothing found inside the playlists", waitSpoken(n, lambda s: s == "Nothing found."), spokenSince(n))
	dlg.kindChoice.SetSelection(mainDialog.KIND_TRACK)
	dlg.searchEdit.SetValue("ipanema")
	dlg.onSearch(None)
	pump(lambda: dlg.listKind == "tracks")
	click(dlg.myPlaylistsButton)
	pump(lambda: dlg.listKind == "myPlaylists")

	# -- shortcuts ---------------------------------------------------------------------------------
	n = len(nvda_stubs.spoken())
	plugin.script_nextTrack(None)
	R.check("FUN-05 NVDA+Alt+Right: next song announced", waitSpoken(n, lambda s: s == "Garota de Ipanema, by Tom Jobim" or ", by " in s), spokenSince(n))
	n = len(nvda_stubs.spoken())
	plugin.script_previousTrack(None)
	R.check("FUN-05 NVDA+Alt+Left: previous song announced", waitSpoken(n, lambda s: ", by " in s), spokenSince(n))
	n = len(nvda_stubs.spoken())
	plugin.script_volumeUp(None)
	R.check("FUN-05 NVDA+Alt+Up: volume up 10", waitSpoken(n, lambda s: s == "Volume 60%"), spokenSince(n))
	config.conf["SpotifyNVDA"]["volumeStep"] = 25
	n = len(nvda_stubs.spoken())
	plugin.script_volumeDown(None)
	R.check("FUN-05 NVDA+Alt+Down: volume down by the configured step", waitSpoken(n, lambda s: s == "Volume 35%"), spokenSince(n))
	config.conf["SpotifyNVDA"]["volumeStep"] = 10
	n = len(nvda_stubs.spoken())
	plugin.script_playPause(None)
	R.check("FUN-05 NVDA+Alt+Space pauses", waitSpoken(n, lambda s: s == "Paused"), spokenSince(n))
	n = len(nvda_stubs.spoken())
	plugin.script_nowPlaying(None)
	R.check("FUN-11 NVDA+Alt+A says what is paused", waitSpoken(n, lambda s: s.startswith("Paused: ")), spokenSince(n))
	n = len(nvda_stubs.spoken())
	plugin.script_resumeLast(None)
	R.check("FUN-10 NVDA+Alt+U continues the last song", waitSpoken(n, lambda s: s.startswith("Continuing: ")) and MOCK.player["is_playing"], spokenSince(n))
	n = len(nvda_stubs.spoken())
	click(dlg.resumeButton)
	R.check("FUN-10 Continue last song button", waitSpoken(n, lambda s: s.startswith("Continuing: ")), spokenSince(n))
	MOCK.product = "free"
	n = len(nvda_stubs.spoken())
	plugin.script_playPause(None)
	R.check("FUN-12 without Premium the shortcut explains", waitSpoken(n, lambda s: "requires Spotify Premium" in s), spokenSince(n))
	MOCK.product = "premium"
	MOCK.player = None
	MOCK.activate("none")
	n = len(nvda_stubs.spoken())
	plugin.script_nowPlaying(None)
	R.check("FUN-11 nothing playing announced", waitSpoken(n, lambda s: s == "Nothing is playing on Spotify."), spokenSince(n))

	# -- settings panel --------------------------------------------------------------------------------
	frame = wx.Frame(None)
	panel = settingsPanel.SpotifySettingsPanel(frame)
	R.check("FUN-14 settings show the saved Client ID", panel.clientIdEdit.GetValue() == mock_spotify.CLIENT_ID)
	panel.portSpin.SetValue(9123)
	panel.onPort(wx.CommandEvent())
	R.check("FUN-14 redirect URI follows the port", panel.redirectEdit.GetValue() == "http://127.0.0.1:9123/callback", panel.redirectEdit.GetValue())
	panel.clientIdEdit.SetValue("not-a-client-id")
	nBoxes = len(RECORD["messageBoxes"])
	R.check("FUN-14 wrong Client ID format refused", panel.isValid() is False and len(RECORD["messageBoxes"]) == nBoxes + 1)
	panel.clientIdEdit.SetValue("  " + mock_spotify.CLIENT_ID.upper() + " ")
	panel.volumeSpin.SetValue(5)
	panel.launchCheck.SetValue(False)
	R.check("FUN-19 Keep the Spotify app hidden is on by default", panel.hideCheck.GetValue() is True)
	panel.hideCheck.SetValue(False)
	R.check("FUN-14 valid Client ID accepted", panel.isValid() is True)
	panel.onSave()
	conf = config.conf["SpotifyNVDA"]
	R.check("FUN-14 settings saved", conf["clientId"] == mock_spotify.CLIENT_ID.upper() and conf["port"] == 9123 and conf["volumeStep"] == 5 and conf["launchApp"] is False and conf["hideApp"] is False, dict(conf))
	R.check("FUN-14 Sign out enabled in settings while signed in", panel.signOutButton.IsEnabled())
	MOCK.devicesHidden = True
	plugin.launches.clear()
	plugin.service.player.launchApp = plugin._launchApp
	n = len(nvda_stubs.spoken())
	click(dlg.playButton)
	R.check("FUN-14 app not opened when the option is off", waitSpoken(n, lambda s: "No Spotify device" in s), spokenSince(n))
	MOCK.devicesHidden = False
	conf["launchApp"] = True
	calls = []
	original = SpotifyNVDA.launchSpotifyApp
	SpotifyNVDA.launchSpotifyApp = lambda hide=True: calls.append(hide)
	try:
		plugin._launchApp()
		conf["hideApp"] = True
		plugin._launchApp()
	finally:
		SpotifyNVDA.launchSpotifyApp = original
	R.check("FUN-19 the hide option reaches the background launcher", calls == [False, True], calls)
	conf["clientId"] = mock_spotify.CLIENT_ID

	# -- sign out ---------------------------------------------------------------------------------------
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.NO
	click(dlg.signOutButton)
	R.check("RF-09 answering No keeps the session", plugin.service.signedIn)
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	n = len(nvda_stubs.spoken())
	path = plugin.service.store.path
	click(dlg.signOutButton)
	R.check("RF-09 Sign out button signs out", not plugin.service.signedIn and not os.path.exists(path))
	R.check("RF-09 sign out announced", waitSpoken(n, lambda s: s.startswith("Signed out of Spotify")), spokenSince(n))
	R.check("RF-09 window back to the signed-out state", dlg.signInButton.IsShown() and not dlg.signOutButton.IsShown() and topTexts(dlg) == [])
	n = len(nvda_stubs.spoken())
	plugin.script_playPause(None)
	R.check("FUN-12 shortcut without account says how to sign in", waitSpoken(n, lambda s: s.startswith("You are not signed in")), spokenSince(n))
	n = len(nvda_stubs.spoken())
	plugin.script_signOut(None)
	R.check("RF-09 Sign out command without account explains", waitSpoken(n, lambda s: s.startswith("You are not signed in")), spokenSince(n))

	# sign out from the settings panel and from the command
	dlg = None
	closeWindow()
	signInThroughWindow(plugin)
	panel2 = settingsPanel.SpotifySettingsPanel(frame)
	click(panel2.signOutButton)
	R.check("RF-09 Sign out from the settings", not plugin.service.signedIn and not panel2.signOutButton.IsEnabled())
	d = mainDialog.SpotifyDialog._instance
	R.check("RF-09 open window follows a sign out made elsewhere", d is not None and d.signInButton.IsShown())
	closeWindow()
	signInThroughWindow(plugin)
	plugin.script_signOut(None)
	pump(lambda: not plugin.service.signedIn)
	R.check("RF-09 Sign out command (after confirming)", not plugin.service.signedIn)
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.OK
	closeWindow()
	frame.Destroy()

	# -- terminate -----------------------------------------------------------------------------------
	plugin.openWindow()
	plugin.terminate()
	R.check("FUN-15 terminate closes the window and removes the settings panel", mainDialog.SpotifyDialog._instance is None and settingsPanel.SpotifySettingsPanel not in gui.settingsDialogs.NVDASettingsDialog.categoryClasses)
	R.check("FUN-15 no unexpected errors in the log", not RECORD["logErrors"], RECORD["logErrors"])


if __name__ == "__main__":
	try:
		run()
	except Exception:
		import traceback

		traceback.print_exc()
		R.check("suite finished without crashing", False, traceback.format_exc()[-500:])
	sys.exit(R.finish())
