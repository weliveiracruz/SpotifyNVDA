# -*- coding: UTF-8 -*-
# SpotifyNVDA - background.py
# Starts the Spotify app in the background: minimized, without taking the focus
# and, optionally, with its window hidden (no taskbar button, no Alt+Tab).
# The sound comes from it as a Spotify Connect device; the user never sees it.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Spotify only allows playback through its own apps and SDKs, so the add-on
# drives the official desktop app instead of playing audio by itself.

import os
import sys
import threading
import time

PROCESS_NAME = "spotify.exe"
#: Same arguments Spotify uses when Windows starts it with the computer.
LAUNCH_ARGUMENTS = "--autostart --minimized"
SW_HIDE = 0
SW_SHOWMINNOACTIVE = 7
#: Seconds during which new Spotify windows are hidden after the launch.
HIDE_WINDOW_SECONDS = 25


def candidateExecutables(env=None):
	"""Spotify.exe of the installer from spotify.com, then the alias of the Microsoft Store version."""
	env = env if env is not None else os.environ
	out = []
	if env.get("APPDATA"):
		out.append(os.path.join(env["APPDATA"], "Spotify", "Spotify.exe"))
	if env.get("LOCALAPPDATA"):
		out.append(os.path.join(env["LOCALAPPDATA"], "Microsoft", "WindowsApps", "Spotify.exe"))
	return out


def findExecutable(exists=os.path.isfile, env=None):
	for path in candidateExecutables(env):
		if exists(path):
			return path
	return None


class Win32:
	"""The few Windows functions needed, through ctypes."""

	def __init__(self):
		import ctypes
		from ctypes import wintypes

		self.ctypes = ctypes
		self.wintypes = wintypes
		self.user32 = ctypes.WinDLL("user32", use_last_error=True)
		self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		self.shell32 = ctypes.WinDLL("shell32", use_last_error=True)
		self.user32.GetForegroundWindow.restype = wintypes.HWND
		self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
		self.user32.IsIconic.argtypes = [wintypes.HWND]
		self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
		self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
		self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
		self.kernel32.OpenProcess.restype = wintypes.HANDLE
		self.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
		self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
		self.kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
		self.shell32.ShellExecuteW.restype = ctypes.c_void_p
		self.shell32.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]

	def processName(self, pid):
		PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
		handle = self.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
		if not handle:
			return ""
		try:
			size = self.wintypes.DWORD(1024)
			buf = self.ctypes.create_unicode_buffer(size.value)
			if not self.kernel32.QueryFullProcessImageNameW(handle, 0, buf, self.ctypes.byref(size)):
				return ""
			return os.path.basename(buf.value).lower()
		finally:
			self.kernel32.CloseHandle(handle)

	def topWindows(self):
		"""Returns [(hwnd, pid)] of every top-level window."""
		found = []
		wintypes = self.wintypes

		@self.ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
		def callback(hwnd, lParam):
			pid = wintypes.DWORD()
			self.user32.GetWindowThreadProcessId(hwnd, self.ctypes.byref(pid))
			found.append((hwnd, pid.value))
			return True

		self.user32.EnumWindows(callback, 0)
		return found

	def isVisible(self, hwnd):
		return bool(self.user32.IsWindowVisible(hwnd))

	def isMinimized(self, hwnd):
		return bool(self.user32.IsIconic(hwnd))

	def hide(self, hwnd):
		self.user32.ShowWindow(hwnd, SW_HIDE)

	def foreground(self):
		return self.user32.GetForegroundWindow()

	def setForeground(self, hwnd):
		if hwnd:
			self.user32.SetForegroundWindow(hwnd)

	def shellExecute(self, path, arguments):
		result = self.shell32.ShellExecuteW(None, "open", path, arguments, None, SW_SHOWMINNOACTIVE)
		return (result or 0) > 32


class BackgroundLauncher:
	"""Opens the Spotify app without showing it. Only windows of a Spotify that
	the add-on started are hidden; a Spotify the user opened is never touched."""

	def __init__(self, win=None, findExe=findExecutable, startfile=None, sleep=time.sleep, clock=time.monotonic):
		self._win = win
		self.findExe = findExe
		self.startfile = startfile
		self.sleep = sleep
		self.clock = clock
		self._hider = None

	@property
	def win(self):
		if self._win is None:
			self._win = Win32()
		return self._win

	def spotifyWindows(self):
		names = {}
		out = []
		for hwnd, pid in self.win.topWindows():
			if pid not in names:
				names[pid] = self.win.processName(pid)
			if names[pid] == PROCESS_NAME:
				out.append(hwnd)
		return out

	def isRunning(self):
		return bool(self.spotifyWindows())

	def launch(self, hide=True):
		"""Starts Spotify in the background. Returns 'running', 'started' or 'unavailable'."""
		if sys.platform != "win32" and self._win is None:
			return "unavailable"
		if self.isRunning():
			return "running"
		previous = self.win.foreground()
		path = self.findExe()
		started = False
		if path:
			started = self.win.shellExecute(path, LAUNCH_ARGUMENTS)
		if not started:
			# Unknown installation: the registered protocol still opens it (with a window).
			try:
				(self.startfile or os.startfile)("spotify:")  # nosec B606 - fixed protocol, no shell
				started = True
			except (OSError, AttributeError):
				return "unavailable"
		if hide:
			self._hider = threading.Thread(target=self.keepHidden, args=(previous,), name="SpotifyNVDA-hide", daemon=True)
			self._hider.start()
		return "started"

	def keepHidden(self, previous, seconds=HIDE_WINDOW_SECONDS):
		"""Hides the windows of the Spotify just started and gives the focus back.
		Spotify creates its window a few seconds after starting, so it watches for a while."""
		end = self.clock() + seconds
		while self.clock() < end:
			windows = self.spotifyWindows()
			stolen = self.win.foreground() in windows
			for hwnd in windows:
				if self.win.isVisible(hwnd):
					self.win.hide(hwnd)
			if stolen and previous:
				self.win.setForeground(previous)
			self.sleep(0.25)
