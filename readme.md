# SpotifyNVDA

NVDA add-on to listen to Spotify with your account: your playlists, song and playlist search, new playlists, play and pause, change songs, change the volume and continue the last song, all from the keyboard with spoken feedback.

## Before you start (once)

Spotify asks each person to use their own free "app", created in the developer dashboard:

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard), sign in with your Spotify account and accept the terms if asked.
2. Choose **Create app**. Fill in a name (for example "My NVDA") and a description.
3. In **Redirect URIs**, type exactly `http://127.0.0.1:8898/callback` and choose **Add**.
4. In **Which API/SDKs are you planning to use?**, check **Web API**. Accept the terms and save.
5. Open the app, go to **Settings** and copy the **Client ID** (32 letters and numbers).
6. In **User Management**, add your name and the e-mail of your Spotify account (apps in development mode only accept the listed accounts).
7. In NVDA, open the NVDA menu, Preferences, Settings, **Spotify** category, paste the Client ID in **Spotify Client ID** and press OK.

The Client ID is not a password: with PKCE, no secret is stored on the computer.

## Sign in

1. Press **NVDA+Alt+P** to open the Spotify window.
2. Choose **Sign in with Spotify**. The browser opens Spotify's own login page.
3. Sign in and choose **Agree**. The page says you can close the tab.
4. NVDA says "Signed in to Spotify as …" and the window shows your playlists.

You stay signed in the next times you start NVDA, also after updating the add-on. The session is encrypted with the Windows data protection, only for your Windows user.

## Songs of the playlists

The results are a tree: Right Arrow opens a playlist and shows its songs, Left Arrow closes it, Enter on a song plays the playlist from that song and Delete on a playlist deletes it (after confirming). The Type box also offers **Songs in my playlists**, which searches inside your playlists ignoring accents and case. **Order songs…** sorts a playlist by title, artist, album, date added or duration and, for your own playlists, can save the new order on Spotify. Spotify only shows the songs of playlists you own or collaborate on.

## Shortcuts

| Shortcut | Action |
|---|---|
| NVDA+Alt+P | Open the Spotify window |
| NVDA+Alt+Space | Play or pause |
| NVDA+Alt+Right Arrow | Next song |
| NVDA+Alt+Left Arrow | Previous song |
| NVDA+Alt+Up Arrow | Volume up |
| NVDA+Alt+Down Arrow | Volume down |
| NVDA+Alt+A | Say what is playing |
| NVDA+Alt+U | Continue the last song |

They can be changed in NVDA, Preferences, Input gestures, Spotify category, where there is also a "Sign out" command without a shortcut.

## Where the sound comes from

The add-on controls Spotify Connect: the sound comes from the Spotify app on this computer (or a phone, speaker, wherever it is playing). If no device is open, the add-on starts the Spotify app **in the background**: minimized, without taking the focus and with its window hidden (no taskbar button, no Alt+Tab). A Spotify you opened yourself is never touched. Spotify only allows playback through its own apps, so it must be installed; the add-on just keeps it out of sight (setting: Keep the Spotify app hidden). Playback control through the Spotify API **needs Spotify Premium**; listing, searching and creating playlists work with any account.

## Privacy and security

* Sign-in on Spotify's official page with PKCE: the add-on never sees your password.
* Tokens encrypted with the Windows data protection; never in the log, in speech or in nvda.ini.
* Connections only to Spotify, over HTTPS with verified certificates.
* To also remove the permission on Spotify's site, use [spotify.com/account/apps](https://www.spotify.com/account/apps/).
