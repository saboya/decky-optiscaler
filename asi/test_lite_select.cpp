// Native test for lite_select.h. Run by scripts/selftest.py; exits non-zero on
// the first wrong answer and says which.
#include <stdio.h>
#include <string.h>

#include "lite_select.h"

static int g_failed = 0;

#define LIST(...) \
    static const char names[][32] = { __VA_ARGS__ }; \
    const int count = (int) (sizeof(names) / sizeof(names[0]))

#define CHECK(what, got, want) do { \
    int g = (got), w = (want); \
    if (g != w) { printf("FAIL %s: got %d, want %d\n", what, g, w); g_failed++; } \
    else printf("ok   %s\n", what); } while (0)

int main() {
    using namespace litesel;

    { // Vulkan: SDK versions first, the driver's FSR 4 appended last.
        LIST("3.1.4", "2.3.3", "4.1.2");
        CHECK("vulkan: the appended driver entry is chosen, not index 0", PickLiteIndex(names, count), 2);
    }
    { // DX12: driver 4.1.2 inserted above the SDK's 4.1.1.
        LIST("4.1.2", "4.1.1", "3.1.5", "2.3.4");
        CHECK("dx12: the driver's 4.1.2 beats the SDK's 4.1.1", PickLiteIndex(names, count), 0);
    }
    { // DX12 with no driver library: only the SDK's FSR 4, which has no Lite model.
        LIST("4.1.1", "3.1.5", "2.3.4");
        CHECK("dx12 without the driver DLL: 4.1.1 is refused, not silently chosen", PickLiteIndex(names, count), -1);
        CHECK("...though it is still the highest entry", HighestIndex(names, count), 0);
    }
    { // Vulkan with no driver library at all.
        LIST("3.1.4", "2.3.3");
        CHECK("vulkan without the driver DLL: nothing is new enough", PickLiteIndex(names, count), -1);
    }
    { // A newer driver than the one this was written for still qualifies.
        LIST("3.1.4", "2.3.3", "4.2.0");
        CHECK("a newer driver library is accepted", PickLiteIndex(names, count), 2);
    }
    { // 4.1.10 is newer than 4.1.9 -- compared as numbers, not text.
        LIST("4.1.9", "4.1.10", "4.1.2");
        CHECK("versions compare as numbers, not strings", PickLiteIndex(names, count), 1);
    }
    { // Decorated names, as OptiScaler's own parser tolerates.
        LIST("FSR 3.1.4", "FSR 4.1.2 *");
        CHECK("a prefix and a trailing mark do not matter", PickLiteIndex(names, count), 1);
    }
    { // Equal entries: the first wins, so a repeat never moves the choice.
        LIST("4.1.2", "4.1.2");
        CHECK("ties keep the first entry", PickLiteIndex(names, count), 0);
    }
    { // Entries that do not parse are skipped, not fatal.
        LIST("", "garbage", "4.1.2", "x.y.z");
        CHECK("unparseable names are skipped", PickLiteIndex(names, count), 2);
    }
    {
        static const char names[1][32] = { "4.1.2" };
        CHECK("an empty list picks nothing", PickLiteIndex(names, 0), -1);
        CHECK("a single entry that qualifies", PickLiteIndex(names, 1), 0);
    }

    Version v = Parse("4.1.2");
    CHECK("parse: major", (int) v.major, 4);
    CHECK("parse: minor", (int) v.minor, 1);
    CHECK("parse: patch", (int) v.patch, 2);
    CHECK("parse: junk is not ok", Parse("nothing here").ok ? 1 : 0, 0);

    printf(g_failed ? "\n%d failed\n" : "\nall passed\n", g_failed);
    return g_failed ? 1 : 0;
}
