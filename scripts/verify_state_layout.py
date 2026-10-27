#!/usr/bin/env python3
"""Check the ASI's State mirror against the OptiScaler.dll this plugin ships.

live.cpp mirrors OptiScaler's `State` class by declaration order, but two types
in it are MSVC standard-library internals the headers cannot size: std::mutex
(80 bytes) and std::deque (40). Their sizes decide every offset after them, so
they are checked against the binary itself rather than assumed.

How: State::Instance() is a function-local static, so the code that builds it
calls one small accessor and then initialises members with constants -- here
`lastMipBias = 100.0f; lastMipBiasMax = -100.0f` -- which identifies the
accessor, and which member sits at which offset. Every `[reg + disp]` memory
operand in .text is then collected (the compiler keeps `State&` in whatever
register it likes, so looking only at rax after the call misses most of them),
and each mirrored member is checked to have at least one access of the width
its type implies at the offset the mirror computes.

That is evidence, not proof: an access of the right width at the right offset
is what a correct layout produces, and a wrong mutex or deque size moves whole
groups of members off any access at all. It is not a substitute for running the
ASI in a game.

Needs `pip install capstone pefile`, and bsdtar or 7z for the bundled archive.

    python3 scripts/verify_state_layout.py [path/to/OptiScaler.dll] [--shift NAME=DELTA ...]

``--shift`` moves one member's expected offset, which is how the check is shown
to be able to fail: a correct layout passes, a layout with a mutex or deque of
the wrong size does not.
"""

import re
import struct
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "py_modules"))

# (member, offset from State::changeBackend, kind). The offsets are the ones
# live.cpp pins with static_assert (selftest.py compares the two), so the
# compiler holds this table to the mirror.
TABLE = [
    ("newBackend", 64, "u32"),
    ("xessDebugFrames", 72, "u32"),
    ("lastMipBias", 76, "f32"),
    ("lastMipBiasMax", 80, "f32"),
    ("WAR_xefgRequestFGToggle", 84, "bool"),
    ("xefgDynamicCapFps", 88, "f32"),
    ("dlssgLastSetMode", 96, "u32"),
    ("ffxUpscalerVersionsDx12.names", 312, "ptr"),
    ("ffxFGVersionNames", 408, "ptr"),
    ("lastFGFrameTime", 592, "f64"),
    ("presentFrameTime", 600, "f64"),
    ("lastFGPresentMs", 608, "f64"),
    ("postDone", 696, "bool"),
]
# lastMipBias sits at +76; its 100.0f initialiser anchors the whole table.
ANCHOR_REL = 76
FLOAT_100 = b"\x00\x00\xc8\x42"
FLOAT_M100 = b"\x00\x00\xc8\xc2"

WINDOW = (-0x40, 0x400)  # relative to changeBackend


def find_dll(argument):
    if argument:
        return Path(argument)
    from optiscaler.constants import PAYLOAD_ARCHIVE
    out = Path(tempfile.mkdtemp(prefix="state-layout-"))
    archive = ROOT / "bin" / PAYLOAD_ARCHIVE
    for command in (["bsdtar", "-xf", str(archive), "-C", str(out)],
                    ["7z", "x", "-y", f"-o{out}", str(archive)]):
        try:
            if subprocess.run(command, capture_output=True).returncode == 0:
                return out / "OptiScaler.dll"
        except OSError:
            continue
    sys.exit("could not unpack the bundled archive (need bsdtar or 7z)")


def find_anchor(data, text_lo, text_hi, image_base, text_rva):
    """The State::Instance() accessor and where lastMipBias is, from the ctor.

        call Instance ; mov dword [rax+D], 100.0f
        call Instance ; mov dword [rax+D+4], -100.0f
    """
    region = data[text_lo:text_hi]
    pattern = re.compile(
        rb"(?s)\xe8(....)\xc7[\x80-\x87](....)" + re.escape(FLOAT_100) +
        rb"\xe8(....)\xc7[\x80-\x87](....)" + re.escape(FLOAT_M100))
    found = []
    for match in pattern.finditer(region):
        call1 = struct.unpack("<i", match.group(1))[0]
        call2 = struct.unpack("<i", match.group(3))[0]
        d1 = struct.unpack("<i", match.group(2))[0]
        d2 = struct.unpack("<i", match.group(4))[0]
        at1 = match.start()
        at2 = match.start() + 1 + 4 + 1 + 1 + 4 + 4
        target1 = at1 + 5 + call1
        target2 = at2 + 5 + call2
        if target1 == target2 and d2 == d1 + 4:
            found.append((text_rva + target1, d1))
    return found


def sweep(data, text_lo, text_hi, text_rva, image_base, window):
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from capstone.x86 import X86_OP_MEM, X86_REG_RIP, X86_REG_RSP, X86_REG_RBP

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    md.skipdata = True
    lo, hi = window
    by_disp = defaultdict(list)
    skip = (0, X86_REG_RIP, X86_REG_RSP, X86_REG_RBP)
    for ins in md.disasm(data[text_lo:text_hi], image_base + text_rva):
        if ins.id == 0:
            continue
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base not in skip and lo <= op.mem.disp <= hi:
                by_disp[op.mem.disp].append(
                    (ins.address - image_base, ins.mnemonic, ins.op_str))
    return by_disp


def width_matches(kind, mnemonic, operands):
    if kind == "bool":
        return "byte ptr" in operands
    if kind == "u32":
        return "dword ptr" in operands
    if kind == "f32":
        return "dword ptr" in operands and "ss" in mnemonic
    if kind == "f64":
        return mnemonic.endswith("sd") and "xmm" in operands
    if kind == "ptr":
        return "qword ptr" in operands or "xmmword ptr" in operands or mnemonic == "lea"
    return False


def main():
    try:
        import pefile  # noqa: F401
        import capstone  # noqa: F401
    except ImportError:
        sys.exit("needs `pip install capstone pefile`")
    import pefile

    arguments = sys.argv[1:]
    shifts = {}
    while "--shift" in arguments:
        at = arguments.index("--shift")
        name, _, delta = arguments[at + 1].partition("=")
        shifts[name] = int(delta)
        del arguments[at:at + 2]
    dll = find_dll(arguments[0] if arguments else None)
    data = dll.read_bytes()
    pe = pefile.PE(str(dll), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Name.startswith(b".text"))
    lo, hi = text.PointerToRawData, text.PointerToRawData + text.SizeOfRawData

    anchors = find_anchor(data, lo, hi, base, text.VirtualAddress)
    if not anchors:
        sys.exit("could not find State's constructor (lastMipBias = 100.0f)")
    instances = {a for a, _ in anchors}
    offsets = {d for _, d in anchors}
    if len(instances) != 1 or len(offsets) != 1:
        sys.exit(f"ambiguous anchor: {anchors}")
    instance_rva, anchor_disp = anchors[0]
    change_backend = anchor_disp - ANCHOR_REL
    print(f"State::Instance() at RVA {instance_rva:#x}; lastMipBias at +{anchor_disp:#x}, "
          f"so changeBackend at +{change_backend:#x}")

    by_disp = sweep(data, lo, hi, text.VirtualAddress, base,
                    (change_backend + WINDOW[0], change_backend + WINDOW[1]))
    print(f"{sum(len(v) for v in by_disp.values())} memory operands in "
          f"[{change_backend + WINDOW[0]:#x}, {change_backend + WINDOW[1]:#x}]\n")

    failures = 0
    for name, rel, kind in TABLE:
        disp = change_backend + rel + shifts.get(name, 0)
        hits = [(a, m, o) for a, m, o in by_disp.get(disp, []) if width_matches(kind, m, o)]
        mark = "ok  " if hits else "MISS"
        failures += 0 if hits else 1
        sample = f"  e.g. rva {hits[0][0]:#x}: {hits[0][1]} {hits[0][2]}" if hits else ""
        print(f"[{mark}] {name:32s} +{disp:#06x} {kind:5s} {len(hits):3d} access(es){sample}")
    print(f"\n{len(TABLE) - failures}/{len(TABLE)} members have an access of the right width")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
