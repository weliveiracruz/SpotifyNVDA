# -*- coding: UTF-8 -*-
"""Vulnerability tests (SEG-xx of docs/SDD-TESTES.md): OAuth, loopback listener,
tokens at rest and in logs, TLS, timeouts, redirects, injection, static analysis.

Run:  python tests/test_security.py   (bandit must be installed: pip install bandit)"""

import ast
import json
import os
import re
import socket
import subprocess  # nosec B404 - runs bandit in the test only
import sys
import tempfile
import threading
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _guiapp import MOCK, RECORD, SpotifyNVDA, config, mainDialog, newPlugin, pump, signInThroughWindow, wx  # noqa: E402
import _helpers  # noqa: E402
import mock_spotify  # noqa: E402
import nvda_stubs  # noqa: E402
from _results import Recorder  # noqa: E402

R = Recorder("security (test_security)")
core = _helpers.loadCore()
BASE = _helpers.startMock()
ADDON = os.path.join(_helpers.ROOT, "addon")
SpotifyError = core.errors.SpotifyError


def addonSources():
	out = {}
	for folder, dirs, files in os.walk(ADDON):
		dirs[:] = [d for d in dirs if d != "__pycache__"]
		for f in files:
			if f.endswith(".py"):
				p = os.path.join(folder, f)
				with open(p, encoding="utf-8") as fh:
					out[os.path.relpath(p, _helpers.ROOT)] = fh.read()
	return out


def allTokens():
	with MOCK.lock:
		return [t for t in list(MOCK.accessTokens) + list(MOCK.refreshTokens) if t]


def rawGet(port, request):
	s = socket.create_connection(("127.0.0.1", port), timeout=5)
	try:
		s.sendall(request)
		data = b""
		while True:
			chunk = s.recv(65536)
			if not chunk:
				break
			data += chunk
		return data.decode("utf-8", "replace")
	finally:
		s.close()


def run():
	sources = addonSources()

	# -- SEG-01 tokens at rest ---------------------------------------------------------------
	plugin = newPlugin()
	dlg = signInThroughWindow(plugin)
	path = plugin.service.store.path
	with open(path, encoding="utf-8") as f:
		raw = f.read()
	tokens = allTokens()
	R.check("SEG-01 session file exists after signing in", os.path.isfile(path))
	R.check("SEG-01 no access or refresh token in clear text in the file", tokens and not any(t in raw for t in tokens))
	R.check("SEG-01 no user name in clear text in the file", "Wellington" not in raw)
	if sys.platform == "win32":
		R.check("SEG-01 Windows DPAPI is the codec in use", type(plugin.service.store._codec).__name__ == "_DPAPI")
		blob = json.loads(raw)["session"]
		import base64

		plainTry = core.credentials.CredentialStore(os.path.dirname(path), codec=core.credentials._PlainCodec())
		R.check("SEG-01 file cannot be read without DPAPI (another user/computer)", plainTry.get("session") is None and len(base64.b64decode(blob)) > 100)
	confText = json.dumps(dict(config.conf["SpotifyNVDA"]))
	R.check("SEG-01 nothing secret in nvda.ini", set(config.conf.spec["SpotifyNVDA"]) == {"clientId", "port", "volumeStep", "launchApp", "hideApp"} and not any(t in confText for t in tokens))

	# -- SEG-02 tokens never in log, speech or messages ---------------------------------------
	MOCK.fail("GET", "/v1/me/player", 500, {"error": {"status": 500, "message": "boom"}})
	plugin.script_playPause(None)
	MOCK.expireAll()
	plugin.script_nowPlaying(None)
	MOCK.fail("GET", "/v1/search", 400, {"error": {"status": 400, "message": "x" * 5000}})
	dlg.searchEdit.SetValue("ipanema")
	dlg.onSearch(None)
	pump(timeout=1.5)
	tokens = allTokens()
	texts = nvda_stubs.spoken() + RECORD["log"] + RECORD["messageBoxes"]
	leaked = [t for t in tokens if any(t in x for x in texts)]
	R.check("SEG-02 tokens never in speech, log or message boxes", not leaked, leaked[:2])
	codes = [r["query"].get("code") for r in MOCK.requests]
	R.check("SEG-02 authorization address (with the code) never logged", not any("callback?" in x or "code=" in x for x in RECORD["log"]))
	R.check("SEG-18 long error details are cut", all(len(s) < 400 for s in nvda_stubs.spoken()))
	try:
		raise SpotifyError("badRequest", "y" * 10000)
	except SpotifyError as e:
		R.check("SEG-18 error detail limited to 200 characters", len(e.detail) == 200)

	# -- SEG-03 TLS / SEG-05 HTTPS -------------------------------------------------------------
	opener = core.net.buildOpener()
	https = [h for h in opener.handlers if h.__class__.__name__ == "HTTPSHandler"]
	ctx = https[0]._context if https else None
	R.check("SEG-03 certificate and host name verification on", ctx is not None and ctx.check_hostname and ctx.verify_mode == 2)
	bad = [p for p, s in sources.items() if re.search(r"_create_unverified_context|CERT_NONE|check_hostname\s*=\s*False|verify\s*=\s*False", s)]
	R.check("SEG-03 no code that turns certificate checks off", not bad, bad)
	urls = [core.auth.AUTHORIZE_URL, core.auth.TOKEN_URL, core.api.API_BASE, core.service.DEVELOPER_DASHBOARD_URL, core.service.ACCOUNT_APPS_URL]
	R.check("SEG-05 every Spotify address is HTTPS", all(u.startswith("https://") for u in urls), urls)
	R.check("SEG-05 the hosts are Spotify's", all(urllib.parse.urlsplit(u).hostname.endswith("spotify.com") for u in urls))

	# -- SEG-04 timeouts ----------------------------------------------------------------------
	missing = []
	for p, s in sources.items():
		for node in ast.walk(ast.parse(s)):
			if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("open", "urlopen") and isinstance(node.func.value, ast.Name) and node.func.value.id in ("opener", "urllib", "request"):
				if not any(k.arg == "timeout" for k in node.keywords):
					missing.append("%s:%d" % (p, node.lineno))
	R.check("SEG-04 every HTTP request has a timeout", not missing, missing)
	R.check("SEG-04 urlopen without our opener is never used", not any("urlopen(" in s for s in sources.values()))
	R.check("SEG-04 client and OAuth default timeouts are short", core.net.DEFAULT_TIMEOUT <= 20)

	# -- SEG-06 redirects / SEG-07 size ----------------------------------------------------------
	client = plugin.service.client
	saved = client.baseUrl
	client.baseUrl = BASE
	before = len(MOCK.requests)
	try:
		client.request("GET", "/redirect-me")
		R.check("SEG-06 redirects are not followed", False, "no error")
	except SpotifyError:
		R.check("SEG-06 redirects are not followed (token never sent elsewhere)", True)
	R.check("SEG-06 nothing requested after the redirect", len(MOCK.requests) == before + 1)
	try:
		client.request("GET", "/huge")
		R.check("SEG-07 giant answer refused", False, "accepted")
	except SpotifyError as e:
		R.check("SEG-07 giant answer refused without reading it all", e.kind == "tooLarge", e.kind)
	client.baseUrl = saved

	# -- SEG-08 injection ---------------------------------------------------------------------
	bads = []
	for value in ("../me", "abc/def", "abc?x=1", "abc#x", "", "a" * 65, "abç"):
		try:
			core.api.checkId(value)
			bads.append(value)
		except SpotifyError:
			pass
	R.check("SEG-08 IDs with path characters are refused", not bads, bads)
	for call in (
		lambda: client.addToPlaylist("p0000001/../../me", ["spotify:track:t0000001"]),
		lambda: client.play(contextUri="spotify:playlist:abc/../../x"),
		lambda: client.play(deviceId="dev/../x"),
		lambda: client.setVolume(10, deviceId="a?b=c"),
	):
		before = len(MOCK.requests)
		try:
			call()
			bads.append("accepted")
		except SpotifyError as e:
			if e.kind != "badRequest" or len(MOCK.requests) != before:
				bads.append(e.kind)
	R.check("SEG-08 bad IDs never reach the network", not bads, bads)
	R.check("SEG-08 only track URIs are played or added", client.play.__self__ is client and not core.api.isTrackUri("spotify:track:x/../y") and not core.api.isTrackUri("https://evil/x"))
	client.search("a&type=playlist&limit=50 #?/", "track")
	q = [r for r in MOCK.requests if r["path"] == "/v1/search"][-1]["query"]
	R.check("SEG-08 search text cannot change the query", q["type"] == "track" and q["limit"] == "10" and q["q"] == "a&type=playlist&limit=50 #?/", q)

	# -- SEG-09 OAuth -------------------------------------------------------------------------
	browser = mock_spotify.FakeBrowser(BASE)
	svc = _helpers.makeService(core)
	svc.signIn(mock_spotify.CLIENT_ID, _helpers.freePort(), browser, timeout=10)
	params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(browser.urls[0]).query))
	tokenReq = [r for r in MOCK.requests if r["path"] == "/api/token"][-1]
	form = dict(urllib.parse.parse_qsl(tokenReq["body"].decode("ascii")))
	R.check("SEG-09 PKCE with S256", params["code_challenge_method"] == "S256" and len(params["code_challenge"]) == 43)
	R.check("SEG-09 verifier is long and random (64 characters)", len(form["code_verifier"]) == 64)
	R.check("SEG-09 public client: no client secret anywhere", "client_secret" not in form and not any(re.search(r"client_secret|clientSecret", s) for s in sources.values()))
	R.check("SEG-09 no Authorization header sent to the accounts service", "Authorization" not in tokenReq["headers"])
	states = {core.auth.randomToken() for _ in range(200)}
	R.check("SEG-09 state is random (32 bytes)", len(states) == 200 and all(len(s) == 43 for s in states))
	R.check("SEG-09 redirect only to 127.0.0.1/callback", re.fullmatch(r"http://127\.0\.0\.1:\d+/callback", params["redirect_uri"]) is not None)

	svc2 = _helpers.makeService(core)
	evil = mock_spotify.FakeBrowser(BASE, mode="wrongState")
	try:
		svc2.signIn(mock_spotify.CLIENT_ID, _helpers.freePort(), evil, timeout=1.5)
		R.check("SEG-09 answer with another state refused (CSRF)", False, "accepted")
	except SpotifyError as e:
		R.check("SEG-09 answer with another state refused (CSRF)", e.kind == "timeout" and evil.callbackStatus and evil.callbackStatus[0][0] == 400 and not svc2.signedIn, (e.kind, evil.callbackStatus))
	R.check("SEG-09 state compared in constant time", core.auth.constantTimeEqual("abc", "abc") and not core.auth.constantTimeEqual("abc", "abd") and not core.auth.constantTimeEqual("abc", "abcd"))

	# loopback listener
	port = _helpers.freePort()
	state = core.auth.randomToken()
	receiver = core.auth.LoopbackReceiver(state, port)
	try:
		R.check("SEG-10 listener only on 127.0.0.1", receiver.address[0] == "127.0.0.1")
		if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
			intruder = socket.socket()
			intruder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			try:
				intruder.bind(("127.0.0.1", port))
				hijacked = True
			except OSError:
				hijacked = False
			finally:
				intruder.close()
			R.check("SEG-10 no other program can listen on the same port", not hijacked)
		answer = rawGet(port, b"GET /other?code=x&state=" + state.encode() + b" HTTP/1.1\r\nHost: x\r\n\r\n")
		R.check("SEG-10 other paths get 404", answer.startswith("HTTP/1.1 404") and receiver.result is None)
		answer = rawGet(port, b"POST /callback?code=x&state=" + state.encode() + b" HTTP/1.1\r\nHost: x\r\n\r\n")
		R.check("SEG-10 POST is refused", answer.startswith("HTTP/1.1 405") and receiver.result is None)
		answer = rawGet(port, b"GET /callback?code=x&state=" + state.encode() + b" HTTP/1.1\r\n" + b"X: " + b"a" * 20000 + b"\r\n\r\n")
		R.check("SEG-10 oversized request refused", answer.startswith("HTTP/1.1 400") and receiver.result is None)
		answer = rawGet(port, b"GET /callback?error=%3Cscript%3Ealert(1)%3C/script%3E&state=" + state.encode() + b" HTTP/1.1\r\n\r\n")
		R.check("SEG-11 nothing from the address is echoed in the page (no XSS)", "<script>" not in answer and "alert(1)" not in answer)
		R.check("SEG-11 page sent with no-store, CSP and nosniff", "Cache-Control: no-store" in answer and "Content-Security-Policy: default-src 'none'" in answer and "X-Content-Type-Options: nosniff" in answer)
	finally:
		receiver.close()
	evilPages = core.auth.LoopbackReceiver("s", _helpers.freePort(), {"done": "<img src=x onerror=alert(1)>"})
	try:
		page = rawGet(evilPages.port, b"GET /callback?code=1&state=s HTTP/1.1\r\n\r\n")
	finally:
		evilPages.close()
	R.check("SEG-11 page texts are HTML-escaped", "<img" not in page and "&lt;img" in page)
	try:
		core.auth.LoopbackReceiver("s", port).close()
		R.check("SEG-10 port is released after the sign-in", True)
	except SpotifyError:
		R.check("SEG-10 port is released after the sign-in", False)

	# -- SEG-12 sign out and uninstall ------------------------------------------------------------
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	plugin.confirmSignOut()
	R.check("SEG-12 sign out deletes the session file", not os.path.exists(path))
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.OK
	import importlib.util

	spec = importlib.util.spec_from_file_location("installTasks", os.path.join(ADDON, "installTasks.py"))
	installTasks = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(installTasks)
	import globalVars

	cfg = tempfile.mkdtemp()
	globalVars.appArgs.configPath = cfg
	cred = os.path.join(cfg, core.credentials.FILE_NAME)
	R.check("SEG-12 installTasks uses the same file name", installTasks._CREDENTIALS_FILE == core.credentials.FILE_NAME)
	open(cred, "w").close()
	os.makedirs(os.path.join(cfg, "addons", "SpotifyNVDA.pendingInstall"))
	installTasks.onUninstall()
	R.check("SEG-12 update keeps the session (stay signed in)", os.path.exists(cred))
	os.rmdir(os.path.join(cfg, "addons", "SpotifyNVDA.pendingInstall"))
	installTasks.onUninstall()
	R.check("SEG-12 real uninstall deletes the session", not os.path.exists(cred))

	# -- SEG-13 scopes --------------------------------------------------------------------------
	expected = {"user-read-private", "playlist-read-private", "playlist-read-collaborative", "playlist-modify-private", "playlist-modify-public", "user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing", "user-read-recently-played"}
	R.check("SEG-13 only the scopes the add-on uses", set(core.auth.SCOPES) == expected, core.auth.SCOPES)

	# -- SEG-14 browser addresses ------------------------------------------------------------------
	refused = 0
	for url in ("http://accounts.spotify.com/authorize?x", "https://accounts.spotify.com.evil.com/authorize?x", "javascript:alert(1)", "file:///c:/windows", "https://evil.com/?https://developer.spotify.com/dashboard", "spotify:"):
		try:
			core.service.openUrl(url)
		except ValueError:
			refused += 1
		except OSError:
			pass
	R.check("SEG-14 browser only opens fixed Spotify HTTPS addresses", refused == 6, refused)

	# -- SEG-19 background launcher ---------------------------------------------------------------
	bg = sources[os.path.join("addon", "globalPlugins", "SpotifyNVDA", "background.py")]
	tree = ast.parse(bg)
	calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("shellExecute", "ShellExecuteW", "startfile")]
	argsOk = all(
		(n.func.attr == "shellExecute" and isinstance(n.args[1], ast.Name) and n.args[1].id == "LAUNCH_ARGUMENTS")
		or (n.func.attr == "ShellExecuteW")
		or (n.func.attr == "startfile")
		for n in calls
	)
	R.check("SEG-19 the launcher only runs Spotify with fixed arguments", argsOk and core.background.LAUNCH_ARGUMENTS == "--autostart --minimized" and all(p.lower().endswith("spotify.exe") for p in core.background.candidateExecutables({"APPDATA": "a", "LOCALAPPDATA": "b"})))
	R.check("SEG-19 only windows of spotify.exe are hidden", core.background.PROCESS_NAME == "spotify.exe" and "names[pid] == PROCESS_NAME" in bg)
	R.check("SEG-19 a Spotify the user opened is never touched", "if self.isRunning():\n\t\t\treturn \"running\"" in bg)

	# -- SEG-20 playlist changes (1.2.0) ------------------------------------------------------------
	before = len(MOCK.requests)
	refused = 0
	for call in (
		lambda: client.deletePlaylist("p0000001/../../me"),
		lambda: client.deletePlaylist("p0000001,spotify:playlist:p0000002"),
		lambda: client.playlistItems("../me/playlists"),
		lambda: client.reorder("p1?x=1", 0, 1),
	):
		try:
			call()
		except SpotifyError as e:
			refused += e.kind == "badRequest"
	R.check("SEG-20 playlist IDs checked before deleting, reading or reordering", refused == 4 and len(MOCK.requests) == before, refused)
	dialogSource = sources[os.path.join("addon", "globalPlugins", "SpotifyNVDA", "mainDialog.py")]
	R.check("SEG-20 deleting a playlist and saving an order always ask first", dialogSource.count("wx.YES_NO | wx.NO_DEFAULT") >= 2 and "confirmDelete" in dialogSource and "confirmSaveOrder" in dialogSource)
	R.check("SEG-20 saving an order never removes songs (only moves)", "range_start" in sources[os.path.join("addon", "globalPlugins", "SpotifyNVDA", "api.py")] and '"uris"' not in sources[os.path.join("addon", "globalPlugins", "SpotifyNVDA", "library.py")])
	R.check("SEG-13 no new OAuth scope for deleting or sorting", len(core.auth.SCOPES) == 9)

	# -- SEG-15 secure screens -------------------------------------------------------------------
	import globalPluginHandler

	globalVars.appArgs.secure = True
	R.check("SEG-15 add-on disabled on secure screens", SpotifyNVDA.disableInSecureMode(SpotifyNVDA.GlobalPlugin) is globalPluginHandler.GlobalPlugin)
	globalVars.appArgs.secure = False

	# -- SEG-16 dangerous functions / dependencies ------------------------------------------------------
	pattern = re.compile(r"(?<![\w.])(eval|exec|compile)\s*\(|\bpickle\b|\bmarshal\b|\bsubprocess\b|os\.system|os\.popen|shell\s*=\s*True|__import__|yaml\.load|ctypes\.CDLL\(.*(http|\\\\)")
	bad = ["%s: %s" % (p, m.group(0)) for p, s in sources.items() for m in pattern.finditer(s)]
	R.check("SEG-16 no eval, exec, pickle, subprocess or shell in the add-on", not bad, bad)
	allowed = {"base64", "calendar", "ctypes", "unicodedata", "hashlib", "html", "json", "os", "queue", "re", "socket", "ssl", "sys", "threading", "time", "urllib",
		"addonHandler", "config", "globalPluginHandler", "globalVars", "gui", "queueHandler", "ui", "wx", "logHandler", "scriptHandler", "addonStore"}
	imported = set()
	for p, s in sources.items():
		for node in ast.walk(ast.parse(s)):
			if isinstance(node, ast.Import):
				imported.update(a.name.split(".")[0] for a in node.names)
			elif isinstance(node, ast.ImportFrom) and node.level == 0:
				imported.add(node.module.split(".")[0])
	R.check("SEG-16 no third-party dependency", imported <= allowed, sorted(imported - allowed))

	# -- SEG-17 static analysis (bandit) -------------------------------------------------------------
	try:
		proc = subprocess.run([sys.executable, "-m", "bandit", "-q", "-r", ADDON, "-f", "json"], capture_output=True, text=True, timeout=300)  # nosec B603
		report = json.loads(proc.stdout or "{}")
		issues = [r for r in report.get("results", []) if r["issue_severity"] in ("MEDIUM", "HIGH")]
		R.check("SEG-17 bandit: no medium or high problems", "results" in report and not issues, [(i["test_id"], i["filename"], i["line_number"]) for i in issues] or proc.stderr[-300:])
		low = [r for r in report.get("results", [])]
		R.check("SEG-17 bandit: low findings are only the justified ones", all(i["test_id"] in ("B404", "B603", "B606", "B607", "B110", "B311") for i in low), [(i["test_id"], i["filename"], i["line_number"]) for i in low])
	except Exception as e:  # bandit missing
		R.check("SEG-17 bandit installed and ran", False, repr(e))


if __name__ == "__main__":
	try:
		run()
	except Exception:
		import traceback

		traceback.print_exc()
		R.check("suite finished without crashing", False, traceback.format_exc()[-500:])
	sys.exit(R.finish())
