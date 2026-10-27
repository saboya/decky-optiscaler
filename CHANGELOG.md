# Changelog

Newest first. Each release ships `Decky OptiScaler.zip` for Decky Loader's
*Install from URL* (Developer mode). 0.0.x bundles **OptiScaler 0.9.4**; 0.1.0 and
later bundle a **10.x nightly**, named in each entry.

## [Unreleased]

### Changed

- **FSR 4.1.2 Lite picks its own FSR version in the game.** The preset used to
  leave `UpscalerIndex=0` and rely on it being the right entry, which it is not on
  Vulkan: that list has the SDK's FSR 3 versions first and AMD's driver library,
  the only one with the Lite model, appended last. The in-game plugin now reads
  the list the game reports, takes the highest entry that is 4.1.2 or newer (the
  SDK's own FSR 4 is 4.1.1 and has no Lite model), and switches to it with the
  same rebuild the FSR version picker uses. It does so only while the Lite model
  is what is configured, leaves a game that already qualifies alone, and when the
  list has nothing new enough it says so in the panel and changes nothing. The
  choice is made again each launch, since it is only right for that game on that
  API. The rule is plain C++ (`asi/lite_select.h`) with a native test that the
  self-test compiles and runs; it has not been run inside a game.
- The live status file is schema 7: it adds `lite_state` and `lite_index`.

## [0.1.0-lite.1] - 2026-10-27

**Prerelease, and not yet run in a game.** FSR 4.1.2 Lite on the Steam Deck, on
top of an OptiScaler 10.x nightly. Everything below passes the plugin's own
tests (494 checks and 34 lifecycle tests); none of it has been tried on a Deck.

This is a fork of [danielcamilo1/decky-optiscaler](https://github.com/danielcamilo1/decky-optiscaler)
0.0.7. See the README for what that means.

### Changed

- **Bundles OptiScaler 10.0.0-pre1, nightly 2026-10-27** (commit `b19cfd29`)
  instead of 0.9.4. 0.9.4 has no setting for the Lite model. The nightly is a
  development build; the archive's SHA-256 is pinned in the plugin.
- **The install layout is 10.x's.** The support DLLs live in `OptiScaler/` next to
  the proxy instead of beside it, and the live-control plugin is in
  `OptiScaler/plugins/`. Install, uninstall, backup and restore all follow it, and
  a game set up by 0.0.7 is migrated in place: the old files are removed, the
  game's own FidelityFX DLL comes back where it belongs, and imported FSR 4
  driver DLLs are moved into `OptiScaler/` rather than lost.
- The settings schema is regenerated from the nightly's INI: 350 options across
  37 sections (was 288 across 34). The Basic upscaler presets write `ffx` /
  `ffx_12` and `UpscalerIndex`; `Fsr4Update` and `Fsr4ForceEnableInt8` are gone
  from 10.x and are no longer written.

### Added

- **FSR 4.1.2 Lite — Steam Deck**, in the Basic upscaler dropdown, replacing
  *FSR 4.1.1b — Steam Deck*. One choice fetches AMD's FSR 4.1.2 libraries from
  AMD's Adrenalin 26.10.1 installer and selects the INT8 Lite model
  (`Fsr4GpuSupport=4`, `Fsr4Model=3`, watermark on). Only the stretch of the
  installer holding each DLL is downloaded (about 75 MB in all), decoded locally
  and checked against pinned hashes; nothing from AMD ships in the plugin. The
  DLLs, the INI and the manifest are written together and rolled back together,
  and it refuses while the game is running. *Remove FSR 4.1.2 Lite* undoes it.
  The download recipe is adapted from
  [FSR4Injector](https://github.com/Rayekkk/FSR4Injector) (BSD-3-Clause).
- **Native Vulkan games.** The Vulkan library (`amdvkffx64.dll`) is fetched as
  well, native Vulkan games get `VulkanUpscaler=ffx`, and live control reads the
  FFX version list that matches the game's graphics API, since OptiScaler keeps a
  separate one for Vulkan and it is the one that offers the driver's FSR 4.
- `scripts/verify_state_layout.py` checks the live-control plugin's model of
  OptiScaler's `State` object against the shipped `OptiScaler.dll` itself, and
  reports a miss when the layout is wrong.

### Fixed

- Live control works against 10.x. Its model of OptiScaler's internals was
  written for 0.9.4: the upscaler ids became an enum, a table it used to tell
  apart from the others was removed, and several members moved. The `Config` and
  `State` mirrors are regenerated and ported, and every lookup still fails
  closed, so a layout that does not match leaves a feature reporting
  unavailable.

### Known gaps

- Not run in a game. In particular: that the Lite model is actually selected on a
  Steam Deck's RDNA 2 GPU, that `VulkanUpscaler=ffx` makes a Vulkan game load
  `amdvkffx64.dll`, and the live-control offsets, which are derived from the
  headers and cross-checked against the binary, not observed.
- AMD's library identifies the GPU through Windows driver data that Wine does not
  have, so under Proton it may fall back to FSR 3. FSR4Injector ships a stand-in
  `amdxc64.dll` for that; this plugin does not, and relies on OptiScaler 10.x's
  `Fsr4GpuSupport` instead. If the watermark says FSR3, that is the first thing
  to suspect.
- Native Vulkan games have no frame rate: OptiScaler only counts frames in its
  DXGI swapchain wrapper.
- `Fsr4Preset` is left to the game's own default.
- OptiPatcher and the compatibility-list seed were not re-checked against the
  nightly.

[0.1.0-lite.1]: https://github.com/saboya/decky-optiscaler/releases/tag/v0.1.0-lite.1

## [0.0.7] - 2026-09-18

FSR 4 on the Steam Deck, and the compatibility list is whole again.

### Added

- **FSR 4.1.1b — Steam Deck**, in the Basic upscaler dropdown. One choice
  downloads the community RDNA 2 build of the FidelityFX upscaler, checks it
  against a hash pinned in the plugin, puts it next to the game and switches on
  the INT8 override that reaches FSR 4 on RDNA 2. Close the game first; it
  applies on the next launch. Frame generation is left exactly as it was.
  Thanks to [@drewboardman](https://github.com/drewboardman), who built this and
  tested it on a Deck.
- Setup names which upscaler build is in the game folder, identified by its bytes
  rather than its version — the community build reports the same 4.1.1 the
  released SDK does — and will put the bundled one back.

### Fixed

- **297 of the 695 games on the compatibility list were answering "no wiki entry
  matched".** One row on the wiki was saved without its leading `|`, which the
  parser read as the end of the table, so everything after Metro Exodus was
  invisible: Monster Hunter Wilds, the Resident Evil entries, Stalker 2, The
  Witcher 3 and 293 others. A row that lost its first character is now read as
  the row it is. Bundled list regenerated — 698 entries.
- Games listed under *Upscaler mods support* and *Luma Unreal Engine* no longer
  claim OptiPatcher support they do not have, and their notes are their notes
  rather than the images column. Those two tables have one column fewer than the
  main one, and were being read as though they did not.
- The refreshed list adds Onimusha: Way of the Sword to the games that need
  REFramework in place before OptiScaler can do anything.
- All six FSR 4 quality presets are offered. The reference INI writes them as one
  comma-separated line, of which two were being read, so Quality, Performance,
  DRS and Ultra Performance were rejected by the settings writer and never
  reached the file.
- Choosing an FSR version on RDNA 2 no longer turns on the FSR 4 upgrade path.
  That path forces the FP8 model, which such a GPU does not have, and OptiScaler
  answers with a silent FSR 3 fallback.
- Verification recognises a community upscaler by hash, and reinstalling keeps it
  instead of overwriting it with the bundled build.
- Replacing the upscaler is atomic and rolls back the DLL, the INI and the
  manifest together if any part of it fails. It refuses while the game is
  running, and on an install this plugin did not make.

[0.0.7]: https://github.com/danielcamilo1/decky-optiscaler/releases/tag/v0.0.7

## [0.0.6] - 2026-08-28

Everything from the `0.0.5.x-testing` prereleases, as one release.

### Added

- Non-Steam games can be set up. Their folder is taken from the shortcut's
  target, since Steam reports no install folder for them.
- Games whose wiki entry requires
  [REFramework](https://github.com/praydog/REFramework) say so on the setup
  checklist and link the right build. Installing it for you is disabled for
  now, until I can gather more information to get it fully working.

### Fixed

- A non-Steam game's launch options are read from `shortcuts.vdf`, so removing
  OptiScaler no longer wipes them.
- Settings are read only from the install method this plugin actually performs.
  Monster Hunter Wilds would not boot because of this.
- Settings hedged by an "if", a "try", an "e.g." or a "desired" are reported
  rather than applied. Resident Evil 2 was getting 2× output scaling it never
  asked for.
- Setup names the OptiScaler overlay's new shortcut key when an entry moves it
  off Insert.
- Wiki pages with brackets in the name download again — Resident Evil, Dead
  Space (2023) and Elden Ring were affected. Bundled list regenerated.

[0.0.6]: https://github.com/danielcamilo1/decky-optiscaler/releases/tag/v0.0.6

## [0.0.5.3-testing] - 2026-08-27

Prerelease on the `testing` branch.

### Added

- Non-Steam games can be set up. Their folder is taken from the shortcut's
  target, since Steam reports no install folder for them.

### Changed

- Automatic REFramework setup is disabled for now, until I can gather more
  information to get it fully working. The games that need it still say so and
  link the right build, and REFramework installed by 0.0.5.1/0.0.5.2-testing can
  still be removed.

### Fixed

- A non-Steam game's launch options are read from `shortcuts.vdf`, so removing
  OptiScaler no longer wipes them.

## [0.0.5.2-testing] - 2026-08-24

Prerelease.

### Fixed

- Monster Hunter Wilds would not boot: settings were being read from install
  methods other than the one performed.
- Resident Evil 2 got 2× output scaling it never asked for. Settings hedged by
  an "if", a "try", an "e.g." or a "desired" are reported, not applied.
- Setup names the OptiScaler overlay's new shortcut key when an entry moves it
  off Insert.

## [0.0.5.1-testing] - 2026-08-24

Prerelease. REFramework auto-install — **disabled in 0.0.5.3-testing**.

### Added

- The nine compatibility-list games that need REFramework are detected, and the
  build, the `dinput8` override and `PDPerfPlugin.dll` are stated on the
  checklist.

### Fixed

- Wiki pages with brackets in the name download again — Resident Evil, Dead
  Space (2023) and Elden Ring were affected. Bundled list regenerated.

## [0.0.5] - 2026-08-23

### Added

- Removing OptiScaler asks what to do with the Steam launch options: restore
  what was there, remove only the OptiScaler override, or change nothing. The
  answer can be remembered.
- A Settings tab on the main page: remembered answers, the switch that stops
  answers being kept, and the state of the compatibility list.
- A copy of the compatibility list ships with the plugin, so an offline Deck
  still matches games.

### Changed

- The compatibility list is read from cache and refreshed in the background,
  instead of a network timeout in front of every question.

### Fixed

- Launch options are read from three sources, not just
  `SteamClient.Apps.GetAppLaunchOptions`, which some client builds do not have.
- A wiki that will not download is no longer reported as "your game is not on
  the list", and there is a **Try again** button.
- A stalled connection is retried over IPv4.
- The last-resort unverified TLS context no longer reads the system trust store.

[0.0.5]: https://github.com/danielcamilo1/decky-optiscaler/releases/tag/v0.0.5

## [0.0.4] - 2026-08-21

### Added

- The exact FSR version the running game built, rather than just the backend id.
- A second dropdown for which FSR version to run. Applies without a restart.
- Both frame rates while frame generation is on: what the game renders and what
  reaches the screen.
- A live-control readout that says why a number is missing, and a warning when a
  game's in-game plugin is out of date.

### Fixed

- A dropdown could keep a name its option list no longer used.
- Asking for FSR 4 could silently give you FSR 3.
- A game on the SD card reported itself as "writing to a different folder".
- The newest FSR version was named after the reference INI's build, not the
  bundled one.

[0.0.4]: https://github.com/danielcamilo1/decky-optiscaler/releases/tag/v0.0.4

## [0.0.3] - 2026-08-20

### Fixed

- The upscaler dropdown lagged one change behind after reopening the panel.
- The FidelityFX FG version control disappeared on games reporting one
  generator.

[0.0.3]: https://github.com/danielcamilo1/decky-optiscaler/releases/tag/v0.0.3

## [0.0.2] - 2026-08-20

### Fixed

- A control could display a value it was not set to.
- Picking the third FidelityFX frame generator did nothing.
- Settings the config writer refused are reported instead of left on screen.
- Re-reading the config could undo an edit or blank the panel.
- The live upscaler switch works for DX11 games.

[0.0.2]: https://github.com/danielcamilo1/decky-optiscaler/releases/tag/v0.0.2

## [0.0.1] - 2026-08-20

First public release.

### Added

- Per-game install, into a folder scored automatically and overridable by hand.
  Steam libraries including the SD card, plus any folder as a custom library.
- Automatic setup from the OptiScaler
  [Compatibility List](https://github.com/optiscaler/OptiScaler/wiki/Compatibility-List),
  as a checklist that names the wiki field behind every line before writing it.
- Basic settings (four controls) and Advanced (all 288 options across 34
  sections), generated from the shipped `OptiScaler.ini` and preserving its
  comments.
- Live in-game control of frame generation, the FidelityFX FG version and the
  upscaler, with a frame rate readout, via a bundled ASI plugin.
- Quick Access panel: the running game's live controls and a filtered game list.
- Files an install would overwrite are backed up and restored on uninstall.
- `OptiScaler.log` parsing, bundled
  [OptiPatcher](https://github.com/optiscaler/OptiPatcher), and an **OptiScaler
  Settings** entry in the Steam library context menu.

[0.0.1]: https://github.com/danielcamilo1/decky-optiscaler/releases/tag/v0.0.1
