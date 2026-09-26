# Nightbringer Action HUD

A free Aphelios input overlay for Windows and OBS, by **Aleksis007 / Karanthir**.
Colored weapon tiles, stacked attack-move inputs, burst effects and a kill highlight.

## Download and use

Download **Nightbringer-Action-HUD-0.2.0-beta.1-Windows-x64.zip** from this repository's Releases.
Use the Windows download, not GitHub's automatically generated source-code ZIP.
No Python installation, account, API key or administrator access is required.

1. Extract the ZIP into a normal folder.
2. Open **NightbringerActionHUD.exe**. On the first run, open League Practice Tool with Aphelios
   and follow the two timed prompts to mark the Q icon's corners. Calibration is
   saved automatically for your screen and League HUD size.
3. Add one **Browser Source** in OBS:
   - **URL:** `http://127.0.0.1:5002/hud`
   - **Width:** `480`
   - **Height:** `180`
4. Keep Nightbringer Action HUD open while playing. Open it again for each streaming session;
   OBS remembers the source and Nightbringer Action HUD remembers calibration.

The overlay is transparent and blank until an input occurs. To position it with
sample inputs, temporarily use `http://127.0.0.1:5002/hud?demo=1`. Remove `?demo=1`
before streaming. Demo events stay inside that browser source.

Check all five Q weapons, W, R, attack-move and the actual OBS source in Practice
Tool before relying on it. After changing resolution, monitor arrangement or
League HUD size, close Nightbringer Action HUD and open **RECALIBRATE.cmd**.

## What it detects

- Default **Q, W, R** key presses. Q's weapon is estimated from the calibrated
  screen region; it may be wrong when the icon is obscured or calibration differs.
- **A then left-click** within 1.5 seconds counts as an attack-move input.
  Direct attack-move-click, remapped Q/W/R and mouse-button attack bindings are
  not supported. This is not a counter of every actual autoattack.
- A kill animation when League's local Live Client Data API reports a new kill
  by the active player. No API key is used; old kills are not replayed on attach.
- Up to eight visual tiles, oldest on the left; nearby attack inputs stack.
  Same-weapon Q repeats within 1.5 seconds are filtered.

Inputs do not prove a successful cast, hit, damage or cooldown. Heat is a visual
effect based on recent input frequency. Disable effects with
`/hud?heat=0&burst=0&kill=0` if preferred.

## Privacy and troubleshooting

The app polls these keys globally, including outside League. Close it when not
needed. It reads the small Q rectangle on Q presses, keeps recent action labels
in memory, and does not save screenshots or a keystroke log. Settings contain
only calibration coordinates and the attack-move key. They are stored in
`%LOCALAPPDATA%\NightbringerActionHUD\settings.json`.

The overlay server listens only on `127.0.0.1`. The only other application network
requests are to League on `https://127.0.0.1:2999`. No analytics, uploads, game
memory access, injected code, or automated game inputs are included.

- **Already running / address in use:** close the other Nightbringer Action HUD copy. An
  advanced user can use `NightbringerActionHUD.exe --port 5003` and change the OBS URL to match.
- **Wrong Q colors:** recalibrate; keep the game visible on the calibrated monitor.
- **Blank:** try the demo address, then restore the real address and test Q/W/R.
- **Different attack-move key:** close the app, edit `attack_move_key` in the saved
  settings (one letter or number), and reopen it.
- **Stop/uninstall:** close the console. Remove the OBS source and downloaded
  folder; optionally remove `%LOCALAPPDATA%\NightbringerActionHUD`. No startup task or system
  service is installed.

## Beta status

This is an **unsigned Windows x64 community beta**. Windows may display an
unknown-publisher warning. It has not been certified by Riot or Vanguard.
Local automated checks are not proof of compatibility on another PC or real
OBS/gameplay acceptance. Do not treat this beta as universally tested.

## Source and build

On Windows with 64-bit Python 3.10, create a virtual environment, install
`requirements-build.txt`, run `python test_action_hud.py`, then
`python build_release.py`. The build produces a standalone executable and a
release ZIP in `dist/`. `python action_hud.py --preview --port 5013` runs only the
visual preview, without polling inputs, capturing the screen or contacting League.

Packaging follows [PyInstaller's runtime guidance](https://pyinstaller.org/en/stable/runtime-information.html).
Executables belong in [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

## Credits and use

Nightbringer Action HUD is free to download and use as a streaming overlay. Original overlay
presentation: Aleksis007 / Karanthir. No payment or donation is required.
This repository does not grant ownership or a license to Riot's artwork.
League of Legends, Aphelios and the game icons belong to Riot Games. Nightbringer Action HUD
is an unofficial fan project; Riot Games does not endorse or sponsor it.
See Riot's [fan-content policy](https://www.riotgames.com/en/legal).
Bundled third-party license notices are included in `THIRD_PARTY_LICENSES/`.
