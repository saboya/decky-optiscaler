# Steam Deck FSR 4.1.2 Lite (experimental)

Close the game, install OptiScaler through the plugin, and select
**FSR 4.1.2 Lite — Steam Deck** under Basic → Override upscaler with.

This fork bundles an OptiScaler **10.x nightly** (`v10.0.0-pre1`, 2026-10-27,
commit `b19cfd29`) because 0.9.4 has no setting for the Lite model.

## What the option does

- Fetches AMD's FSR 4.1.2 libraries from AMD's Adrenalin 26.10.1 installer: 
  `amdxcffx64.dll` (DirectX, ~43 MB download) and `amdvkffx64.dll` (Vulkan,
  ~30 MB). Only the stretch of the installer that holds each DLL is downloaded,
  decoded locally and checked against a pinned SHA-256. Nothing from AMD is
  bundled with the plugin. The first use accepts the AMD Software EULA on your
  behalf. Both contain the `FSR4Lite_Int8` provider.
- Puts them in the game's `OptiScaler/` folder, where OptiScaler 10.x looks for
  them, and writes `Fsr4GpuSupport=4`, `Fsr4Model=3` (INT8 Lite),
  `UpscalerIndex=0`, `Fsr4EnableWatermark=true`, and the `ffx` / `ffx_12`
  backends: DX12 uses `ffx`, DX11 uses `ffx_12`, and native Vulkan uses `ffx`.
- The DLLs, the INI and the manifest are written as one unit and rolled back
  together if any step fails. It refuses while the game is running.

The download recipe is adapted from
[FSR4Injector](https://github.com/Rayekkk/FSR4Injector) (BSD-3-Clause). The
Vulkan recipe is this plugin's own: it is the same 7z block, 47.8 MB before the
Vulkan DLL, and the decoded file's CRC32 matches the one the archive records.

## Vulkan

Native Vulkan games differ from DirectX ones in ways that matter here:

- OptiScaler keeps a **separate FFX version list for Vulkan**, and it is the one
  that includes the driver's FSR 4 (where INT8 Lite lives). The ASI now reads
  the list that matches `State::api`, and re-reads it if the game's API turns
  out to be different from what it first saw.
- The Vulkan list *appends* the driver's FSR 4 after the SDK's versions, so
  `UpscalerIndex=0` is not necessarily it. The right index is only known once
  the game has queried the list; the panel's FSR version picker shows what the
  game reports.
- **No frame rate for native Vulkan.** OptiScaler counts frames in its DXGI
  swapchain wrapper, so with no DXGI swapchain `frameCount` never moves and the
  frame rate reads as unavailable. DXVK and vkd3d-proton games present through
  DXGI and are counted. That is OptiScaler's behaviour, not something this
  plugin can fix.

**Not verified:** that `VulkanUpscaler=ffx` is what makes a Vulkan game load
`amdvkffx64.dll`. The source says the FFX Vulkan backend initialises the driver
provider (`FSR4DriverProviderVk`) and looks the DLL up in `OptiDllPath` first, so
it should; nothing has been run.

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

- The FFX version list that is read follows the game's graphics API (DX12 or
  Vulkan); DX11 games use the DX12 list.
- `std::mutex` (80 bytes) and `std::deque` (40 bytes) are MSVC internals that the
  headers do not give, so those sizes come from the binary.

## Switching back / removing

Choose another upscaler in Basic settings, or **Remove FSR 4.1.2 Lite** in
Installed Files & FSR 4, which deletes AMD's DLL from the game and resets the
model settings. Uninstall removes it as well.

Avoid modified or injected DLLs in games whose anti-cheat forbids them.
