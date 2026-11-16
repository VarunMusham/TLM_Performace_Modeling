#pragma once

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_get.h>
#include <cstdint>
#include <fstream>
#include <string>

namespace tlm_lab {

class trace_sink {
public:
    explicit trace_sink(const std::string& path, std::uint64_t limit = 0);
    void emit(const char* event, std::uint64_t id = 0,
              std::uint64_t address = 0, std::uint32_t value = 0);
    void finish();
    std::uint64_t count() const { return sequence_; }
    std::uint64_t fingerprint() const { return fingerprint_; }
private:
    std::ofstream stream_;
    bool enabled_;
    std::uint64_t sequence_ = 0;
    std::uint64_t limit_ = 0;
    std::uint64_t fingerprint_ = 14695981039346656037ull;
};

class wdt : public sc_core::sc_module {
public:
    tlm_utils::simple_target_socket<wdt> regs{"regs"};
    sc_core::sc_in<bool> clk{"clk"};
    sc_core::sc_in<bool> reset_n{"reset_n"};
    sc_core::sc_out<bool> irq{"irq"};
    sc_core::sc_out<bool> reset_request{"reset_request"};

    enum : std::uint32_t {
        CTRL = 0x00, LOAD = 0x04, COUNT = 0x08, KICK = 0x0c, STATUS = 0x10,
        ENABLE = 1, IRQ_ENABLE = 2, RESET_ENABLE = 4, KICK_KEY = 0xa5a55a5a
    };

    SC_HAS_PROCESS(wdt);
    wdt(sc_core::sc_module_name name, sc_core::sc_time bus_latency, trace_sink& trace);

private:
    struct request {
        tlm::tlm_generic_payload& payload;
        std::uint64_t id;
        sc_core::sc_time ready_at;
        sc_core::sc_event done;
        bool ready = false;
        bool cancelled = false;
        request(tlm::tlm_generic_payload& p, std::uint64_t n, sc_core::sc_time t)
            : payload(p), id(n), ready_at(t) {}
    };

    void b_transport(tlm::tlm_generic_payload& payload, sc_core::sc_time& delay);
    void receive_ready();
    void tick();
    bool access(request& req);
    void update_outputs();

    sc_core::sc_time bus_latency_;
    trace_sink& trace_;
    tlm_utils::peq_with_get<request> peq_{"register_peq"};
    request* active_ = nullptr;
    std::uint64_t next_id_ = 1;
    std::uint32_t ctrl_ = 0;
    std::uint32_t load_ = 4;
    std::uint32_t count_ = 0;
    bool expired_ = false;
    bool in_reset_ = false;
    bool irq_value_ = false;
    bool reset_value_ = false;
};

} // namespace tlm_lab

