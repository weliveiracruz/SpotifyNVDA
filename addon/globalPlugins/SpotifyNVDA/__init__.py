# -*- coding: UTF-8 -*-
# SpotifyNVDA - global plugin
# Listen to Spotify from NVDA: sign in, playlists, search and playback shortcuts.
# Copyright (C) 2026 Wellington Cruz <weliveiracruz@gmail.com>
# This file is covered by the GNU General Public License, version 2.
# See the file COPYING for more details.

import queue
import threading

import addonHandler
import config
import globalPluginHandler
import globalVars
import gui
import queueHandler
import ui
import wx
from logHandler import log
from scriptHandler import script

from . import messages
from .auth import DEFAULT_PORT
from .errors import SpotifyError
from .service import SpotifyService, launchSpotifyApp

addonHandler.initTranslation()

CONFIG_SECTION = "SpotifyNVDA"
CONFIG_SPEC = {
	"clientId": "string(default='')",
	"port": "integer(default=%d, min=1024, max=65535)" % DEFAULT_PORT,
	"volumeStep": "integer(default=10, min=1, max=50)",
	"launchApp": "boolean(default=True)",
	"hideApp": "boolean(default=True)",
}
# Translators: category of the SpotifyNVDA commands in the Input gestures dialog.
SCRIPT_CATEGORY = _("Spotify")


def disableInSecureMode(cls):
	"""Does not load the add-on on secure screens (logon, UAC), as recommended by NV Access."""
	if globalVars.appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return cls


class Worker:
	"""Runs Spotify calls one at a time, away from NVDA's main thread."""

	def __init__(self):
		self._queue = queue.Queue()
		self._thread = threading.Thread(target=self._loop, name="SpotifyNVDA-worker", daemon=True)
		self._thread.start()

	def _loop(self):
		while True:
			job = self._queue.get()
			if job is None:
				return
			_run(*job)

	def submit(self, func, done):
		self._queue.put((func, done))

	def stop(self):
		self._queue.put(None)


def _run(func, done):
	try:
		result, error = func(), None
	except SpotifyError as e:
		result, error = None, e
	except Exception as e:
		# Never log arguments or responses: they may carry tokens.
		log.error("SpotifyNVDA: unexpected error (%s)" % type(e).__name__)
		result, error = None, SpotifyError("server", type(e).__name__)
	if done is not None:
		done(result, error)


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = SCRIPT_CATEGORY

	def __init__(self):
		super().__init__()
		config.conf.spec[CONFIG_SECTION] = CONFIG_SPEC
		self.service = SpotifyService(globalVars.appArgs.configPath, launchApp=self._launchApp)
		self.worker = Worker()
		from .settingsPanel import SpotifySettingsPanel

		SpotifySettingsPanel.plugin = self
		self._settingsPanelClass = SpotifySettingsPanel
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SpotifySettingsPanel)
		self._menuItem = None
		try:
			toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
			self._menuItem = toolsMenu.Append(
				wx.ID_ANY,
				# Translators: item of the NVDA Tools menu.
				_("&Spotify…"),
				# Translators: help text of the Tools menu item.
				_("Opens the SpotifyNVDA window: playlists, search and playback"),
			)
			gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda evt: self.openWindow(), self._menuItem)
		except Exception:
			log.debugWarning("SpotifyNVDA: could not add the Tools menu item", exc_info=True)

	def terminate(self):
		from .mainDialog import SpotifyDialog

		try:
			SpotifyDialog.closeInstance()
		except Exception:
			pass
		self.worker.stop()
		if self._settingsPanelClass.plugin is self:
			self._settingsPanelClass.plugin = None
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(self._settingsPanelClass)
		except ValueError:
			pass
		if self._menuItem is not None:
			try:
				gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self._menuItem)
			except Exception:
				pass
		super().terminate()

	# -- helpers used by the windows ---------------------------------------------------

	def getConfig(self, key):
		return config.conf[CONFIG_SECTION][key]

	def _launchApp(self):
		if self.getConfig("launchApp"):
			launchSpotifyApp(hide=self.getConfig("hideApp"))

	def speak(self, text):
		queueHandler.queueFunction(queueHandler.eventQueue, ui.message, text)

	def runInBackground(self, func, done, exclusive=False):
		"""Runs func away from the main thread; done(result, error) runs on the main thread.
		exclusive=True uses its own thread (the sign-in waits for the browser for minutes)."""

		def callback(result, error):
			wx.CallAfter(done, result, error)

		if exclusive:
			threading.Thread(target=_run, args=(func, callback), name="SpotifyNVDA-signin-wait", daemon=True).start()
		else:
			self.worker.submit(func, callback)

	def command(self, func, describe):
		"""A playback command: runs in the background and speaks describe(result) or the error."""

		def done(result, error):
			self.speak(messages.errorMessage(error) if error is not None else describe(result))

		self.worker.submit(func, done)

	def openWindow(self):
		from .mainDialog import SpotifyDialog

		gui.mainFrame.prePopup()
		try:
			SpotifyDialog.open(self)
		finally:
			gui.mainFrame.postPopup()

	def openSettings(self):
		gui.mainFrame.popupSettingsDialog(gui.settingsDialogs.NVDASettingsDialog, self._settingsPanelClass)

	def signOut(self):
		self.service.signOut()
		self.speak(messages.signedOut())

	def confirmSignOut(self, parent=None):
		"""Asks before signing out. Returns True when the user signed out."""
		answer = gui.messageBox(
			# Translators: confirmation before signing out.
			_("Sign out of Spotify? The session and the data saved by SpotifyNVDA on this computer will be deleted. To also remove the access, go to Spotify account, Manage apps."),
			# Translators: title of the sign-out confirmation.
			_("Sign out"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
			parent,
		)
		if answer != wx.YES:
			return False
		self.signOut()
		from .mainDialog import SpotifyDialog

		if SpotifyDialog._instance and SpotifyDialog._instance is not parent:
			SpotifyDialog._instance.afterSignOut(focus=False)
		return True

	# -- actions shared by scripts and buttons ---------------------------------------------

	def playPause(self):
		def describe(result):
			if result == "paused":
				return messages.paused()
			if result == "playing":
				return messages.playing()
			return messages.resumedText(result)

		self.command(self.service.player.playPause, describe)

	def resumeLast(self):
		self.command(self.service.player.resumeLast, messages.resumedText)

	def changeTrack(self, forward):
		player = self.service.player

		def describe(track):
			if track:
				return messages.trackText(track)
			# Translators: spoken after next/previous when the new song is not known yet.
			return _("Next song") if forward else _("Previous song")

		self.command(player.next if forward else player.previous, describe)

	def changeVolume(self, up):
		step = int(self.getConfig("volumeStep"))
		self.command(lambda: self.service.player.changeVolume(step if up else -step), messages.volumeText)

	# -- scripts ---------------------------------------------------------------------------

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Opens the Spotify window: sign in, playlists, search and playback"),
		gesture="kb:NVDA+alt+p",
	)
	def script_openWindow(self, gesture):
		wx.CallAfter(self.openWindow)

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: plays or pauses"),
		gesture="kb:NVDA+alt+space",
	)
	def script_playPause(self, gesture):
		self.playPause()

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: next song"),
		gesture="kb:NVDA+alt+rightArrow",
	)
	def script_nextTrack(self, gesture):
		self.changeTrack(True)

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: previous song"),
		gesture="kb:NVDA+alt+leftArrow",
	)
	def script_previousTrack(self, gesture):
		self.changeTrack(False)

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: turns the volume up"),
		gesture="kb:NVDA+alt+upArrow",
	)
	def script_volumeUp(self, gesture):
		self.changeVolume(True)

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: turns the volume down"),
		gesture="kb:NVDA+alt+downArrow",
	)
	def script_volumeDown(self, gesture):
		self.changeVolume(False)

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: says which song is playing"),
		gesture="kb:NVDA+alt+a",
	)
	def script_nowPlaying(self, gesture):
		self.command(self.service.player.nowPlaying, messages.nowPlayingText)

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: continues the last song played on your account"),
		gesture="kb:NVDA+alt+u",
	)
	def script_resumeLast(self, gesture):
		self.resumeLast()

	@script(
		# Translators: description of a command in the Input gestures dialog.
		description=_("Spotify: signs out of your account"),
	)
	def script_signOut(self, gesture):
		if not self.service.signedIn:
			self.speak(messages.errorMessage(SpotifyError("notSignedIn")))
			return
		wx.CallAfter(self.confirmSignOut)
