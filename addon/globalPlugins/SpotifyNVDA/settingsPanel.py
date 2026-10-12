# -*- coding: UTF-8 -*-
# SpotifyNVDA - settingsPanel.py
# NVDA settings > Spotify.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import addonHandler
import config
import gui
import wx
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel

from .auth import isValidClientId, normalizeClientId, redirectUri
from .service import DEVELOPER_DASHBOARD_URL, openUrl

addonHandler.initTranslation()

CONFIG_SECTION = "SpotifyNVDA"


class SpotifySettingsPanel(SettingsPanel):
	# Translators: name of the add-on category in NVDA settings.
	title = _("Spotify")
	#: Set by the global plugin (gives access to the session for Sign out).
	plugin = None

	def makeSettings(self, settingsSizer):
		conf = config.conf[CONFIG_SECTION]
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		# Translators: label of the Client ID field in the settings.
		self.clientIdEdit = sHelper.addLabeledControl(_("Spotify &Client ID:"), wx.TextCtrl, size=(320, -1))
		self.clientIdEdit.SetValue(conf["clientId"])
		self.clientIdEdit.SetMaxLength(64)
		self.portSpin = sHelper.addLabeledControl(
			# Translators: label of the port used to come back from the Spotify login page.
			_("Redirect &port:"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=1024,
			max=65535,
			initial=int(conf["port"]),
		)
		self.redirectEdit = sHelper.addLabeledControl(
			# Translators: label of the read-only field with the address to register in the Spotify dashboard.
			_("Redirect &URI to register in the Spotify dashboard:"),
			wx.TextCtrl,
			style=wx.TE_READONLY,
			size=(320, -1),
		)
		self.redirectEdit.SetValue(redirectUri(self.portSpin.GetValue()))
		self.portSpin.Bind(wx.EVT_SPINCTRL, self.onPort)
		self.portSpin.Bind(wx.EVT_TEXT, self.onPort)
		self.volumeSpin = sHelper.addLabeledControl(
			# Translators: label of the volume step setting.
			_("&Volume step (%):"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=1,
			max=50,
			initial=int(conf["volumeStep"]),
		)
		self.launchCheck = sHelper.addItem(wx.CheckBox(
			self,
			# Translators: check box of the settings.
			label=_("Open the Spotify &app when no device is available"),
		))
		self.launchCheck.SetValue(bool(conf["launchApp"]))
		self.hideCheck = sHelper.addItem(wx.CheckBox(
			self,
			# Translators: check box of the settings: the Spotify app plays in the background, without a window.
			label=_("Keep the Spotify app &hidden (plays in the background, without a window)"),
		))
		self.hideCheck.SetValue(bool(conf["hideApp"]))
		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: button that opens the Spotify developer dashboard in the browser.
		self.dashboardButton = buttons.addButton(self, label=_("Open the Spotify &developer dashboard"))
		# Translators: button of the settings that signs out of Spotify.
		self.signOutButton = buttons.addButton(self, label=_("Sign &out of Spotify"))
		sHelper.addItem(buttons)
		self.dashboardButton.Bind(wx.EVT_BUTTON, self.onDashboard)
		self.signOutButton.Bind(wx.EVT_BUTTON, self.onSignOut)
		self.signOutButton.Enable(bool(self.plugin and self.plugin.service.signedIn))

	def onPort(self, evt):
		self.redirectEdit.SetValue(redirectUri(self.portSpin.GetValue()))
		evt.Skip()

	def onDashboard(self, evt):
		try:
			openUrl(DEVELOPER_DASHBOARD_URL)
		except OSError:
			# Translators: title of a message box.
			gui.messageBox(DEVELOPER_DASHBOARD_URL, _("Spotify"), wx.OK, self)

	def onSignOut(self, evt):
		if not self.plugin:
			return
		if self.plugin.confirmSignOut(self):
			self.signOutButton.Enable(False)
			self.clientIdEdit.SetFocus()

	def isValid(self):
		clientId = normalizeClientId(self.clientIdEdit.GetValue())
		if clientId and not isValidClientId(clientId):
			gui.messageBox(
				# Translators: message when the Client ID typed in the settings has the wrong format.
				_("The Client ID has 32 letters and numbers. Copy it from your app in the Spotify developer dashboard."),
				# Translators: title of a message box.
				_("Spotify"),
				wx.OK | wx.ICON_WARNING,
				self,
			)
			self.clientIdEdit.SetFocus()
			return False
		return True

	def onSave(self):
		conf = config.conf[CONFIG_SECTION]
		conf["clientId"] = normalizeClientId(self.clientIdEdit.GetValue())
		conf["port"] = int(self.portSpin.GetValue())
		conf["volumeStep"] = int(self.volumeSpin.GetValue())
		conf["launchApp"] = self.launchCheck.GetValue()
		conf["hideApp"] = self.hideCheck.GetValue()
