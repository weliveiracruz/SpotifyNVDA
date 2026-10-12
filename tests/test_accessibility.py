# -*- coding: UTF-8 -*-
"""Accessibility tests (ACE-xx of docs/SDD-TESTES.md).

Besides the structure of the windows (labels, Alt shortcuts, tab order, focus),
on Windows it reads the accessible name of every control through MSAA
(oleacc), the same interface NVDA uses for these Win32 controls.

Run:  python tests/test_accessibility.py   (SPOTIFYNVDA_LANG=pt_BR for Portuguese)"""

import importlib
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _guiapp import (  # noqa: E402
	MOCK, SpotifyNVDA, activate, childNodes, closeWindow, config, findTop, mainDialog, newPlugin, pump,
	settingsPanel, signInThroughWindow, spokenSince, useBrowser, waitSpoken, wx,
)
import _strings  # noqa: E402
import nvda_stubs  # noqa: E402
from _results import Recorder  # noqa: E402

LANG = os.environ.get("SPOTIFYNVDA_LANG", "en")
R = Recorder("accessibility (test_accessibility%s)" % ("" if LANG == "en" else ", " + LANG))
FOCUS = []
_originalSetFocus = wx.Window.SetFocus


def _recordFocus(self):
	FOCUS.append(self)
	return _originalSetFocus(self)


wx.Window.SetFocus = _recordFocus
# The dialog only moves the focus when it is the active window (it never steals
# the focus from the browser during the sign-in); in the tests it always is.
mainDialog.SpotifyDialog.IsActive = lambda self: True


def lastFocus():
	return FOCUS[-1] if FOCUS else None


def focusables(win):
	"""Controls reachable with Tab, in tab order (creation order of the children)."""
	out = []
	for c in win.GetChildren():
		if not c.IsShown() or not c.IsEnabled():
			continue
		if isinstance(c, (wx.StaticText, wx.StaticLine)):
			continue
		if isinstance(c, wx.Panel) and not c.AcceptsFocusFromKeyboard():
			out.extend(focusables(c))
		elif c.AcceptsFocusFromKeyboard():
			out.append(c)
	return out


def structuralName(ctrl):
	"""Name Windows gives: own label for buttons and check boxes, otherwise the
	static text that comes right before the control."""
	if isinstance(ctrl, (wx.Button, wx.CheckBox)):
		return ctrl.GetLabel()
	siblings = list(ctrl.GetParent().GetChildren())
	i = siblings.index(ctrl)
	j = i - 1
	while j >= 0 and not siblings[j].IsShown():
		j -= 1
	if j >= 0 and isinstance(siblings[j], wx.StaticText):
		return siblings[j].GetLabel()
	return ""


def mnemonicLabels(win):
	labels = []
	for c in win.GetChildren():
		if isinstance(c, (wx.Button, wx.CheckBox, wx.StaticText)) and c.IsShown():
			labels.append(c.GetLabel())
		if isinstance(c, wx.Panel):
			labels.extend(mnemonicLabels(c))
	return labels


def mnemonic(label):
	m = re.search(r"&([^&])", label.replace("&&", ""))
	return m.group(1).lower() if m else None


# -- MSAA (what NVDA reads) ------------------------------------------------------------------

_msaa = None


def msaaName(ctrl):
	"""Accessible name of a control read through oleacc, or None when MSAA is not available."""
	global _msaa
	if sys.platform != "win32":
		return None
	if _msaa is None:
		try:
			import ctypes

			import comtypes.client

			comtypes.client.GetModule("oleacc.dll")
			from comtypes.gen.Accessibility import IAccessible

			_msaa = (ctypes, IAccessible)
		except Exception:
			_msaa = False
	if not _msaa:
		return None
	ctypes, IAccessible = _msaa
	# Read the window that really gets the focus with Tab (a spin control, for
	# example, gives the focus to its edit box, not to its arrows).
	_originalSetFocus(ctrl)
	wx.Yield()
	user32 = ctypes.windll.user32
	user32.GetFocus.restype = ctypes.c_void_p
	hwnd = user32.GetFocus() or ctrl.GetHandle()
	acc = ctypes.POINTER(IAccessible)()
	OBJID_CLIENT = ctypes.c_long(-4).value & 0xFFFFFFFF
	ctypes.oledll.oleacc.AccessibleObjectFromWindow(ctypes.c_void_p(hwnd), OBJID_CLIENT, ctypes.byref(IAccessible._iid_), ctypes.byref(acc))
	try:
		return acc.accName(0) or ""
	except Exception:
		return ""


def msaaTreeSelection(tree):
	"""(name, state, value) of the selected tree item read through MSAA: what
	NVDA announces (name, expanded or collapsed, level)."""
	if _msaa is None:
		msaaName(tree)
	ctypes, IAccessible = _msaa
	acc = ctypes.POINTER(IAccessible)()
	OBJID_CLIENT = ctypes.c_long(-4).value & 0xFFFFFFFF
	ctypes.oledll.oleacc.AccessibleObjectFromWindow(ctypes.c_void_p(tree.GetHandle()), OBJID_CLIENT, ctypes.byref(IAccessible._iid_), ctypes.byref(acc))
	child = acc.accSelection
	childId = child if isinstance(child, int) else 0
	return acc.accName(childId) or "", int(acc.accState(childId)), str(acc.accValue(childId))


def plain(label):
	return label.replace("&&", "\0").replace("&", "").replace("\0", "&").rstrip(":").strip()


def checkWindow(name, win, expectMnemonicOnButtons=True):
	ctrls = focusables(win)
	unnamed = [type(c).__name__ for c in ctrls if not structuralName(c).strip()]
	R.check("ACE-01 every focusable control has a name: %s" % name, not unnamed, unnamed)
	labels = [lbl for lbl in mnemonicLabels(win) if lbl.strip()]
	keys = [mnemonic(lbl) for lbl in labels]
	present = [k for k in keys if k]
	dups = sorted({k for k in present if present.count(k) > 1})
	R.check("ACE-02 Alt shortcuts are unique: %s" % name, not dups, (dups, labels))
	if expectMnemonicOnButtons:
		missing = [c.GetLabel() for c in ctrls if isinstance(c, (wx.Button, wx.CheckBox)) and c.GetId() not in (wx.ID_OK, wx.ID_CANCEL) and not mnemonic(c.GetLabel())]
		R.check("ACE-02 every button has an Alt shortcut: %s" % name, not missing, missing)
		labelsWithout = [c.GetLabel() for c in win.GetChildren() if isinstance(c, wx.StaticText) and c.IsShown() and c.GetLabel().strip() and not mnemonic(c.GetLabel())]
		R.check("ACE-02 every field label has an Alt shortcut: %s" % name, not labelsWithout, labelsWithout)
	if isinstance(win, wx.TopLevelWindow):
		R.check("ACE-08 window has its own title: %s" % name, bool(win.GetTitle().strip()), win.GetTitle())
	if sys.platform == "win32" and msaaName(ctrls[0]) is not None:
		wrong = []
		for c in ctrls:
			got = msaaName(c)
			expected = plain(structuralName(c))
			if not got or plain(got) != expected:
				wrong.append((type(c).__name__, expected, got))
		R.check("ACE-01 names read through MSAA (what NVDA says): %s" % name, not wrong, wrong)
	return ctrls


def defaultNvdaGestures():
	"""Keyboard gestures of the installed NVDA (scanned from library.zip) or, if
	NVDA is not installed, the NVDA+Alt gestures of NVDA 2026.1."""
	known = {"kb:nvda+alt+c", "kb:nvda+alt+m", "kb:nvda+alt+r", "kb:nvda+alt+s", "kb:nvda+alt+t", "kb:nvda+alt+home", "kb:nvda+alt+end", "kb:nvda+alt+tab"}
	found = set()
	for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
		lib = os.path.join(base, "NVDA", "library.zip")
		if base and os.path.isfile(lib):
			with zipfile.ZipFile(lib) as z:
				for n in z.namelist():
					if n.endswith(".pyc"):
						text = z.read(n).decode("latin-1")
						found.update(m.lower() for m in re.findall(r"kb(?:\([a-z]+\))?:[A-Za-z0-9+]+", text))
	return (found or known), bool(found)


def otherAddonGestures():
	"""Gestures declared by the other add-ons installed in this NVDA (if any)."""
	folder = os.path.join(os.environ.get("APPDATA", ""), "nvda", "addons")
	out = {}
	if not os.path.isdir(folder):
		return out
	for addon in os.listdir(folder):
		if addon.lower().startswith("spotifynvda"):
			continue
		for root, _dirs, files in os.walk(os.path.join(folder, addon)):
			for f in files:
				if f.endswith(".py"):
					try:
						with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
							for g in re.findall(r"[\"'](kb(?:\([a-z]+\))?:[A-Za-z0-9+]+)[\"']", fh.read()):
								out.setdefault(_normalGesture(g), addon)
					except OSError:
						pass
	return out


def _normalGesture(g):
	head, _sep, keys = g.lower().partition(":")
	return head + ":" + "+".join(sorted(keys.split("+")))


def run():
	plugin = newPlugin()
	plugin.openWindow()
	dlg = mainDialog.SpotifyDialog._instance

	# -- signed out -------------------------------------------------------------------------
	ctrls = checkWindow("Spotify window, signed out", dlg)
	R.check("ACE-15 signed out: only status, Sign in and Close in the tab order", ctrls == [dlg.statusEdit, dlg.signInButton, dlg.closeButton], [plain(structuralName(c)) for c in ctrls])
	R.check("ACE-06 focus starts on Sign in when signed out", lastFocus() is dlg.signInButton, lastFocus())
	R.check("ACE-04 hidden Sign out is out of the tab order", dlg.signOutButton not in ctrls)
	R.check("ACE-05 Esc closes the window", dlg.GetEscapeId() == wx.ID_CLOSE and dlg.closeButton.GetId() == wx.ID_CLOSE)
	R.check("ACE-13 status is a read-only text reachable with Tab", dlg.statusEdit.IsEditable() is False and dlg.statusEdit in ctrls)

	# -- signing in -------------------------------------------------------------------------
	useBrowser("nothing")
	n = len(nvda_stubs.spoken())
	dlg.onSignIn(None)
	R.check("ACE-06 waiting for the browser is announced", waitSpoken(n, lambda s: s == importlib.import_module("SpotifyNVDA.messages").waitingBrowser()), spokenSince(n))
	ctrls = focusables(dlg)
	R.check("ACE-01 cancel button has a name while waiting", mnemonic(dlg.signInButton.GetLabel()) and dlg.signInButton in ctrls, dlg.signInButton.GetLabel())
	dlg.onSignIn(None)
	pump(lambda: dlg._signInCancel is None)
	R.check("ACE-06 focus back on Sign in after cancelling", lastFocus() is dlg.signInButton)
	closeWindow()

	dlg = signInThroughWindow(plugin)
	pump(lambda: lastFocus() is dlg.resultsTree, 3)
	R.check("ACE-06 after signing in the focus goes to the playlists", lastFocus() is dlg.resultsTree, lastFocus())
	ctrls = checkWindow("Spotify window, signed in", dlg)
	expected = [dlg.statusEdit, dlg.signOutButton, dlg.searchEdit, dlg.kindChoice, dlg.searchButton, dlg.resultsTree, dlg.playButton, dlg.myPlaylistsButton, dlg.newPlaylistButton, dlg.sortButton, dlg.deleteButton, dlg.resumeButton, dlg.playPauseButton, dlg.closeButton]
	R.check("ACE-03 tab order: status, sign out, search, type, search, results, actions, close", ctrls == expected, [plain(structuralName(c)) for c in ctrls])
	R.check("ACE-04 Add to playlist out of the tab order for playlists (disabled)", dlg.addButton not in ctrls)
	R.check("ACE-14 list name says what it shows and how many", plain(structuralName(dlg.resultsTree)).endswith("(55)"), structuralName(dlg.resultsTree))
	if msaaName(dlg.resultsTree) is not None:
		R.check("ACE-14 list name read through MSAA updates with the content", plain(msaaName(dlg.resultsTree)).endswith("(55)"), msaaName(dlg.resultsTree))
		tree = dlg.resultsTree
		p3 = findTop(dlg, "Playlist 3 ")
		tree.SelectItem(p3)
		name, state, value = msaaTreeSelection(tree)
		R.check("ACE-18 playlist read by MSAA with name and 'collapsed'", name == tree.GetItemText(p3) and state & 0x400 and not state & 0x200, (name, hex(state)))
		R.check("ACE-18 playlist is at level 0 for MSAA", value == "0", value)
		tree.Expand(p3)
		pump(lambda: tree.GetItemData(p3).get("loaded"))
		name, state, value = msaaTreeSelection(tree)
		R.check("ACE-18 open playlist read by MSAA as 'expanded'", state & 0x200 and not state & 0x400, hex(state))
		song = childNodes(dlg, p3)[0]
		tree.SelectItem(song)
		name, state, value = msaaTreeSelection(tree)
		R.check("ACE-18 song inside the playlist read by MSAA with its name at level 1", name == tree.GetItemText(song) and value == "1", (name, value))
		tree.Collapse(p3)
		tree.SelectItem(p3)

	# keyboard: Enter in the search field searches, Enter in the list plays
	dlg.searchEdit.SetValue("ipanema")
	n = len(nvda_stubs.spoken())
	evt = wx.CommandEvent(wx.wxEVT_TEXT_ENTER, dlg.searchEdit.GetId())
	evt.SetEventObject(dlg.searchEdit)
	dlg.searchEdit.GetEventHandler().ProcessEvent(evt)
	R.check("ACE-05 Enter in the search field searches", pump(lambda: dlg.listKind == "tracks"))
	pump(lambda: lastFocus() is dlg.resultsTree, 2)
	R.check("ACE-06 focus goes to the results after searching", lastFocus() is dlg.resultsTree, lastFocus())
	R.check("ACE-07 result count announced", waitSpoken(n, lambda s: s.endswith("(1)")), spokenSince(n))
	ctrls = focusables(dlg)
	R.check("ACE-04 Add to playlist in the tab order for songs", dlg.addButton in ctrls and ctrls.index(dlg.addButton) == ctrls.index(dlg.playButton) + 1)
	n = len(nvda_stubs.spoken())
	activate(dlg)
	R.check("ACE-05 Enter in the list plays and it is announced", waitSpoken(n, lambda s: "Ipanema" in s), spokenSince(n))
	skipped = []

	class DownKey:
		def GetKeyCode(self):
			return wx.WXK_DOWN

		def Skip(self, skip=True):
			skipped.append(skip)

	dlg.onTreeKey(DownKey())
	R.check("ACE-05 arrows still move in the list", skipped == [True])

	# errors are spoken and the focus stays
	MOCK.fail("GET", "/v1/search", 503, {"error": {"status": 503}})
	n = len(nvda_stubs.spoken())
	FOCUS.clear()
	dlg.onSearch(None)
	R.check("ACE-07 errors are announced", waitSpoken(n, lambda s: "Spotify" in s and "problem" in s.lower() or "Spotify" in s and "problema" in s.lower()), spokenSince(n))

	# new playlist dialog
	npd = mainDialog.NewPlaylistDialog(dlg, "Garota de Ipanema, by Tom Jobim")
	ctrls = checkWindow("New playlist", npd)
	R.check("ACE-03 New playlist: name, description, public, add song, OK, Cancel", ctrls == [npd.nameEdit, npd.descriptionEdit, npd.publicCheck, npd.addSongCheck] + [c for c in ctrls if c.GetId() in (wx.ID_OK, wx.ID_CANCEL)] and len(ctrls) == 6, [plain(structuralName(c)) for c in ctrls])
	R.check("ACE-06 New playlist starts on the name", lastFocus() is npd.nameEdit)
	npd.Destroy()

	# sort dialog
	sd = mainDialog.SortDialog(dlg, "Playlist 3", "position", False, canSave=True)
	ctrls = checkWindow("Sort playlist (own playlist)", sd)
	R.check("ACE-03 Sort: sort by, order, save on Spotify, OK, Cancel", ctrls[:3] == [sd.keyChoice, sd.directionChoice, sd.saveCheck] and len(ctrls) == 5, [plain(structuralName(c)) for c in ctrls])
	R.check("ACE-06 Sort starts on Sort by", lastFocus() is sd.keyChoice)
	sd.Destroy()
	sd = mainDialog.SortDialog(dlg, "Playlist 5", "position", False, canSave=False)
	ctrls = checkWindow("Sort playlist (someone else's)", sd)
	R.check("ACE-04 Save on Spotify absent for someone else's playlist", sd.saveCheck is None and len(ctrls) == 4)
	sd.Destroy()

	# settings panel
	frame = wx.Frame(None, title="NVDA settings")
	panel = settingsPanel.SpotifySettingsPanel(frame)
	frame.Fit()
	frame.Show()
	checkWindow("Settings panel", panel)
	R.check("ACE-08 settings category has a title", bool(panel.title))
	frame.Destroy()

	# sign out: focus on Sign in
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	dlg.onSignOut(None)
	R.check("ACE-06 focus on Sign in after signing out", lastFocus() is dlg.signInButton, lastFocus())
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.OK
	closeWindow()

	# -- commands ---------------------------------------------------------------------------------
	scripts = [getattr(SpotifyNVDA.GlobalPlugin, n) for n in dir(SpotifyNVDA.GlobalPlugin) if n.startswith("script_")]
	R.check("ACE-10 every command has a description", all(s.__doc__ for s in scripts), [s.__name__ for s in scripts if not s.__doc__])
	R.check("ACE-10 commands are in the Spotify category", bool(SpotifyNVDA.GlobalPlugin.scriptCategory) and SpotifyNVDA.SCRIPT_CATEGORY == plain_text("Spotify"))
	ours = {}
	for s in scripts:
		for g in s.gestures:
			ours[_normalGesture(g)] = s.__name__
	R.check("ACE-09 eight commands have a default shortcut", len(ours) == 8, ours)
	defaults, scanned = defaultNvdaGestures()
	normalDefaults = {_normalGesture(g) for g in defaults}
	clash = sorted(g for g in ours if g in normalDefaults)
	R.check("ACE-09 no clash with NVDA's own commands%s" % (" (scanned from the installed NVDA)" if scanned else ""), not clash, clash)
	others = otherAddonGestures()
	clash = sorted("%s (%s)" % (g, others[g]) for g in ours if g in others)
	R.check("ACE-09 no clash with the other add-ons installed here", not clash, clash)

	# -- page shown in the browser after the sign-in ------------------------------------------------
	auth = importlib.import_module("SpotifyNVDA.auth")
	messages = importlib.import_module("SpotifyNVDA.messages")
	import _helpers
	import urllib.request

	port = _helpers.freePort()
	receiver = auth.LoopbackReceiver("s" * 43, port, messages.callbackPages())
	try:
		with urllib.request.urlopen("http://127.0.0.1:%d/callback?code=x&state=%s" % (port, "s" * 43), timeout=5) as r:  # nosec B310 - local test
			page = r.read().decode("utf-8")
	finally:
		receiver.close()
	lang = "pt-BR" if LANG == "pt_BR" else "en"
	R.check("ACE-11 browser page has language, title, main and heading", ('lang="%s"' % lang) in page and "<title>" in page and "<main>" in page and "<h1>" in page, page[:200])

	# -- translations -------------------------------------------------------------------------------
	missing = ["%s:%d" % (p, line) for p, line, _m, ok in _strings.translatable() if not ok]
	R.check("ACE-12 every translatable text has a Translators comment", not missing, missing)

	# -- documentation --------------------------------------------------------------------------------
	for docLang in ("en", "pt_BR"):
		path = os.path.join(HERE, "..", "addon", "doc", docLang, "readme.html")
		if os.path.isfile(path):
			with open(path, encoding="utf-8") as f:
				docHtml = f.read()
			R.check("ACE-16 documentation %s has language, headings and real tables" % docLang, ('lang="%s"' % docLang.replace("_", "-")) in docHtml and "<h2>" in docHtml and "<th>" in docHtml)


def plain_text(english):
	"""The text the user hears (translated when testing in Portuguese)."""
	return _(english)  # noqa: F821


if __name__ == "__main__":
	try:
		run()
	except Exception:
		import traceback

		traceback.print_exc()
		R.check("suite finished without crashing", False, traceback.format_exc()[-500:])
	sys.exit(R.finish())
