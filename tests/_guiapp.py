# -*- coding: UTF-8 -*-
"""Starts wxPython with the NVDA fakes and loads the real add-on (its
__init__.py), pointed at the Spotify mock. Shared by the GUI test suites."""

import os
import sys
import time

import _helpers
import nvda_stubs
from nvda_stubs import RECORD

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_helpers.ROOT, "addon", "globalPlugins"))

nvda_stubs.install()
import wx  # noqa: E402

import gui  # noqa: E402  (fake)

app = wx.App(False)
gui.mainFrame = gui.MainFrame()

import SpotifyNVDA  # noqa: E402  (the real add-on)
from SpotifyNVDA import mainDialog, settingsPanel  # noqa: E402

import config  # noqa: E402
import mock_spotify  # noqa: E402
from mock_spotify import MOCK  # noqa: E402

core = _helpers.loadCore()
BASE = _helpers.startMock()


def pump(until=lambda: False, timeout=8.0):
	end = time.time() + timeout
	while time.time() < end:
		wx.Yield()
		if until():
			return True
		time.sleep(0.02)
	wx.Yield()
	return bool(until())


def spokenSince(n):
	return nvda_stubs.spoken()[n:]


def waitSpoken(n, predicate, timeout=8.0):
	ok = pump(lambda: any(predicate(s) for s in spokenSince(n)), timeout)
	return ok


def newPlugin():
	MOCK.reset()
	plugin = SpotifyNVDA.GlobalPlugin()
	plugin.launches = []

	def launch():
		plugin.launches.append(1)
		MOCK.devicesHidden = False

	plugin.service = _helpers.makeService(core, launchApp=launch)
	conf = config.conf["SpotifyNVDA"]
	conf["clientId"] = mock_spotify.CLIENT_ID
	conf["port"] = _helpers.freePort()
	return plugin


class FakeBrowser(mock_spotify.FakeBrowser):
	pass


def useBrowser(mode="agree"):
	browser = mock_spotify.FakeBrowser(BASE, mode=mode)
	mainDialog.openUrl = browser
	return browser


def signInThroughWindow(plugin):
	"""Opens the window and signs in with the fake browser. Returns the dialog."""
	useBrowser()
	plugin.openWindow()
	dlg = mainDialog.SpotifyDialog._instance
	n = len(nvda_stubs.spoken())
	dlg.onSignIn(None)
	waitSpoken(n, lambda s: s.startswith("Signed in to Spotify"))
	pump(lambda: dlg.listKind == "myPlaylists")
	return dlg


def click(button):
	evt = wx.CommandEvent(wx.wxEVT_BUTTON, button.GetId())
	evt.SetEventObject(button)
	button.GetEventHandler().ProcessEvent(evt)


def topNodes(dlg):
	tree = dlg.resultsTree
	out = []
	child, cookie = tree.GetFirstChild(dlg.root)
	while child.IsOk():
		out.append(child)
		child, cookie = tree.GetNextChild(dlg.root, cookie)
	return out


def topTexts(dlg):
	return [dlg.resultsTree.GetItemText(n) for n in topNodes(dlg)]


def childNodes(dlg, node):
	tree = dlg.resultsTree
	out = []
	child, cookie = tree.GetFirstChild(node)
	while child.IsOk():
		out.append(child)
		child, cookie = tree.GetNextChild(node, cookie)
	return out


def childTexts(dlg, node):
	return [dlg.resultsTree.GetItemText(n) for n in childNodes(dlg, node)]


def findTop(dlg, text):
	for n in topNodes(dlg):
		if dlg.resultsTree.GetItemText(n).startswith(text):
			return n
	return None


def nativeKey(dlg, vk):
	"""Sends a real key press to the tree window (the path a keyboard takes),
	without depending on which window is in front."""
	import ctypes

	hwnd = ctypes.c_void_p(dlg.resultsTree.GetHandle())
	ctypes.windll.user32.SendMessageW(hwnd, 0x100, vk, 0)
	ctypes.windll.user32.SendMessageW(hwnd, 0x101, vk, 0)
	wx.Yield()


VK_RIGHT = 0x27
VK_LEFT = 0x25


def userSelect(dlg, node):
	"""The user moving to an item with the keyboard: the tree has the focus and
	the selection changes (the add-on did not select it itself)."""
	dlg.resultsTree.SetFocus()
	wx.Yield()
	dlg.resultsTree.SelectItem(node)
	wx.Yield()


def activate(dlg):
	"""What Enter or a double click on a tree item generates."""
	tree = dlg.resultsTree
	evt = wx.TreeEvent(wx.wxEVT_TREE_ITEM_ACTIVATED, tree, tree.GetSelection())
	tree.GetEventHandler().ProcessEvent(evt)


def closeWindow():
	if mainDialog.SpotifyDialog._instance:
		mainDialog.SpotifyDialog._instance.Close()
		pump(timeout=0.2)


__all__ = ["wx", "gui", "app", "SpotifyNVDA", "mainDialog", "settingsPanel", "config", "MOCK", "RECORD", "core", "BASE"]
