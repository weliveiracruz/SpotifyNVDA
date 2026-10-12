# -*- coding: UTF-8 -*-
# SpotifyNVDA - service.py
# Builds the objects of the add-on core (no user interface, no NVDA modules).
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import os
import sys

from .api import SpotifyClient
from .auth import AUTHORIZE_URL, Session
from .credentials import CredentialStore
from .errors import SpotifyError
from .library import Library
from .player import Player

#: The only addresses the add-on opens in the browser (RS-10).
DEVELOPER_DASHBOARD_URL = "https://developer.spotify.com/dashboard"
ACCOUNT_APPS_URL = "https://www.spotify.com/account/apps/"
_ALLOWED_PREFIXES = (AUTHORIZE_URL + "?", DEVELOPER_DASHBOARD_URL, ACCOUNT_APPS_URL)


def openUrl(url):
	"""Opens one of the fixed Spotify HTTPS addresses in the default browser."""
	if not any(url == p or url.startswith(p) for p in _ALLOWED_PREFIXES):
		raise ValueError("address not allowed")
	if sys.platform != "win32":
		raise OSError("no browser")
	os.startfile(url)  # nosec B606 - fixed https address, checked above, no shell


def launchSpotifyApp(hide=True):
	"""Opens the Spotify desktop app in the background (minimized, without the
	focus and, with hide=True, without any window). See background.py."""
	if sys.platform != "win32":
		return "unavailable"
	from .background import BackgroundLauncher

	return BackgroundLauncher().launch(hide=hide)


class SpotifyService:
	def __init__(self, configPath, store=None, oauth=None, opener=None, baseUrl=None, launchApp=launchSpotifyApp, sleep=None):
		self.store = store or CredentialStore(configPath)
		self.session = Session(self.store, oauth=oauth)
		kwargs = {"opener": opener}
		if baseUrl:
			kwargs["baseUrl"] = baseUrl
		if sleep:
			kwargs["sleep"] = sleep
		self.client = SpotifyClient(self.session, **kwargs)
		playerKwargs = {"launchApp": launchApp}
		if sleep:
			playerKwargs["sleep"] = sleep
		self.player = Player(self.client, self.store, **playerKwargs)
		self.library = Library(self.client, self.store)

	@property
	def signedIn(self):
		return self.session.signedIn

	def signIn(self, clientId, port, openBrowser, cancelEvent=None, pages=None, timeout=None):
		kwargs = {"cancelEvent": cancelEvent, "pages": pages}
		if timeout:
			kwargs["timeout"] = timeout
		self.session.signIn(clientId, port, openBrowser, **kwargs)
		try:
			me = self.client.me()
		except SpotifyError as e:
			if e.kind in ("forbidden", "auth"):
				# For example an app in development mode that does not list this
				# account in User Management: the session cannot be used.
				self.session.signOut()
				raise
			# The name is only a nicety: stay signed in without it.
			return self.session.user
		self.session.setUser(me)
		return self.session.user

	def signOut(self):
		self.library.forget()
		self.session.signOut()
