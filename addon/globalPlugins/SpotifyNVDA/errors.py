# -*- coding: UTF-8 -*-
# SpotifyNVDA - errors.py
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

#: Biggest detail kept in an error (it may be spoken or logged).
MAX_DETAIL = 200

KINDS = frozenset((
	"notSignedIn",
	"noClientId",
	"invalidClientId",
	"auth",
	"denied",
	"cancelled",
	"portInUse",
	"timeout",
	"network",
	"rateLimited",
	"premiumRequired",
	"noDevice",
	"restricted",
	"forbidden",
	"notFound",
	"badRequest",
	"server",
	"badResponse",
	"tooLarge",
	"nothingToResume",
	"tooManyChanges",
))


class SpotifyError(Exception):
	"""Every failure of the add-on core. `kind` is one of KINDS; the user
	interface turns it into a short translated sentence (messages.py).
	The detail never carries tokens: it comes from Spotify error messages."""

	def __init__(self, kind, detail="", status=None, retryAfter=None):
		if kind not in KINDS:
			kind = "server"
		detail = str(detail or "")[:MAX_DETAIL]
		super().__init__("%s: %s" % (kind, detail) if detail else kind)
		self.kind = kind
		self.detail = detail
		self.status = status
		self.retryAfter = retryAfter
