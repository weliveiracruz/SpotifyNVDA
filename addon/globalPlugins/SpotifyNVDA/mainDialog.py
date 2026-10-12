# -*- coding: UTF-8 -*-
# SpotifyNVDA - mainDialog.py
# The "Spotify" window: sign in/out, search, the tree of playlists and their
# songs, sorting, deleting and the playback actions.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import contextlib
import threading

import addonHandler
import gui
import wx
from gui import guiHelper

from . import library, messages
from .auth import isValidClientId
from .errors import SpotifyError
from .library import SORT_KEYS
from .service import openUrl

addonHandler.initTranslation()

#: Values of the Type box.
KIND_TRACK = 0
KIND_PLAYLIST = 1
KIND_IN_PLAYLISTS = 2
#: Above this many songs, opening a playlist says how many are coming.
BIG_PLAYLIST = 200


class NewPlaylistDialog(wx.Dialog):
	"""Asks the name, description and visibility of a new playlist."""

	def __init__(self, parent, selectedSong=None):
		# Translators: title of the dialog that creates a playlist.
		super().__init__(parent, title=_("New playlist"))
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: label of the playlist name field.
		self.nameEdit = sHelper.addLabeledControl(_("&Name:"), wx.TextCtrl, size=(360, -1))
		self.nameEdit.SetMaxLength(100)
		# Translators: label of the playlist description field.
		self.descriptionEdit = sHelper.addLabeledControl(_("&Description:"), wx.TextCtrl, size=(360, -1))
		self.descriptionEdit.SetMaxLength(300)
		# Translators: check box of the new playlist dialog.
		self.publicCheck = sHelper.addItem(wx.CheckBox(self, label=_("&Public playlist")))
		self.addSongCheck = None
		if selectedSong:
			self.addSongCheck = sHelper.addItem(wx.CheckBox(
				self,
				# Translators: check box of the new playlist dialog. {song} is "song, by artist".
				label=_("Add the &selected song: {song}").format(song=selectedSong.replace("&", "&&")),
			))
			self.addSongCheck.SetValue(True)
		sHelper.addDialogDismissButtons(wx.OK | wx.CANCEL, separated=True)
		self.Bind(wx.EVT_BUTTON, self.onOk, id=wx.ID_OK)
		main = wx.BoxSizer(wx.VERTICAL)
		main.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizer(main)
		main.Fit(self)
		self.CentreOnScreen()
		self.nameEdit.SetFocus()

	def onOk(self, evt):
		if not self.nameEdit.GetValue().strip():
			gui.messageBox(
				# Translators: message when the playlist name is empty.
				_("Type a name for the playlist."),
				# Translators: title of a message box.
				_("New playlist"),
				wx.OK | wx.ICON_WARNING,
				self,
			)
			self.nameEdit.SetFocus()
			return
		evt.Skip()

	def values(self):
		return {
			"name": self.nameEdit.GetValue().strip(),
			"description": self.descriptionEdit.GetValue().strip(),
			"public": self.publicCheck.GetValue(),
			"addSong": bool(self.addSongCheck and self.addSongCheck.GetValue()),
		}


class SortDialog(wx.Dialog):
	"""Chooses how a playlist is sorted and, for the user's own playlists,
	whether the new order is saved on Spotify."""

	def __init__(self, parent, playlistName, key, descending, canSave):
		# Translators: title of the dialog that sorts a playlist. {name} is the playlist.
		super().__init__(parent, title=_("Sort {name}").format(name=playlistName))
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: label of the box that chooses how to sort a playlist.
		self.keyChoice = sHelper.addLabeledControl(_("Sort &by:"), wx.Choice, choices=messages.sortKeyLabels())
		self.keyChoice.SetSelection(SORT_KEYS.index(key) if key in SORT_KEYS else 0)
		self.directionChoice = sHelper.addLabeledControl(
			# Translators: label of the box that chooses ascending or descending order.
			_("&Order:"),
			wx.Choice,
			choices=[
				# Translators: ascending order.
				_("Ascending (A to Z, oldest first, shortest first)"),
				# Translators: descending order.
				_("Descending (Z to A, newest first, longest first)"),
			],
		)
		self.directionChoice.SetSelection(1 if descending else 0)
		self.saveCheck = None
		if canSave:
			self.saveCheck = sHelper.addItem(wx.CheckBox(
				self,
				# Translators: check box of the sort dialog.
				label=_("&Save this order on Spotify (changes the playlist on every device)"),
			))
		sHelper.addDialogDismissButtons(wx.OK | wx.CANCEL, separated=True)
		main = wx.BoxSizer(wx.VERTICAL)
		main.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		self.SetSizer(main)
		main.Fit(self)
		self.CentreOnScreen()
		self.keyChoice.SetFocus()

	def values(self):
		return {
			"key": SORT_KEYS[max(0, self.keyChoice.GetSelection())],
			"descending": self.directionChoice.GetSelection() == 1,
			"save": bool(self.saveCheck and self.saveCheck.GetValue()),
		}


class SpotifyDialog(wx.Dialog):
	_instance = None

	@classmethod
	def open(cls, plugin):
		if cls._instance:
			cls._instance.Raise()
			cls._instance.refreshState()
			cls._instance.focusFirst()
			return cls._instance
		dlg = cls(gui.mainFrame, plugin)
		cls._instance = dlg
		dlg.Show()
		dlg.Raise()
		dlg.focusFirst()
		return dlg

	@classmethod
	def closeInstance(cls):
		if cls._instance:
			cls._instance.Destroy()
			cls._instance = None

	def __init__(self, parent, plugin):
		# Translators: title of the main window of the add-on.
		super().__init__(parent, title=_("Spotify"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.plugin = plugin
		self.listKind = None
		self.topCount = 0
		self.myPlaylists = None
		self._signInCancel = None
		#: True when the user moved to an item of the tree that was not played yet.
		self._freshSelection = False
		#: Above 0 while the add-on itself changes the tree (not the user).
		self._programmatic = 0
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Translators: label of the read-only status field of the Spotify window.
		self.statusEdit = sHelper.addLabeledControl(_("S&tatus:"), wx.TextCtrl, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_RICH2, size=(520, 50))

		accountRow = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: button that opens the Spotify login page.
		self.signInButton = accountRow.addButton(self, label=_("Sign &in with Spotify"))
		# Translators: button that signs out of the Spotify account.
		self.signOutButton = accountRow.addButton(self, label=_("Sign &out"))
		sHelper.addItem(accountRow)

		searchRow = guiHelper.BoxSizerHelper(self, orientation=wx.HORIZONTAL)
		# Translators: label of the search field.
		self.searchEdit = searchRow.addLabeledControl(_("&Search for:"), wx.TextCtrl, style=wx.TE_PROCESS_ENTER, size=(260, -1))
		self.searchEdit.SetMaxLength(200)
		self.kindChoice = searchRow.addLabeledControl(
			# Translators: label of the box that chooses what to search.
			_("T&ype:"),
			wx.Choice,
			choices=[
				# Translators: search for songs.
				_("Songs"),
				# Translators: search for playlists.
				_("Playlists"),
				# Translators: search for songs inside the user's playlists.
				_("Songs in my playlists"),
			],
		)
		self.kindChoice.SetSelection(KIND_TRACK)
		# Translators: button that runs the search.
		self.searchButton = searchRow.addItem(wx.Button(self, label=_("Searc&h")))
		sHelper.addItem(searchRow)

		self.resultsLabel = wx.StaticText(self, label=self._resultsLabel())
		self.resultsTree = wx.TreeCtrl(self, size=(520, 300), style=wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_SINGLE)
		self.root = self.resultsTree.AddRoot("")
		sHelper.addItem(self.resultsLabel)
		sHelper.addItem(self.resultsTree, flag=wx.EXPAND, proportion=1)

		actions = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# One button plays: the item just chosen in the tree ("Play <name>") or,
		# otherwise, plays/pauses Spotify and continues the last song when nothing is loaded.
		self.playButton = actions.addButton(self, label=self._playPauseLabel())
		# Translators: button that adds the selected song to a playlist.
		self.addButton = actions.addButton(self, label=_("&Add to playlist…"))
		# Translators: button that removes the selected song from its playlist.
		self.removeButton = actions.addButton(self, label=_("Remo&ve from playlist"))
		# Translators: button that lists the user playlists.
		self.myPlaylistsButton = actions.addButton(self, label=_("&My playlists"))
		# Translators: button that creates a playlist.
		self.newPlaylistButton = actions.addButton(self, label=_("&New playlist…"))
		sHelper.addItem(actions)
		actions2 = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: button that sorts the songs of the selected playlist.
		self.sortButton = actions2.addButton(self, label=_("Or&der songs…"))
		# Translators: button that deletes the selected playlist.
		self.deleteButton = actions2.addButton(self, label=_("D&elete playlist"))
		# Translators: button that closes the Spotify window.
		self.closeButton = actions2.addButton(self, id=wx.ID_CLOSE, label=_("C&lose"))
		sHelper.addItem(actions2)

		main = wx.BoxSizer(wx.VERTICAL)
		main.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL | wx.EXPAND, proportion=1)
		self.SetSizer(main)
		main.Fit(self)
		self.SetEscapeId(wx.ID_CLOSE)

		self.signInButton.Bind(wx.EVT_BUTTON, self.onSignIn)
		self.signOutButton.Bind(wx.EVT_BUTTON, self.onSignOut)
		self.searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
		self.searchEdit.Bind(wx.EVT_TEXT_ENTER, self.onSearch)
		self.resultsTree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.onPlay)
		self.resultsTree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.onExpanding)
		self.resultsTree.Bind(wx.EVT_TREE_SEL_CHANGED, self.onSelectionChanged)
		self.resultsTree.Bind(wx.EVT_TREE_KEY_DOWN, self.onTreeKey)
		self.playButton.Bind(wx.EVT_BUTTON, self.onPlayButton)
		self.addButton.Bind(wx.EVT_BUTTON, self.onAddToPlaylist)
		self.removeButton.Bind(wx.EVT_BUTTON, self.onRemoveSong)
		self.myPlaylistsButton.Bind(wx.EVT_BUTTON, lambda evt: self.loadMyPlaylists())
		self.newPlaylistButton.Bind(wx.EVT_BUTTON, self.onNewPlaylist)
		self.sortButton.Bind(wx.EVT_BUTTON, self.onSort)
		self.deleteButton.Bind(wx.EVT_BUTTON, self.onDelete)
		self.closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		self.Bind(wx.EVT_CLOSE, self.onClose)

		self.refreshState()
		self.CentreOnScreen()
		if self.service.signedIn:
			self.loadMyPlaylists(announce=False)

	@property
	def service(self):
		return self.plugin.service

	# -- state -----------------------------------------------------------------------

	def _resultsLabel(self, count=None):
		if self.listKind == "myPlaylists":
			# Translators: label of the results list showing the user playlists. {count} is a number.
			return _("&Results: my playlists ({count})").format(count=count)
		if self.listKind == "tracks":
			# Translators: label of the results list after a song search.
			return _("&Results: songs found ({count})").format(count=count)
		if self.listKind == "playlists":
			# Translators: label of the results list after a playlist search.
			return _("&Results: playlists found ({count})").format(count=count)
		if self.listKind == "inPlaylists":
			# Translators: label of the results list after searching inside the playlists. {count} is a number of songs.
			return _("&Results: songs in my playlists ({count})").format(count=count)
		# Translators: label of the empty results list.
		return _("&Results:")

	def refreshState(self):
		signedIn = self.service.signedIn
		signingIn = self._signInCancel is not None
		if signingIn:
			self.statusEdit.SetValue(messages.waitingBrowser())
		else:
			self.statusEdit.SetValue(messages.statusText(signedIn, self.service.session.user))
		if signingIn:
			# Translators: label of the sign-in button while waiting for the browser.
			self.signInButton.SetLabel(_("Cancel sign-&in"))
		else:
			# Translators: button that opens the Spotify login page.
			self.signInButton.SetLabel(_("Sign &in with Spotify"))
		self.signInButton.Show(not signedIn)
		self.signOutButton.Show(signedIn)
		for ctrl in (self.searchEdit, self.kindChoice, self.searchButton, self.resultsTree, self.myPlaylistsButton, self.newPlaylistButton, self.playButton):
			ctrl.Enable(signedIn)
		if not signedIn:
			self.clearTree(None)
		self.updateButtons()
		self.Layout()

	def onSelectionChanged(self, evt):
		# The tree also sends this event while the window is being destroyed.
		if not self._alive():
			return
		if not self._programmatic and self.resultsTree.HasFocus():
			self._freshSelection = True
		self.updateButtons()

	@contextlib.contextmanager
	def programmatic(self):
		"""Changes of the tree made by the add-on: they are not a choice of the user."""
		self._programmatic += 1
		try:
			yield
		finally:
			self._programmatic -= 1

	def select(self, node):
		with self.programmatic():
			self.resultsTree.SelectItem(node)
		self._freshSelection = False
		self.updateButtons()

	def offerSelection(self):
		"""After a search, the play button offers the result that is selected."""
		self._freshSelection = True
		self.updateButtons()

	@staticmethod
	def _playPauseLabel():
		# Translators: the play button when no new item was chosen: plays or pauses Spotify (and continues the last song when nothing is loaded).
		return _("&Play/pause")

	def _playItemLabel(self, item):
		# Translators: the play button after choosing an item in the tree. {name} is the song or playlist.
		return _("&Play {name}").format(name=(item.get("name") or "").replace("&", "&&"))

	def chosenItem(self):
		"""The playable item the user just moved to in the tree, or None."""
		if not self._freshSelection:
			return None
		node, data = self.selectedNode()
		if not data or data.get("node") not in ("playlist", "track"):
			return None
		if data["node"] == "track" and not data["item"].get("playable", True):
			return None
		return data["item"]

	def updateButtons(self):
		signedIn = self.service.signedIn
		node, data = self.selectedNode()
		kind = data.get("node") if data else None
		item = data.get("item") if data else None
		playableTrack = kind == "track" and item.get("playable", True)
		chosen = self.chosenItem()
		label = self._playItemLabel(chosen) if chosen else self._playPauseLabel()
		if self.playButton.GetLabel() != label:
			self.playButton.SetLabel(label)
			self.Layout()
		self.playButton.Enable(signedIn)
		self.addButton.Enable(signedIn and playableTrack)
		inPlaylist = data.get("playlist") if kind == "track" else None
		self.removeButton.Enable(bool(signedIn and playableTrack and inPlaylist and self._isMine(inPlaylist)))
		self.sortButton.Enable(signedIn and self.playlistOf(node) is not None)
		self.deleteButton.Enable(signedIn and kind == "playlist")

	def focusFirst(self):
		if not self.service.signedIn:
			self.signInButton.SetFocus()
		elif self.topCount:
			self.resultsTree.SetFocus()
		else:
			self.searchEdit.SetFocus()

	def _alive(self):
		return bool(self) and not self.IsBeingDeleted()

	def run(self, func, onSuccess, focus=None, onError=None):
		"""Runs func in the background and onSuccess(result) back in the window.
		Errors are spoken; the focus goes to `focus` or stays where it is (RA-06)."""

		def done(result, error):
			if not self._alive():
				return
			if error is not None:
				if onError is not None:
					onError(error)
				self.plugin.speak(messages.errorMessage(error))
				if getattr(error, "kind", "") in ("auth", "notSignedIn"):
					self.refreshState()
					self.focusFirst()
			else:
				onSuccess(result)
			if focus is not None and focus.IsEnabled() and focus.IsShown() and self.IsActive():
				focus.SetFocus()

		self.plugin.runInBackground(func, done)

	# -- tree ------------------------------------------------------------------------

	def clearTree(self, kind):
		self.listKind = kind
		self.topCount = 0
		self._freshSelection = False
		with self.programmatic():
			self.resultsTree.DeleteChildren(self.root)
		self.resultsLabel.SetLabel(self._resultsLabel(0))

	def _setCount(self, count):
		self.topCount = count
		self.resultsLabel.SetLabel(self._resultsLabel(count))

	def addPlaylistNode(self, playlist, filterWords=None):
		node = self.resultsTree.AppendItem(self.root, messages.itemText(playlist), data={"node": "playlist", "item": playlist, "loaded": False, "filter": filterWords})
		self.resultsTree.AppendItem(node, messages.loading(), data={"node": "info"})
		return node

	def addTrackNode(self, parent, entry, playlist):
		return self.resultsTree.AppendItem(parent, messages.entryText(entry), data={"node": "track", "item": entry, "playlist": playlist})

	def setTopItems(self, kind, items):
		self.clearTree(kind)
		for item in items:
			if item.get("kind") == "playlist":
				self.addPlaylistNode(item)
			else:
				self.addTrackNode(self.root, item, None)
		self._setCount(len(items))
		self.selectFirst()
		self.updateButtons()

	def _recount(self):
		"""Number shown in the list name: songs when searching inside the playlists, top items otherwise."""
		tree = self.resultsTree
		count = 0
		child, cookie = tree.GetFirstChild(self.root)
		while child.IsOk():
			if self.listKind == "inPlaylists":
				count += tree.GetChildrenCount(child, False)
			else:
				count += 1
			child, cookie = tree.GetNextChild(self.root, cookie)
		return count

	def selectFirst(self):
		first, _cookie = self.resultsTree.GetFirstChild(self.root)
		if first.IsOk():
			self.select(first)

	def selectedNode(self):
		node = self.resultsTree.GetSelection()
		if not node.IsOk() or node == self.root:
			return None, None
		return node, self.resultsTree.GetItemData(node)

	def playlistOf(self, node):
		"""The playlist node of a playlist or of a song inside a playlist."""
		if node is None or not node.IsOk():
			return None
		data = self.resultsTree.GetItemData(node)
		if data and data.get("node") == "playlist":
			return node
		if data and data.get("node") == "track" and data.get("playlist"):
			return self.resultsTree.GetItemParent(node)
		return None

	def renderPlaylist(self, node, entries):
		"""Shows the songs of a playlist node, in the chosen order (RF-14) and
		only those of the search when the node comes from a search (RF-13)."""
		tree = self.resultsTree
		data = tree.GetItemData(node)
		playlist = data["item"]
		wasExpanded = tree.IsExpanded(node)
		with self.programmatic():
			tree.Freeze()
			try:
				tree.DeleteChildren(node)
				data["loaded"] = True
				if entries is None:
					tree.AppendItem(node, messages.songsHidden(), data={"node": "info"})
					return 0
				entries = self.service.library.sorted(playlist["id"], entries)
				if data.get("filter"):
					entries = [e for e in entries if library.matches(e, data["filter"])]
				else:
					# The real number of songs, also in the name of the playlist.
					playlist["total"] = len(entries)
					tree.SetItemText(node, messages.itemText(playlist))
				if not entries:
					tree.AppendItem(node, messages.playlistEmpty(), data={"node": "info"})
				for entry in entries:
					self.addTrackNode(node, entry, playlist)
				if wasExpanded:
					tree.Expand(node)
			finally:
				tree.Thaw()
		return len(entries)

	def loadPlaylistNode(self, node, announce=True, selectIndex=None):
		data = self.resultsTree.GetItemData(node)
		if data.get("loading"):
			return
		data["loading"] = True
		playlistId = data["item"]["id"]
		lib = self.service.library

		def total(count):
			# Big playlists take a few seconds: say how many songs are coming.
			if announce and count > BIG_PLAYLIST:
				self.plugin.speak(messages.loadingSongs(count))

		def load():
			try:
				return lib.items(playlistId, onTotal=total)
			except SpotifyError as e:
				if e.kind == "forbidden":
					return None
				raise

		def loaded(entries):
			data["loading"] = False
			if not node.IsOk():
				return
			count = self.renderPlaylist(node, entries)
			if selectIndex is not None:
				children = []
				child, cookie = self.resultsTree.GetFirstChild(node)
				while child.IsOk():
					children.append(child)
					child, cookie = self.resultsTree.GetNextChild(node, cookie)
				self.select(children[min(selectIndex, len(children) - 1)] if children else node)
			if announce:
				self.plugin.speak(messages.songsHidden() if entries is None else messages.songsCount(count))

		self.run(load, loaded, onError=lambda error: data.update(loading=False))

	def onExpanding(self, evt):
		node = evt.GetItem()
		data = self.resultsTree.GetItemData(node)
		if data and data.get("node") == "playlist" and not data.get("loaded"):
			self.loadPlaylistNode(node)
		evt.Skip()

	def reloadPlaylist(self, playlistId, selectIndex=None):
		"""After a change on Spotify, the songs are read again where they are shown."""
		self.service.library.forget(playlistId)
		tree = self.resultsTree
		child, cookie = tree.GetFirstChild(self.root)
		while child.IsOk():
			data = tree.GetItemData(child)
			if data and data.get("node") == "playlist" and data["item"]["id"] == playlistId and data.get("loaded"):
				if tree.IsExpanded(child):
					data["loaded"] = False
					self.loadPlaylistNode(child, announce=False, selectIndex=selectIndex)
				else:
					with self.programmatic():
						tree.DeleteChildren(child)
						tree.AppendItem(child, messages.loading(), data={"node": "info"})
					data["loaded"] = False
			child, cookie = tree.GetNextChild(self.root, cookie)

	def onTreeKey(self, evt):
		if evt.GetKeyCode() == wx.WXK_DELETE:
			node, data = self.selectedNode()
			if data and data.get("node") == "playlist":
				self.onDelete(evt)
				return
			if data and data.get("node") == "track" and data.get("playlist"):
				self.onRemoveSong(evt)
				return
		evt.Skip()

	# -- account ---------------------------------------------------------------------

	def onSignIn(self, evt):
		if self._signInCancel is not None:
			self._signInCancel.set()
			return
		clientId = self.plugin.getConfig("clientId")
		if not isValidClientId(clientId):
			gui.messageBox(
				messages.errorMessage(SpotifyError("noClientId" if not clientId.strip() else "invalidClientId")),
				# Translators: title of a message box.
				_("Spotify"),
				wx.OK | wx.ICON_INFORMATION,
				self,
			)
			self.plugin.openSettings()
			return
		port = self.plugin.getConfig("port")
		cancel = threading.Event()
		self._signInCancel = cancel
		self.refreshState()
		self.plugin.speak(messages.waitingBrowser())

		def signIn():
			return self.service.signIn(clientId, port, openUrl, cancelEvent=cancel, pages=messages.callbackPages())

		def done(user, error):
			if not self._alive():
				return
			self._signInCancel = None
			self.refreshState()
			self.Raise()
			if error is not None:
				self.plugin.speak(messages.errorMessage(error))
				self.signInButton.SetFocus()
				return
			self.plugin.speak(messages.signedInText(user))
			self.searchEdit.SetFocus()
			self.loadMyPlaylists(announce=False)

		self.plugin.runInBackground(signIn, done, exclusive=True)

	def onSignOut(self, evt):
		if not self.plugin.confirmSignOut(self):
			self.signOutButton.SetFocus()
			return
		self.afterSignOut()

	def afterSignOut(self, focus=True):
		self.myPlaylists = None
		self.refreshState()
		if focus:
			self.signInButton.SetFocus()

	# -- lists -----------------------------------------------------------------------

	def loadMyPlaylists(self, announce=True):
		if announce:
			self.plugin.speak(messages.loading())

		def shown(items):
			self.myPlaylists = items
			self.setTopItems("myPlaylists", items)
			self.plugin.speak(self.resultsLabel.GetLabel().replace("&", ""))

		self.run(self.service.client.myPlaylists, shown, focus=self.resultsTree)

	def _searchablePlaylists(self, playlists):
		userId = self.service.session.user.get("id")
		return [p for p in playlists if not userId or p.get("ownerId") == userId or p.get("collaborative")]

	def onSearch(self, evt):
		text = self.searchEdit.GetValue().strip()
		if not text:
			# Translators: spoken when the search field is empty.
			self.plugin.speak(_("Type what you want to search for."))
			self.searchEdit.SetFocus()
			return
		choice = self.kindChoice.GetSelection()
		if choice == KIND_IN_PLAYLISTS:
			return self.searchInPlaylists(text)
		kind = "playlist" if choice == KIND_PLAYLIST else "track"
		self.plugin.speak(messages.loading())

		def shown(items):
			self.setTopItems("playlists" if kind == "playlist" else "tracks", items)
			self.offerSelection()
			if items:
				self.plugin.speak(self.resultsLabel.GetLabel().replace("&", ""))
			else:
				self.plugin.speak(messages.noResults())

		self.run(lambda: self.service.client.search(text, kind), shown, focus=self.resultsTree)

	def searchInPlaylists(self, text):
		self.plugin.speak(messages.searchingPlaylists())
		known = self.myPlaylists
		lib = self.service.library

		def search():
			playlists = known if known is not None else self.service.client.myPlaylists()
			found, _skipped = lib.search(text, self._searchablePlaylists(playlists))
			return playlists, found

		def shown(result):
			playlists, found = result
			self.myPlaylists = playlists
			self.clearTree("inPlaylists")
			words = library.normalize(text).split()
			total = 0
			for playlist, hits in found:
				node = self.addPlaylistNode(playlist, filterWords=words)
				total += self.renderPlaylist(node, lib.cached(playlist["id"]))
				self.resultsTree.Expand(node)
			self._setCount(total)
			self.selectFirst()
			self.offerSelection()
			if total:
				self.plugin.speak(messages.foundInPlaylists(total, len(found)))
			else:
				self.plugin.speak(messages.noResults())

		self.run(search, shown, focus=self.resultsTree)

	# -- actions ---------------------------------------------------------------------

	def onPlayButton(self, evt):
		"""The single play button: the item just chosen in the tree, otherwise
		play/pause (which also continues the last song when nothing is loaded)."""
		if self.chosenItem() is not None:
			self.onPlay(evt)
		else:
			self.plugin.playPause()

	def onPlay(self, evt):
		node, data = self.selectedNode()
		if not data or data.get("node") not in ("playlist", "track"):
			return
		self._freshSelection = False
		self.updateButtons()
		item = data["item"]
		player = self.service.player
		if data["node"] == "track" and not item.get("playable", True):
			self.plugin.speak(messages.notPlayable())
			return
		if data["node"] == "track" and data.get("playlist"):
			playlist = data["playlist"]
			self.run(lambda: player.playInContext(playlist["uri"], item["uri"]), lambda _r: self.plugin.speak(messages.playingItemText(item)))
		else:
			self.run(lambda: player.playItem(item), lambda i: self.plugin.speak(messages.playingItemText(i)))

	def _editablePlaylists(self):
		userId = self.service.session.user.get("id")
		return [p for p in (self.myPlaylists or []) if not userId or p.get("ownerId") == userId]

	def _isMine(self, playlist):
		userId = self.service.session.user.get("id")
		return not userId or playlist.get("ownerId") == userId or bool(playlist.get("collaborative"))

	def onAddToPlaylist(self, evt):
		node, data = self.selectedNode()
		if not data or data.get("node") != "track" or not data["item"].get("playable", True):
			return
		item = data["item"]

		def choose(playlists):
			self.myPlaylists = playlists
			editable = self._editablePlaylists()
			if not editable:
				# Translators: spoken when the user has no playlist of their own.
				self.plugin.speak(_("You have no playlist of your own yet. Use New playlist."))
				self.newPlaylistButton.SetFocus()
				return
			dlg = wx.SingleChoiceDialog(
				self,
				# Translators: message of the dialog that chooses a playlist.
				_("Choose the playlist for {song}").format(song=messages.trackText(item)),
				# Translators: title of the dialog that chooses a playlist.
				_("Add to playlist"),
				[p["name"] for p in editable],
			)
			try:
				if dlg.ShowModal() != wx.ID_OK:
					self.resultsTree.SetFocus()
					return
				playlist = editable[dlg.GetSelection()]
			finally:
				dlg.Destroy()

			def added(_r):
				self.reloadPlaylist(playlist["id"])
				self.plugin.speak(messages.addedToPlaylist(item["name"], playlist["name"]))

			self.run(
				lambda: self.service.client.addToPlaylist(playlist["id"], [item["uri"]]),
				added,
				focus=self.resultsTree,
			)

		if self.myPlaylists is None:
			self.run(self.service.client.myPlaylists, choose)
		else:
			choose(self.myPlaylists)

	def onNewPlaylist(self, evt):
		node, data = self.selectedNode()
		item = data["item"] if data and data.get("node") == "track" and data["item"].get("playable", True) else None
		song = messages.trackText(item) if item else None
		dlg = NewPlaylistDialog(self, song)
		try:
			if dlg.ShowModal() != wx.ID_OK:
				self.newPlaylistButton.SetFocus()
				return
			values = dlg.values()
		finally:
			dlg.Destroy()

		def create():
			playlist = self.service.client.createPlaylist(values["name"], values["description"], values["public"])
			if values["addSong"] and song:
				self.service.client.addToPlaylist(playlist["id"], [item["uri"]])
			return playlist

		def created(playlist):
			self.myPlaylists = None
			self.plugin.speak(messages.playlistCreated(playlist["name"]))
			if self.listKind == "myPlaylists":
				self.loadMyPlaylists(announce=False)

		self.run(create, created, focus=self.newPlaylistButton)

	def onRemoveSong(self, evt):
		node, data = self.selectedNode()
		if not data or data.get("node") != "track" or not data.get("playlist") or not data["item"].get("playable", True):
			return
		playlist = data["playlist"]
		if not self._isMine(playlist):
			return
		entry = data["item"]
		lib = self.service.library
		copies = lib.copies(playlist["id"], entry["uri"])
		answer = gui.messageBox(
			messages.confirmRemoveSong(messages.trackText(entry), playlist["name"], copies),
			# Translators: title of the confirmation before removing a song from a playlist.
			_("Remove from playlist"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
			self,
		)
		if answer != wx.YES:
			self.resultsTree.SetFocus()
			return
		parent = self.resultsTree.GetItemParent(node)
		index = 0
		child, cookie = self.resultsTree.GetFirstChild(parent)
		while child.IsOk() and child != node:
			index += 1
			child, cookie = self.resultsTree.GetNextChild(parent, cookie)

		def removed(_count):
			self.reloadPlaylist(playlist["id"], selectIndex=index)
			self.plugin.speak(messages.songRemoved(entry["name"], playlist["name"]))

		self.run(lambda: lib.removeSong(playlist["id"], entry), removed, focus=self.resultsTree)

	def onSort(self, evt):
		node = self.playlistOf(self.selectedNode()[0])
		if node is None:
			return
		data = self.resultsTree.GetItemData(node)
		playlist = data["item"]
		lib = self.service.library
		key, descending = lib.sortPref(playlist["id"])
		dlg = SortDialog(self, playlist["name"], key, descending, canSave=self._isMine(playlist))
		try:
			if dlg.ShowModal() != wx.ID_OK:
				self.resultsTree.SetFocus()
				return
			values = dlg.values()
		finally:
			dlg.Destroy()
		labels = messages.sortKeyLabels()
		label = labels[SORT_KEYS.index(values["key"])]
		lib.setSortPref(playlist["id"], values["key"], values["descending"])
		if data.get("loaded"):
			self.renderPlaylist(node, lib.cached(playlist["id"]))
		self.select(node)
		self.resultsTree.SetFocus()
		self.plugin.speak(messages.sortedText(playlist["name"], label, values["descending"]))
		if not values["save"]:
			return
		answer = gui.messageBox(
			messages.confirmSaveOrder(playlist["name"]),
			# Translators: title of the confirmation before saving an order on Spotify.
			_("Save order"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
			self,
		)
		if answer != wx.YES:
			return
		self.plugin.speak(messages.savingOrder(playlist["name"]))

		def saved(_moves):
			self.reloadPlaylist(playlist["id"])
			self.plugin.speak(messages.orderSaved(playlist["name"]))

		self.run(lambda: lib.saveOrder(playlist["id"], values["key"], values["descending"]), saved, focus=self.resultsTree)

	def onDelete(self, evt):
		node, data = self.selectedNode()
		if not data or data.get("node") != "playlist":
			return
		playlist = data["item"]
		answer = gui.messageBox(
			messages.confirmDelete(playlist["name"]),
			# Translators: title of the confirmation before deleting a playlist.
			_("Delete playlist"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
			self,
		)
		if answer != wx.YES:
			self.resultsTree.SetFocus()
			return

		def deleted(_r):
			self.service.library.forget(playlist["id"])
			if self.myPlaylists is not None:
				self.myPlaylists = [p for p in self.myPlaylists if p["id"] != playlist["id"]]
			if node.IsOk():
				following = self.resultsTree.GetNextSibling(node)
				if not following.IsOk():
					following = self.resultsTree.GetPrevSibling(node)
				with self.programmatic():
					self.resultsTree.Delete(node)
				if following.IsOk():
					self.select(following)
				self._setCount(self._recount())
			self.updateButtons()
			self.plugin.speak(messages.deleted(playlist["name"]))

		self.run(lambda: self.service.client.deletePlaylist(playlist["id"]), deleted, focus=self.resultsTree)

	def onClose(self, evt):
		if self._signInCancel is not None:
			self._signInCancel.set()
		SpotifyDialog._instance = None
		self.Destroy()
