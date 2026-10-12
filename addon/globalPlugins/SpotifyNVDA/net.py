# -*- coding: UTF-8 -*-
# SpotifyNVDA - net.py
# HTTPS helpers shared by auth.py and api.py.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import socket
import ssl
import urllib.error
import urllib.request

from .errors import SpotifyError

#: Biggest response accepted from Spotify (playlists pages are a few hundred KB).
MAX_RESPONSE = 4 * 1024 * 1024
DEFAULT_TIMEOUT = 15


class _NoRedirect(urllib.request.HTTPRedirectHandler):
	"""Spotify never redirects API calls. Following a redirect could send the
	Authorization header to another host, so every redirect is an error."""

	def redirect_request(self, req, fp, code, msg, headers, newurl):
		return None


def buildOpener():
	context = ssl.create_default_context()
	# create_default_context already verifies certificates and host names;
	# being explicit protects against a future default change.
	context.check_hostname = True
	context.verify_mode = ssl.CERT_REQUIRED
	return urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), _NoRedirect())


def readLimited(resp, limit=MAX_RESPONSE):
	data = resp.read(limit + 1)
	if len(data) > limit:
		raise SpotifyError("tooLarge", "response bigger than %d bytes" % limit)
	return data


def openRequest(opener, request, timeout):
	"""Returns (status, headers, body). HTTP errors are returned, not raised;
	network problems raise SpotifyError."""
	try:
		resp = opener.open(request, timeout=timeout)
	except urllib.error.HTTPError as e:
		try:
			body = readLimited(e)
		except SpotifyError:
			raise
		except Exception:
			body = b""
		finally:
			e.close()
		return e.code, e.headers, body
	except (socket.timeout, TimeoutError) as e:
		raise SpotifyError("timeout", type(e).__name__)
	except urllib.error.URLError as e:
		if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)):
			raise SpotifyError("timeout", "connect")
		raise SpotifyError("network", type(getattr(e, "reason", e)).__name__)
	except OSError as e:
		raise SpotifyError("network", type(e).__name__)
	try:
		try:
			body = readLimited(resp)
		except (socket.timeout, TimeoutError):
			raise SpotifyError("timeout", "read")
		return resp.status, resp.headers, body
	finally:
		resp.close()
