# Nightbringer Action HUD

A free Aphelios input overlay for Windows and OBS, by **Aleksis007**.
Shows weapon-colored ability icons, stacked attack-move inputs and kill effects.

## Download and setup

**[Download for Windows](https://github.com/Aleksis0007/nightbringer-action-hud/releases/download/v0.2.0-beta.2/Nightbringer-Action-HUD-0.2.0-beta.2-Windows-x64.zip)**

No Python installation, account or API key is needed.

1. Extract the ZIP into a normal folder.
2. Open **NightbringerActionHUD.exe**. On the first run, open Practice Tool with
   Aphelios and follow the two prompts to mark the corners of your Q icon.
3. In OBS, add a **Browser Source** with these settings:

   | Setting | Value |
   | --- | --- |
   | URL | `http://127.0.0.1:5002/hud` |
   | Width | `480` |
   | Height | `180` |

4. Keep the app open while playing. Open it again each streaming session.
   Your calibration and OBS source are saved for next time.

The background is transparent. The overlay stays blank until you press a supported key.
To position it with sample inputs, temporarily use
`http://127.0.0.1:5002/hud?demo=1`. Remove `?demo=1` before streaming.

## Supported inputs

- **Q, W and R** with their default key bindings. Q's weapon is recognized from
  the calibrated icon on your screen.
- **A followed by left-click** within 1.5 seconds. Consecutive attack-move inputs
  stack together. Direct attack-move-click and mouse-button bindings are not supported.
- A kill effect when League reports a new kill by your player.

This displays inputs, so it cannot confirm that an ability landed or count every
actual autoattack. Same-weapon Q repeats within 1.5 seconds are filtered.
To turn off effects, use `http://127.0.0.1:5002/hud?heat=0&burst=0&kill=0`.

## Troubleshooting

- **Wrong Q color:** close the app and run **RECALIBRATE.cmd**. Repeat calibration
  after changing your resolution, monitor arrangement or League HUD size.
- **Blank overlay:** try the demo URL, then restore the normal URL and test Q/W/R.
- **Already running:** close the other copy before opening the app again.
- **Different attack-move key:** close the app and edit `attack_move_key` in
  `%LOCALAPPDATA%\NightbringerActionHUD\settings.json` to one letter or number.
- **Stop:** close the app window. To uninstall, remove the OBS source and extracted
  folder. You can also remove `%LOCALAPPDATA%\NightbringerActionHUD` to erase settings.

## Privacy and beta status

The app reads the supported keys globally, including outside League, and captures
the small Q-icon area when you press Q. Close it when you are done. It does not save
screenshots or keystroke logs, upload your inputs, or read game memory. It communicates
only with the overlay and League services on your own computer.

This is an **unsigned Windows x64 beta**; Windows may show an unknown-publisher
warning. Test all five weapons and the OBS source in Practice Tool before streaming.
Fresh-PC and real OBS/gameplay testing remain unverified. Riot/Vanguard compatibility
is not certified.

## Credits

By Aleksis007. Free to download and use as a streaming overlay.
League of Legends, Aphelios and the game icons belong to Riot Games. This is an
unofficial fan project, not endorsed or sponsored by Riot Games. Third-party
license notices are included in `THIRD_PARTY_LICENSES/`.

<details>
<summary>Build from source</summary>

On Windows with 64-bit Python 3.10, create a virtual environment and install
`requirements-build.txt`. Run `python test_action_hud.py`, then
`python build_release.py`. The download package is created in `dist/`.

</details>
