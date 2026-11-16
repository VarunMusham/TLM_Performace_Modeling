#include "wdt.hpp"
#include <stdexcept>

namespace tlm_lab {

trace_sink::trace_sink(const std::string& path, std::uint64_t limit) : enabled_(path != "-"), limit_(limit) {
    if (!enabled_) return;
    stream_.open(path);
    if (!stream_) throw std::runtime_error("Cannot open trace: " + path);
    stream_ << "tick,delta,sequence,event,transaction_id,address,value\n";
}

void trace_sink::emit(const char* event, std::uint64_t id,
                      std::uint64_t address, std::uint32_t value) {
    ++sequence_;
    // An allocation-free semantic digest also runs in trace-off mode.
    auto mix = [&](std::uint64_t number) {
        for (unsigned i = 0; i < 8; ++i) {
            fingerprint_ ^= (number >> (8*i)) & 255u;
            fingerprint_ *= 1099511628211ull;
        }
    };
    for (const char* c = event; *c; ++c) { fingerprint_ ^= *c; fingerprint_ *= 1099511628211ull; }
    mix(sc_core::sc_time_stamp().value()); mix(id); mix(address); mix(value);
    if (!enabled_) return;
    if (limit_ && sequence_ > limit_) throw std::runtime_error("Trace event limit exceeded; evidence incomplete");
    stream_ << sc_core::sc_time_stamp().value() << ',' << sc_core::sc_delta_count()
            << ',' << sequence_ << ',' << event << ',' << id << ',' << address
            << ',' << value << '\n';
    if (!stream_) throw std::runtime_error("Trace write failed");
}

void trace_sink::finish() {
    if (!enabled_) return;
    stream_.flush();
    if (!stream_) throw std::runtime_error("Trace flush failed");
}

wdt::wdt(sc_core::sc_module_name name, sc_core::sc_time bus_latency, trace_sink& trace)
    : sc_module(name), bus_latency_(bus_latency), trace_(trace) {
    regs.register_b_transport(this, &wdt::b_transport);
    irq.initialize(false);
    reset_request.initialize(false);
    SC_THREAD(receive_ready);
    SC_METHOD(tick);
    sensitive << clk.pos();
    dont_initialize();
}

void wdt::b_transport(tlm::tlm_generic_payload& payload, sc_core::sc_time& delay) {
    payload.set_dmi_allowed(false);
    if (active_ != nullptr) {
        payload.set_response_status(tlm::TLM_GENERIC_ERROR_RESPONSE);
        delay = sc_core::SC_ZERO_TIME;
        SC_REPORT_ERROR("wdt", "Pilot supports one outstanding blocking request");
        return;
    }
    // Caller retains the payload throughout the blocking call. The context lives
    // until the PEQ entry has been consumed and the clock process completes it.
    request req(payload, next_id_++, sc_core::sc_time_stamp() + delay + bus_latency_);
    active_ = &req;
    payload.set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);
    trace_.emit("submit", req.id, payload.get_address());
    peq_.notify(req, delay + bus_latency_);
    sc_core::wait(req.done);
    delay = sc_core::SC_ZERO_TIME; // All elapsed time has already been consumed.
}

void wdt::receive_ready() {
    while (true) {
        sc_core::wait(peq_.get_event());
        while (auto* req = peq_.get_next_transaction()) {
            req->ready = true;
            trace_.emit("peq_ready", req->id, req->payload.get_address());
        }
    }
}

bool wdt::access(request& req) {
    auto& p = req.payload;
    const auto address = p.get_address();
    auto fail = [&](tlm::tlm_response_status status) {
        p.set_response_status(status);
        trace_.emit("access_error", req.id, address);
        return false;
    };
    if (p.get_command() != tlm::TLM_READ_COMMAND && p.get_command() != tlm::TLM_WRITE_COMMAND)
        return fail(tlm::TLM_COMMAND_ERROR_RESPONSE);
    if (p.get_data_ptr() == nullptr || p.get_data_length() != 4 || p.get_streaming_width() < 4)
        return fail(tlm::TLM_BURST_ERROR_RESPONSE);
    if (p.get_byte_enable_ptr() != nullptr) return fail(tlm::TLM_BYTE_ENABLE_ERROR_RESPONSE);
    if (address != CTRL && address != LOAD && address != COUNT && address != KICK && address != STATUS)
        return fail(tlm::TLM_ADDRESS_ERROR_RESPONSE);

    std::uint32_t value = 0;
    bool reloaded = false;
    if (p.is_read()) {
        switch (address) {
        case CTRL: value = ctrl_; break;
        case LOAD: value = load_; break;
        case COUNT: value = count_; break;
        case STATUS: value = expired_ ? 1 : 0; break;
        default: return fail(tlm::TLM_COMMAND_ERROR_RESPONSE);
        }
        for (unsigned i = 0; i < 4; ++i) p.get_data_ptr()[i] = static_cast<unsigned char>(value >> (8 * i));
    } else {
        for (unsigned i = 0; i < 4; ++i) value |= std::uint32_t(p.get_data_ptr()[i]) << (8 * i);
        switch (address) {
        case CTRL: {
            if (value & ~7u) return fail(tlm::TLM_GENERIC_ERROR_RESPONSE);
            const bool enabling = !(ctrl_ & ENABLE) && (value & ENABLE);
            ctrl_ = value;
            if (!(ctrl_ & ENABLE)) count_ = 0;
            if (enabling) { count_ = load_; expired_ = false; reloaded = true; }
            break;
        }
        case LOAD:
            if (value == 0) return fail(tlm::TLM_GENERIC_ERROR_RESPONSE);
            load_ = value;
            break;
        case KICK:
            if (value != KICK_KEY) return fail(tlm::TLM_GENERIC_ERROR_RESPONSE);
            count_ = (ctrl_ & ENABLE) ? load_ : 0;
            expired_ = false;
            reloaded = true;
            break;
        case STATUS:
            if (value & ~1u) return fail(tlm::TLM_GENERIC_ERROR_RESPONSE);
            if (value & 1u) expired_ = false;
            break;
        default: return fail(tlm::TLM_COMMAND_ERROR_RESPONSE);
        }
    }
    p.set_response_status(tlm::TLM_OK_RESPONSE);
    trace_.emit(p.is_read() ? "commit_read" : "commit_write", req.id, address, value);
    return reloaded;
}

void wdt::update_outputs() {
    const bool next_irq = expired_ && (ctrl_ & IRQ_ENABLE);
    const bool next_reset = expired_ && (ctrl_ & RESET_ENABLE);
    if (next_irq != irq_value_) trace_.emit("irq", 0, 0, next_irq);
    if (next_reset != reset_value_) trace_.emit("reset_request", 0, 0, next_reset);
    irq_value_ = next_irq;
    reset_value_ = next_reset;
    irq.write(next_irq);
    reset_request.write(next_reset);
}

void wdt::tick() {
    const bool resetting = !reset_n.read();
    if (resetting) {
        if (!in_reset_) trace_.emit("reset");
        ctrl_ = 0;
        load_ = 4;
        count_ = 0;
        expired_ = false;
        if (active_) active_->cancelled = true;
    }
    in_reset_ = resetting;

    bool reloaded = false;
    request* completed = nullptr;
    // Strictly later than PEQ readiness: deterministic even when readiness and
    // a clock edge share a timestamp and their process execution order differs.
    if (active_ && active_->ready && active_->ready_at < sc_core::sc_time_stamp()) {
        completed = active_;
        if (completed->cancelled) {
            completed->payload.set_response_status(tlm::TLM_GENERIC_ERROR_RESPONSE);
            trace_.emit("reset_cancel", completed->id, completed->payload.get_address());
        } else {
            reloaded = access(*completed);
        }
        active_ = nullptr;
    }
    if (!resetting && !reloaded && (ctrl_ & ENABLE) && count_ > 0) {
        if (--count_ == 0) {
            expired_ = true;
            trace_.emit("expiry");
        }
    }
    update_outputs();
    if (completed) completed->done.notify(sc_core::SC_ZERO_TIME);
}

} // namespace tlm_lab

