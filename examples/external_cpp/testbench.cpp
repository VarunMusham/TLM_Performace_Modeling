#include "model.hpp"
#include "tlm_trace.hpp"
#include <iostream>
int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::runtime_error("Usage: ip_demo output service_tick count drain");
        tlm_lab::transaction_trace trace(argv[1]);
        service_model model{std::stoull(argv[2])};
        const auto count = std::stoull(argv[3]), drain = std::stoull(argv[4]);
        std::uint64_t tick = 0;
        for (std::uint64_t i = 0; i < count; ++i) {
            const auto id = "request_" + std::to_string(i);
            trace.emit(tick, "offer", id, 64);
            trace.emit(tick, "accept", id, 64);
            tick = model.completion(tick);
            if (tick > drain) throw std::runtime_error("Drain deadline exceeded");
            trace.emit(tick, "complete", id, 64);
        }
        trace.finish(drain);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
