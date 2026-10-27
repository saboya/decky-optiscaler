# Decky OptiScaler

[![Build](https://github.com/danielcamilo1/decky-optiscaler/actions/workflows/build.yml/badge.svg)](https://github.com/danielcamilo1/decky-optiscaler/actions/workflows/build.yml)
[![Latest release](https://img.shields.io/github/v/release/danielcamilo1/decky-optiscaler)](https://github.com/danielcamilo1/decky-optiscaler/releases/latest)
[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/danielcamilo)

A [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) plugin that installs and
configures [OptiScaler](https://github.com/optiscaler/OptiScaler) per game from Game Mode
(SteamOS, Bazzite, whatever you run). Frame generation, upscaler overrides and the rest of
OptiScaler's settings, with a gamepad. The ones OptiScaler can change on the fly apply to the
running game; the rest say plainly that they take effect on the next launch.

OptiScaler is bundled, so installing works offline and every game gets the same build. This
fork bundles a **10.x nightly** (10.0.0-pre1, 2026-10-27) rather than 0.9.4, for the FSR 4.1.2
Lite model; see [About this fork](#about-this-fork).

> **Unofficial.** I am an independent developer with no connection to the OptiScaler project.
> This plugin is not made, endorsed or supported by them — it bundles their release and drives
> it from the Steam Deck UI. Please report problems with the plugin
> [here](https://github.com/danielcamilo1/decky-optiscaler/issues), not to the OptiScaler
> maintainers.

## What it does

- **Finds your games and the folder to install into.** Steam libraries from
  `libraryfolders.vdf` including the SD card, non-Steam shortcuts, and any folder you add as a
  custom library. OptiScaler has to sit next to the executable that creates the D3D device, so
  the plugin scores the candidates (Unreal's `Binaries/Win64`, Cyberpunk's `bin/x64`) and lets
  you override its pick.
- **Sets the game up from the wiki, online or not.** Your game is matched against the OptiScaler
  [Compatibility List](https://github.com/optiscaler/OptiScaler/wiki/Compatibility-List), with a
  search box to pin the right entry. A copy of the list ships with the plugin and the last
  download is cached, so answers come from disk at once and the refresh runs behind them. Setup
  is then a checklist — install the DLL under the filename the entry names, write the launch
  options, apply the settings it lists — and every line says which wiki field it came from
  before anything is written. Anything the plugin couldn't place is shown to you rather than
  guessed at, including the games that need
  [REFramework](https://github.com/praydog/REFramework) installed first.
- **Basic or Advanced settings.** Basic is a handful of controls (frame generation on/off, which
  generator, 2X/3X/4X, which upscaler), each driving several INI keys at once. Advanced gives
  you all 350 settings across 37 sections, generated from the comments in `OptiScaler.ini` so
  they match the shipped build. Edits keep every comment in the file, and names are the
  overlay's own.
- **FSR 4.1.2 Lite on Steam Deck (experimental).** Close the game, then choose
  **FSR 4.1.2 Lite — Steam Deck** in Basic settings. One selection fetches AMD's FSR 4.1.2
  libraries (about 75 MB, DirectX and Vulkan) from AMD's own driver package and selects the
  INT8 Lite model made for handhelds. Frame generation stays separate. Nothing from AMD ships
  in the plugin. See [Steam Deck FSR 4](docs/steam-deck-fsr4.md) for verification, rollback and
  what is not verified.
- **Changes settings while you play.** A bundled ASI plugin applies frame generation, the
  FidelityFX FG version, the upscaler and the FSR version immediately from the Quick Access
  panel — next to what the game actually ended up running and, with frame generation on, both
  frame rates. See [Live in-game control](#live-in-game-control).
- **Doesn't lose your files, or your launch options.** Anything an install would overwrite is
  moved into `decky_optiscaler_backup_files/` and put back on uninstall. The launch options the
  game had beforehand are kept the same way, so removing OptiScaler can offer to restore them
  rather than clearing a field it never owned.
- **Odds and ends.** `OptiScaler.log` is parsed for the backend that got created, the GPU and
  the Proton version. [OptiPatcher](https://github.com/optiscaler/OptiPatcher) is bundled. An
  **OptiScaler Settings** entry is added to the game's Steam library context menu.

## Screenshots

<img src="assets/quick-access-live-tiles.jpg" alt="The Quick Access panel over a running game, showing base and frame-generated frame rates side by side, frame generation on, and FSR 4.1.1 as the upscaler" />

Over the running game: what it renders, what reaches the screen, and the exact
FSR version it ended up with — above the controls that change them.

| | |
|---|---|
| <img src="assets/library-context-menu.jpg" alt="The Steam library context menu with an OptiScaler Settings entry" /> | <img src="assets/setup-checklist.jpg" alt="The setup checklist for a game matched on the OptiScaler wiki" /> |
| **OptiScaler Settings** in the game's library context menu. | Setup is a checklist, and it says what it will write before it writes it. |
| <img src="assets/quick-access-frame-generation.jpg" alt="The Quick Access panel showing the frame generation toggle, the in-game state and the frame rate" /> | <img src="assets/quick-access-upscaler.jpg" alt="The Quick Access panel showing the upscaler override and the FG method the wiki recommends" /> |
| Frame generation, the FidelityFX FG version and the live frame rate, over the running game. | The upscaler applies live too; what doesn't is under **Needs a restart**, with the wiki's recommendation under it. |

## Installing

Grab `Decky-OptiScaler-v*.zip` from the
[latest release](https://github.com/danielcamilo1/decky-optiscaler/releases/latest), then either:

- In Game Mode, open Decky's settings, turn on **Developer mode**, and use
  **Install Plugin from URL** with the zip's download link; or
- unpack the zip into `~/homebrew/plugins/` and restart Decky Loader.

Every release bundles OptiScaler itself, so there is nothing else to download. The FSR 4.1.2
Lite option is the exception: it downloads AMD's libraries the first time you use it.
See the [changelog](CHANGELOG.md) for what changed.

A game set up by an older release is migrated in place when you reinstall: the 10.x layout
keeps the support DLLs in an `OptiScaler/` folder, and the old files are cleaned up.

## Live in-game control

OptiScaler reads its INI once, at startup — no file watcher, no IPC — and its overlay gets away
with live changes only because it *is* the game process. So the plugin ships a small ASI plugin
that OptiScaler loads into the game and that makes the same writes the overlay makes. That is
what lets the Quick Access panel change, mid-game:

- **Frame generation** — `Config::FGEnabled`, read every frame.
- **Upscaler** — the backend id into `State::newBackend`, then every entry of
  `State::changeBackend` marked. The overlay's "Change Upscaler" in full.
- **FidelityFX FG version** — `Config::FfxFGIndex`, then `State::fgChanged` and
  `State::scChanged`, so the generator's context is destroyed and rebuilt on the new index. The
  versions offered are the ones the SDK reported to *that* game.
- **FSR version** — `Config::FfxUpscalerIndex` plus the same feature rebuild. One backend id
  covers every FSR from 2.3.4 to 4.1.x, so the exact version comes from the list the running
  game reported — the same one its overlay names in the title bar. OptiScaler keeps separate
  lists for DirectX and Vulkan, and the plugin reads the one that matches the game.

It also reads out both frame rates: what the game renders next to what reaches the screen, and
says when the generator is switched on but not actually inserting frames. Native Vulkan games
have no frame rate: OptiScaler only counts frames in its DXGI swapchain wrapper.

The plugin finds OptiScaler's `Config` and `State` objects in memory and models their layout
from the vendored headers (`asi/optiscaler_ref/`), so it is tied to the exact build it ships
with. `scripts/verify_state_layout.py` checks that model against the shipped `OptiScaler.dll`.
**On this fork it has not been run in a game yet**; every lookup fails closed, so a layout that
does not match leaves the feature reporting unavailable.

## Steam launch options

Proton loads its own `dxgi.dll` unless you tell it not to, so the proxy needs an override:

```
WINEDLLOVERRIDES="dxgi=n,b" %command%
```

Setup shows the exact string for the filename you picked and can write it for you.
`OptiScaler.asi` installs don't need it.

Whatever Steam was passing beforehand is recorded next to the install, so removing OptiScaler
asks what to do with the field: restore exactly what was there, remove only the OptiScaler
override, or leave it alone. The answer can be remembered; **Settings** on the main page lists
remembered answers and takes them back.

## Requirements

- Decky Loader
- One of `7z`, `7zz`, `7za`, `7zr` or `bsdtar` to unpack the bundled release. SteamOS has both
  p7zip and bsdtar. It runs once, on first install.

## Building

```sh
pnpm install
python3 scripts/generate_schema.py   # option metadata, from the reference INI
python3 scripts/fetch_compat_seed.py # refresh the bundled compatibility list
./asi/build.sh                       # live-control ASI -> bin/ (needs zig)
pnpm build
python3 scripts/package.py           # -> out/Decky OptiScaler.zip
```

`asi/build.sh` cross-compiles a Windows x64 DLL with `zig cc`, so you don't need MSVC or a
Windows machine; `brew install zig` is the only prerequisite. Packaging without the ASI works
fine, live control just reports itself as unavailable.

Tests:

```sh
python3 scripts/selftest.py                          # backend, against a synthetic library
python3 scripts/test_fsr4.py                         # install / FSR 4 Lite lifecycle and rollback
python3 scripts/verify_state_layout.py               # ASI's State model vs OptiScaler.dll (needs capstone, pefile)
HARNESS=run.tsx node testharness/build-and-run.mjs    # renders the UI headlessly
HARNESS=all-options.tsx node testharness/build-and-run.mjs
```

## About this fork

This is a fork of [danielcamilo1/decky-optiscaler](https://github.com/danielcamilo1/decky-optiscaler)
0.0.7, which is the project the rest of this README describes. What the fork changes:

- Bundles an OptiScaler **10.x nightly** instead of 0.9.4, and follows its new layout.
- Replaces *FSR 4.1.1b — Steam Deck* with **FSR 4.1.2 Lite**, fetched from AMD's installer.
- Ports the live-control plugin to the nightly and adds native Vulkan support.

It is a **prerelease**, versioned `0.1.0-lite.1`, and the changes above have **not been run in a
game**: they pass the plugin's own tests, and that is all that can be said. The upstream project
and its author are not involved and should not be asked about this fork. Report problems with it
[here](https://github.com/saboya/decky-optiscaler/issues). The nightly is a development build and
AMD's FSR 4.1.2 Lite is days old, so expect rough edges.

## Support

This plugin is free and open source, and it will stay that way. If it got a game running better
on your Deck and you feel like saying thanks, you can buy me a coffee — it is genuinely
appreciated and it keeps the updates coming ☕

[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/danielcamilo)

## Credits

This is an unofficial, independently developed plugin. It is not affiliated with, endorsed by or
supported by the OptiScaler project or any of the projects below; all it does is package and
drive their work.

- [OptiScaler](https://github.com/optiscaler/OptiScaler) and its wiki contributors.
- [Decky Framegen](https://github.com/xXJSONDeruloXx/Decky-Framegen) — reference for how
  OptiScaler is deployed into a game folder on Linux.
- [Decky LSFG-VK](https://github.com/xXJSONDeruloXx/decky-lsfg-vk) — reference for the
  configuration-driven plugin UI.

## AI disclosure

Upstream 0.0.7 was built with heavy use of AI: Claude Opus 5 was the model mainly used for its development. Every design decision, review and manual testing runs were the upstream author's, and that version was run on an Xbox Ally X running Bazzite.

The changes in this fork were also written with an AI assistant, and — unlike upstream — have not been tested on a device.
