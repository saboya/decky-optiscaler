# Steam Deck FSR 4.1.2 Lite (experimental)

Close the game, install OptiScaler through the plugin, and select
**FSR 4.1.2 Lite — Steam Deck** under Basic → Override upscaler with.

This fork bundles an OptiScaler **10.x nightly** (`v10.0.0-pre1`, 2026-10-27,
commit `b19cfd29`) because 0.9.4 has no setting for the Lite model.

## What the option does

- Fetches AMD's `amdxcffx64.dll` (FidelityFX 2.4.0.4370, FSR 4.1.2) from AMD's
  Adrenalin 26.10.1 installer. Only the ~43 MB stretch of the installer that
  holds the DLL is downloaded, decoded locally and checked against a pinned
  SHA-256. Nothing from AMD is bundled with the plugin. The first use accepts
  the AMD Software EULA on your behalf.
- Puts the DLL in the game's `OptiScaler/` folder, where OptiScaler 10.x looks
  for it, and writes `Fsr4GpuSupport=4`, `Fsr4Model=3` (INT8 Lite),
  `UpscalerIndex=0`, `Fsr4EnableWatermark=true` and the `ffx` / `ffx_12` backends.
- The DLL, the INI and the manifest are written as one unit and rolled back
  together if any step fails. It refuses while the game is running.

The download recipe is adapted from
[FSR4Injector](https://github.com/Rayekkk/FSR4Injector) (BSD-3-Clause).

## Verification

Launch the game through its supported upscaler input. The watermark is on, so it
shows which model runs. Plain FSR3 means a fallback.

## Not verified

- Nobody has confirmed the Lite model on a Steam Deck (Van Gogh, RDNA 2). The
  reports found were from RDNA 3.5 handhelds.
- AMD's library asks Windows for the GPU family and Wine cannot answer. FSR4Injector
  ships a stand-in `amdxc64.dll` for that; this plugin does not. OptiScaler 10.x's
  `Fsr4GpuSupport` and `LoadCustomAmdxc64OnRdna2` may be enough, or may not.
- Proton 11 or newer is expected to be needed.

## Live control

The in-game ASI is rebuilt against the nightly's `Config` and `State` layouts,
so frame generation, the upscaler switch, the FFX frame generator and FSR
version switches and the two frame rates are all wired up again.

**None of it has been run in a game yet.** The `State` offsets were derived from
the headers and cross-checked against the memory accesses in the shipped
`OptiScaler.dll` (see `asi/optiscaler_ref/SOURCE_COMMIT.txt`), and every lookup
fails closed, so a layout that does not match leaves the feature reporting
unavailable rather than writing anywhere. Two limits:

- Only the DX12 FFX version list is read; Vulkan games report none.
- `std::mutex` (80 bytes) and `std::deque` (40 bytes) are MSVC internals that the
  headers do not give, so those sizes come from the binary.

## Switching back / removing

Choose another upscaler in Basic settings, or **Remove FSR 4.1.2 Lite** in
Installed Files & FSR 4, which deletes AMD's DLL from the game and resets the
model settings. Uninstall removes it as well.

Avoid modified or injected DLLs in games whose anti-cheat forbids them.
