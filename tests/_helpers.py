# -*- coding: UTF-8 -*-
"""Shared helpers: loads the add-on core without NVDA, starts the Spotify mock
and builds a SpotifyService pointed at it."""

import importlib
import os
import socket
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
PKG_DIR = os.path.join(ROOT, "addon", "globalPlugins", "SpotifyNVDA")
sys.path.insert(0, HERE)

import mock_spotify  # noqa: E402

_server = None
BASE = None


def startMock():
	global _server, BASE
	if _server is None:
		_server, BASE = mock_spotify.start()
	return BASE


def loadCore():
	"""Imports the add-on modules as package 'SpotifyNVDA' without running its
	__init__ (which needs NVDA). Returns a namespace with the modules."""
	if "SpotifyNVDA" not in sys.modules:
		pkg = types.ModuleType("SpotifyNVDA")
		pkg.__path__ = [PKG_DIR]
		sys.modules["SpotifyNVDA"] = pkg
	ns = types.SimpleNamespace()
	for name in ("errors", "net", "credentials", "auth", "api", "player", "service", "background", "library"):
		setattr(ns, name, importlib.import_module("SpotifyNVDA." + name))
	return ns


def freePort():
	s = socket.socket()
	s.bind(("127.0.0.1", 0))
	port = s.getsockname()[1]
	s.close()
	return port


def makeService(core, configPath=None, launchApp=None, store=None):
	base = startMock()
	configPath = configPath or tempfile.mkdtemp(prefix="spotifynvda-test-")
	oauth = core.auth.OAuthClient(authorizeUrl=base + "/authorize", tokenUrl=base + "/api/token")
	return core.service.SpotifyService(
		configPath,
		store=store,
		oauth=oauth,
		baseUrl=base + "/v1",
		launchApp=launchApp or (lambda: None),
		sleep=lambda s: None,
	)


def signIn(svc, mode="agree", port=None, timeout=10, cancelEvent=None):
	browser = mock_spotify.FakeBrowser(BASE, mode=mode)
	user = svc.signIn(mock_spotify.CLIENT_ID, port or freePort(), browser, cancelEvent=cancelEvent, timeout=timeout)
	return user, browser
