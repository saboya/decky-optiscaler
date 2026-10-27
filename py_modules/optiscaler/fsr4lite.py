"""Fetch AMD's FSR 4.1.2 library (the source of the INT8 Lite model).

AMD ships amdxcffx64.dll only inside the Adrenalin installer, a 1.7 GB 7z SFX
compressed as a few solid LZMA2+BCJ blocks. 7-Zip's multithreaded LZMA2 resets
its dictionary every so often, so decoding can start at a reset chunk shortly
before the DLL. The recipe below pins that chunk's offsets and the DLL's
SHA-256; only the stretch from the chunk to the end of the DLL (~43 MiB) is
downloaded, decoded in one streaming pass, and kept if the hash matches. Nothing
from AMD is bundled with this plugin.

Adapted from FSR4Injector's fsr4_dll.py (https://github.com/Rayekkk/FSR4Injector),
Copyright (c) 2026 Rayekkk, BSD-3-Clause.
"""

import hashlib
import os
import ssl
import urllib.request
from pathlib import Path

RECIPE = {
    "id": "amd-4.1.2",
    "api": "dx12",
    "driver": "Adrenalin 26.10.1",
    "fsr": "4.1.2",
    "file": "amdxcffx64.dll",
    "file_version": "2.4.0.4370",
    "url": "https://drivers.amd.com/drivers/whql-amd-software-adrenalin-edition-26.10.1-win11-c.exe",
    "referer": "https://www.amd.com/",
    # LZMA2 dictionary-reset chunk, as an absolute offset into the installer.
    "packed_offset": 857273233,
    # Where that chunk starts in its block's decoded stream (the BCJ filter needs it).
    "unpacked_offset": 1610612736,
    # The DLL's start, counted from the chunk, and its length.
    "dll_offset": 124861144,
    "dll_size": 85684104,
    "sha256": "c33a287f3048bf02311cae430b6a977500b94ca7b315cd7bff751e6b03e483e3",
}
# The Vulkan build of the same library. Both come out of the same 7z block (the
# one holding amdxcffx64.dll), at a dictionary reset 47.8 MB before this DLL, so
# only ~30 MB is downloaded. Its CRC32 (54d9e289) is also what the archive's own
# header records for it, which is an independent check on the decoded bytes.
RECIPE_VULKAN = {
    "id": "amd-4.1.2-vk",
    "api": "vulkan",
    "driver": "Adrenalin 26.10.1",
    "fsr": "4.1.2",
    "file": "amdvkffx64.dll",
    "file_version": "2.4.0.4370",
    "url": RECIPE["url"],
    "referer": RECIPE["referer"],
    "packed_offset": 791702864,
    "unpacked_offset": 1342177280,
    "dll_offset": 47769160,
    "dll_size": 72497568,
    "sha256": "80e761f7c8c0ec8ead7b321df01911baaf917defae51388d29eaecb1d6bc58bd",
}
RECIPES = {"dx12": RECIPE, "vulkan": RECIPE_VULKAN}
EULA_URL = "https://www.amd.com/en/legal/eula/amd-software-eula.html"
CHUNK = 1 << 20
USER_AGENT = "Mozilla/5.0 (decky-optiscaler)"
CA_FILES = ("/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem")


class FetchError(Exception):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def is_valid(path, recipe=RECIPE):
    try:
        return (os.path.getsize(path) == recipe["dll_size"]
                and sha256_file(path) == recipe["sha256"])
    except OSError:
        return False


def cached_path(cache_dir, recipe=RECIPE):
    return Path(cache_dir) / recipe["id"] / recipe["file"]


def _ssl_context():
    """Verified TLS; never turned off. Decky's Python may carry no CA store of its own."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, OSError):
        pass
    for cafile in CA_FILES:
        if os.path.isfile(cafile):
            return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def _open(recipe):
    # AMD's CDN answers open-ended ranges with the whole file; a closed one works.
    start = recipe["packed_offset"]
    end = start + int((recipe["dll_offset"] + recipe["dll_size"]) * 1.01) + CHUNK
    request = urllib.request.Request(recipe["url"], headers={
        "User-Agent": USER_AGENT, "Referer": recipe["referer"],
        "Range": f"bytes={start}-{end}"})
    return urllib.request.urlopen(request, timeout=60, context=_ssl_context())


def fetch(dest, recipe=RECIPE, progress=None, opener=_open, cancelled=lambda: False):
    """Download, decode and verify the DLL into `dest`. Leaves nothing behind on failure."""
    try:
        import lzma
    except ImportError as exc:
        raise FetchError("this Python has no lzma module; the DLL cannot be decoded") from exc

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    skip, size = recipe["dll_offset"], recipe["dll_size"]
    decoder = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[
        {"id": lzma.FILTER_X86, "start_offset": recipe["unpacked_offset"] % 2**32},
        {"id": lzma.FILTER_LZMA2, "dict_size": 2**24},
    ])
    digest = hashlib.sha256()
    tmp = dest.with_name(dest.name + ".part")
    got = 0
    try:
        with opener(recipe) as response, open(tmp, "wb") as out:
            if getattr(response, "status", 206) != 206:
                raise FetchError(f"server ignored the range request (HTTP {response.status})")
            while got < size:
                if cancelled():
                    raise FetchError("cancelled")
                chunk = response.read(CHUNK)
                if not chunk:
                    raise FetchError("download ended before the DLL was complete")
                try:
                    data = decoder.decompress(chunk)
                except lzma.LZMAError as exc:
                    raise FetchError(f"AMD package does not match the recipe ({exc})") from exc
                if skip:
                    cut = min(skip, len(data))
                    skip -= cut
                    data = data[cut:]
                data = data[:size - got]
                if data:
                    out.write(data)
                    digest.update(data)
                    got += len(data)
                    if progress:
                        progress(got, size)
        if digest.hexdigest() != recipe["sha256"]:
            raise FetchError("checksum mismatch: AMD changed the package, a new recipe is needed")
        os.replace(tmp, dest)
    except OSError as exc:
        raise FetchError(f"network or disk error: {exc}") from exc
    finally:
        if tmp.exists():
            tmp.unlink()
    return dest


def ensure(cache_dir, recipe=RECIPE, logger=None, **kwargs):
    """The verified DLL from the cache, fetching it first when it is not there."""
    path = cached_path(cache_dir, recipe)
    if is_valid(path, recipe):
        return path
    if logger:
        logger.info("fetching AMD FSR %s (%s) from %s", recipe["fsr"], recipe["driver"], recipe["url"])
    fetch(path, recipe, **kwargs)
    return path
