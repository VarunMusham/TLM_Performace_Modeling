#pragma once
#include <cstdint>
// Replace this synthetic service model with your existing IP.
struct service_model {
    std::uint64_t latency;
    std::uint64_t completion(std::uint64_t accepted) const { return accepted + latency; }
};
