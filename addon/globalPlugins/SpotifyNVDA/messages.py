# -*- coding: UTF-8 -*-
# SpotifyNVDA - messages.py
# Translated sentences spoken or shown by the add-on.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import addonHandler

addonHandler.initTranslation()


def errorMessage(err):
	"""Short sentence for a SpotifyError (RA-05). Never includes tokens."""
	kind = getattr(err, "kind", "server")
	detail = getattr(err, "detail", "") or ""
	if kind == "notSignedIn":
		# Translators: spoken when a command needs a Spotify account.
		return _("You are not signed in to Spotify. Press NVDA+Alt+P and choose Sign in with Spotify.")
	if kind == "noClientId":
		# Translators: spoken when the Client ID was not configured.
		return _("Enter your Spotify Client ID in NVDA settings, Spotify category, before signing in.")
	if kind == "invalidClientId":
		# Translators: spoken when Spotify does not accept the Client ID.
		return _("Spotify did not accept the Client ID. Check it in NVDA settings, Spotify category.")
	if kind == "auth":
		# Translators: spoken when the saved Spotify session can no longer be used.
		return _("Your Spotify session has ended. Sign in again.")
	if kind == "denied":
		# Translators: spoken when the user did not allow the add-on on the Spotify page.
		return _("You did not authorize SpotifyNVDA on the Spotify page.")
	if kind == "cancelled":
		# Translators: spoken when the sign-in was cancelled.
		return _("Sign-in cancelled.")
	if kind == "portInUse":
		# Translators: spoken when the sign-in port is used by another program. {port} is a number.
		return _("Port {port} is already in use by another program. Choose another port in NVDA settings, Spotify category, and register the new redirect address in the Spotify dashboard.").format(port=detail)
	if kind == "timeout":
		# Translators: spoken when Spotify takes too long to answer.
		return _("Spotify took too long to answer. Try again.")
	if kind == "network":
		# Translators: spoken when there is no internet connection.
		return _("Could not connect to Spotify. Check your internet connection.")
	if kind == "rateLimited":
		# Translators: spoken when Spotify asks to slow down.
		return _("Spotify asked to wait a little. Try again in a few seconds.")
	if kind == "premiumRequired":
		# Translators: spoken when playback control needs a paid account.
		return _("Playing music from here requires Spotify Premium.")
	if kind == "noDevice":
		# Translators: spoken when there is no Spotify device to play on.
		return _("No Spotify device available. Open the Spotify app on this computer or on another device and try again.")
	if kind == "restricted":
		# Translators: spoken when the device does not allow the command (for example volume).
		return _("This device does not allow this action.")
	if kind == "forbidden":
		if "regist" in detail.lower():
			# Translators: spoken when the Spotify app is in development mode and the account is not in its user list.
			return _("This Spotify account is not registered in your Spotify app. In the Spotify dashboard, add your e-mail in User Management.")
		# Translators: spoken when Spotify refuses an action.
		return _("Spotify did not allow this action.")
	if kind == "notFound":
		# Translators: spoken when a playlist or song no longer exists.
		return _("Spotify could not find this item.")
	if kind == "nothingToResume":
		# Translators: spoken when there is no song to continue.
		return _("No recently played song was found.")
	if kind == "tooManyChanges":
		# Translators: spoken when a new order would need too many changes on Spotify.
		return _("This playlist is too big to save the new order on Spotify. The order was kept only in this window.")
	if kind == "tooLarge":
		# Translators: spoken when Spotify sends an answer that is too big.
		return _("Spotify sent an answer that is too big.")
	# Translators: spoken for any other Spotify failure.
	return _("Spotify had a problem. Try again later.")


def trackText(track):
	if not track:
		return ""
	if track.get("artists"):
		# Translators: a song and its artists, for example "Garota de Ipanema, by Tom Jobim".
		return _("{name}, by {artists}").format(name=track.get("name") or "", artists=track["artists"])
	return track.get("name") or ""


def itemText(item):
	"""Text of a line of the results list."""
	if item.get("kind") == "playlist":
		if item.get("total") is not None:
			# Translators: a playlist in the results list. {count} is the number of songs.
			return _("{name} - {owner}, {count} songs").format(name=item["name"], owner=item.get("owner") or "", count=item["total"])
		# Translators: a playlist in the results list, without the number of songs.
		return _("{name} - {owner}").format(name=item["name"], owner=item.get("owner") or "")
	text = trackText(item)
	if item.get("album"):
		# Translators: a song in the results list followed by its album.
		text = _("{song}, album {album}").format(song=text, album=item["album"])
	return text


def nowPlayingText(info):
	if not info or not info.get("track"):
		# Translators: spoken when nothing is playing.
		return _("Nothing is playing on Spotify.")
	if info.get("isPlaying"):
		# Translators: spoken by the "what is playing" command. {track} is "song, by artist".
		return _("Playing: {track}").format(track=trackText(info["track"]))
	# Translators: spoken by the "what is playing" command when paused.
	return _("Paused: {track}").format(track=trackText(info["track"]))


def resumedText(track):
	# Translators: spoken when the last song is continued. {track} is "song, by artist".
	return _("Continuing: {track}").format(track=trackText(track))


def playingItemText(item):
	# Translators: spoken when a song or playlist starts. {name} is its name.
	return _("Playing {name}").format(name=item.get("name") or "")


def volumeText(volume):
	# Translators: spoken after changing the volume. {volume} is a number from 0 to 100.
	return _("Volume {volume}%").format(volume=volume)


def signedInText(user):
	name = (user or {}).get("name")
	if name:
		# Translators: spoken after signing in. {name} is the Spotify user name.
		return _("Signed in to Spotify as {name}").format(name=name)
	# Translators: spoken after signing in when the name is unknown.
	return _("Signed in to Spotify")


def statusText(signedIn, user):
	if not signedIn:
		# Translators: status line of the Spotify window when there is no account.
		return _("Not signed in. Choose Sign in with Spotify.")
	name = (user or {}).get("name") or ""
	product = (user or {}).get("product") or ""
	if product == "premium":
		# Translators: status line of the Spotify window. {name} is the user name.
		return _("Signed in as {name} (Premium)").format(name=name)
	if product:
		# Translators: status line of the Spotify window for an account without Premium.
		return _("Signed in as {name} (free account: playback control needs Premium)").format(name=name)
	# Translators: status line of the Spotify window when the plan is unknown.
	return _("Signed in as {name}").format(name=name)


# Simple sentences (functions, so the translation is ready when they are used).

def paused():
	# Translators: spoken after pausing.
	return _("Paused")


def playing():
	# Translators: spoken after resuming playback.
	return _("Playing")


def signedOut():
	# Translators: spoken after signing out.
	return _("Signed out of Spotify. Your session and saved data were deleted from this computer.")


def waitingBrowser():
	# Translators: status line while the Spotify login page is open in the browser.
	return _("Waiting for the sign-in in the browser. Sign in on the Spotify page and come back here.")


def loading():
	# Translators: spoken while the list is loading.
	return _("Loading…")


def noResults():
	# Translators: spoken when the search finds nothing.
	return _("Nothing found.")


def playlistCreated(name):
	# Translators: spoken after creating a playlist. {name} is its name.
	return _("Playlist {name} created").format(name=name)


def addedToPlaylist(song, playlist):
	# Translators: spoken after adding a song to a playlist.
	return _("{song} added to {playlist}").format(song=song, playlist=playlist)


def callbackPages():
	"""Texts of the page shown in the browser after the Spotify login (RA-11)."""
	return {
		# Translators: language code of the page shown in the browser after signing in (en, pt-BR...).
		"lang": _("en"),
		"title": "SpotifyNVDA",
		# Translators: page shown in the browser when the sign-in worked.
		"done": _("Signed in to Spotify. You can close this tab and go back to NVDA."),
		# Translators: page shown in the browser when the sign-in failed.
		"error": _("Sign-in was not completed. You can close this tab and go back to NVDA."),
		# Translators: page shown for an address that does not belong to the current sign-in.
		"invalid": _("This address does not belong to the current sign-in."),
	}


# Songs inside the playlists (1.2.0)

def entryText(entry):
	"""Text of a song inside a playlist in the tree."""
	text = itemText(entry)
	if entry.get("playable") is False:
		# Translators: a song of a playlist that cannot be played (local file or removed from Spotify).
		text = _("{song} (not available to play)").format(song=text)
	return text


def songsCount(count):
	if count == 1:
		# Translators: spoken after the songs of a playlist are loaded (one song).
		return _("1 song")
	# Translators: spoken after the songs of a playlist are loaded. {count} is a number.
	return _("{count} songs").format(count=count)


def playlistEmpty():
	# Translators: item shown inside an empty playlist.
	return _("Empty playlist")


def songsHidden():
	# Translators: item shown inside a playlist whose songs Spotify does not give to the add-on.
	return _("Spotify only shows the songs of playlists that are yours or that you collaborate on.")


def notPlayable():
	# Translators: spoken when the selected song cannot be played.
	return _("This song is not available to play.")


def searchingPlaylists():
	# Translators: spoken while searching inside the user playlists.
	return _("Searching in your playlists…")


def foundInPlaylists(songs, playlists):
	# Translators: spoken after searching inside the playlists. {songs} and {playlists} are numbers.
	return _("{songs} songs found in {playlists} playlists").format(songs=songs, playlists=playlists)


def sortKeyLabels():
	"""Labels of library.SORT_KEYS, in the same order."""
	return [
		# Translators: sort option: the order saved on Spotify.
		_("Playlist order (as saved on Spotify)"),
		# Translators: sort option.
		_("Title"),
		# Translators: sort option.
		_("Artist"),
		# Translators: sort option.
		_("Album"),
		# Translators: sort option.
		_("Date added"),
		# Translators: sort option.
		_("Duration"),
	]


def sortedText(name, keyLabel, descending):
	if descending:
		# Translators: spoken after sorting a playlist in descending order. {name} is the playlist, {key} the sort option.
		return _("{name} sorted by {key}, descending").format(name=name, key=keyLabel)
	# Translators: spoken after sorting a playlist. {name} is the playlist, {key} the sort option.
	return _("{name} sorted by {key}").format(name=name, key=keyLabel)


def savingOrder(name):
	# Translators: spoken while the new order is saved on Spotify.
	return _("Saving the new order of {name} on Spotify…").format(name=name)


def orderSaved(name):
	# Translators: spoken after the new order was saved on Spotify.
	return _("New order of {name} saved on Spotify").format(name=name)


def confirmSaveOrder(name):
	# Translators: confirmation before changing the order of a playlist on Spotify.
	return _("Change the order of {name} on Spotify? The playlist will have this order on every device.").format(name=name)


def confirmDelete(name):
	# Translators: confirmation before deleting a playlist.
	return _("Delete the playlist {name}? It will leave your Spotify library. A playlist of yours can be recovered on your Spotify account page, in Recover playlists.").format(name=name)


def deleted(name):
	# Translators: spoken after deleting a playlist.
	return _("Playlist {name} deleted").format(name=name)
