// Which entry of OptiScaler's FFX upscaler version list is the one that can run
// the FSR 4.1.2 INT8 Lite model.
//
// Pure C++ with no Windows dependency, so scripts/selftest.py compiles and runs
// asi/test_lite_select.cpp natively against it.
//
// The lists are not fixed. OptiScaler builds them per game from what the FFX
// runtime reports, and:
//   * DX12: the SDK's own versions plus the driver's FSR 4, inserted by version,
//     newest first -- so the SDK's 4.1.1 sits just below the driver's 4.1.2.
//   * Vulkan: the SDK's versions (2.3.3, 3.1.4 -- nothing with FSR 4) with the
//     driver's FSR 4 *appended*, so index 0 is an FSR 3 and the one wanted is
//     last.
// The Lite model exists only in AMD's driver library, which is 4.1.2 or newer,
// and the SDK's FSR 4 (4.1.1) does not have it. So the rule is by version, not
// by position: the highest entry that is at least 4.1.2.
#pragma once

#include <stdio.h>
#include <string.h>

namespace litesel {

struct Version {
    unsigned major, minor, patch;
    bool ok;
};

// The first version AMD's library carries INT8 Lite in.
static const Version kMinLite = { 4, 1, 2, true };

/** "4.1.2", "FSR 4.1.2", "4.1.2 *" all read as 4.1.2, the way OptiScaler's own parser does. */
inline Version Parse(const char* text) {
    for (const char* p = text; *p; ++p) {
        if (*p < '0' || *p > '9') continue;
        unsigned a = 0, b = 0, c = 0;
        if (sscanf(p, "%u.%u.%u", &a, &b, &c) == 3) return { a, b, c, true };
    }
    return { 0, 0, 0, false };
}

inline bool Less(const Version& a, const Version& b) {
    if (a.major != b.major) return a.major < b.major;
    if (a.minor != b.minor) return a.minor < b.minor;
    return a.patch < b.patch;
}

/** The index of the highest version in the list, or -1. Ties keep the first. */
template <size_t NameLen>
inline int HighestIndex(const char (*names)[NameLen], int count) {
    int best = -1;
    Version bestVersion = { 0, 0, 0, false };
    for (int i = 0; i < count; i++) {
        Version v = Parse(names[i]);
        if (!v.ok) continue;
        if (best < 0 || Less(bestVersion, v)) { best = i; bestVersion = v; }
    }
    return best;
}

/** The entry that can run INT8 Lite, or -1 when the list has none new enough. */
template <size_t NameLen>
inline int PickLiteIndex(const char (*names)[NameLen], int count) {
    int best = HighestIndex(names, count);
    if (best < 0) return -1;
    return Less(Parse(names[best]), kMinLite) ? -1 : best;
}

}  // namespace litesel
