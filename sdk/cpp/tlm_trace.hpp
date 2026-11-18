#pragma once
// Standalone C++14 observer. Pass integer model ticks; no SystemC dependency.
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>

namespace tlm_lab {
class transaction_trace {
    std::ofstream stream_;
    std::string completion_;
    std::uint64_t count_ = 0, last_tick_ = 0;
public:
    explicit transaction_trace(const std::string& directory)
        : stream_(directory + "/transactions.csv"), completion_(directory + "/completion.json") {
        if (!stream_) throw std::runtime_error("Cannot open transaction trace");
        stream_ << "sequence,tick,event,transaction_id,payload_bytes\n";
    }
    void emit(std::uint64_t tick, const char* event, const std::string& id, std::uint64_t bytes) {
        if (tick < last_tick_) throw std::runtime_error("Trace time moved backwards");
        // IDs in this small writer use safe CSV characters. Use your own CSV
        // escaping/monitor for arbitrary text IDs; the importer accepts CSV.
        if (id.empty() || id.find_first_of(",\r\n\"") != std::string::npos)
            throw std::runtime_error("Invalid trace ID");
        last_tick_ = tick;
        stream_ << ++count_ << ',' << tick << ',' << event << ',' << id << ',' << bytes << '\n';
        if (!stream_) throw std::runtime_error("Trace write failed");
    }
    void finish(std::uint64_t stop_tick) {
        if (stop_tick < last_tick_) throw std::runtime_error("Capture stop precedes last event");
        stream_.flush();
        if (!stream_) throw std::runtime_error("Trace flush failed");
        stream_.close();
        std::ofstream result(completion_);
        result << "{\"schema_version\":\"capture-1\",\"finished\":true,\"event_count\":" << count_
               << ",\"loss_count\":0,\"stop_tick\":\"" << stop_tick << "\"}\n";
        result.flush();
        if (!result) throw std::runtime_error("Completion marker write failed");
    }
};
}
