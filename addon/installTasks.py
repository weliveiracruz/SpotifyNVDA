# -*- coding: UTF-8 -*-
# SpotifyNVDA - installTasks.py
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# NVDA runs onUninstall of the OLD version also when the add-on is UPDATED
# (the old copy is removed at the next restart). The saved Spotify session is
# only deleted on a real uninstall, so the user stays signed in after updates (RF-02).

import os

import globalVars

ADDON_NAME = "SpotifyNVDA"
# Must match credentials.FILE_NAME
_CREDENTIALS_FILE = "SpotifyNVDA-credentials.json"
_PENDING_INSTALL_SUFFIX = ".pendingInstall"


def _configPath():
	return globalVars.appArgs.configPath


def isUpdate():
	"""True when NVDA is removing the old version because a new one was installed."""
	cfg = _configPath()
	if os.path.isdir(os.path.join(cfg, "addons", ADDON_NAME + _PENDING_INSTALL_SUFFIX)):
		return True
	try:
		import addonHandler
		from addonStore.models.status import AddonStateCategory

		return ADDON_NAME in addonHandler.state[AddonStateCategory.PENDING_INSTALL]
	except Exception:
		return False


def onUninstall():
	"""Deletes the saved session and data only when the add-on is really uninstalled."""
	if isUpdate():
		return
	try:
		os.remove(os.path.join(_configPath(), _CREDENTIALS_FILE))
	except OSError:
		pass
