#include "wdt.hpp"
#include <tlm_utils/simple_initiator_socket.h>
#include <iostream>
#include <stdexcept>

using namespace sc_core;
using tlm_lab::wdt;

class testbench : public sc_module {
public:
    tlm_utils::simple_initiator_socket<testbench> initiator{"initiator"};
    sc_in<bool> irq{"irq"}, reset_request{"reset_request"};
    sc_out<bool> reset_n{"reset_n"};
    bool passed = false;

    SC_HAS_PROCESS(testbench);
    testbench(sc_module_name name, std::string scenario)
        : sc_module(name), scenario_(std::move(scenario)) {
        SC_THREAD(run);
        SC_THREAD(reset_driver);
    }

private:
    std::string scenario_;
    sc_event reset_during_request_;

    void require(bool condition, const char* message) {
        if (!condition) throw std::runtime_error(message);
    }

    std::uint32_t transfer(tlm::tlm_command command, std::uint64_t address,
                          std::uint32_t value = 0, unsigned delay_ns = 0,
                          tlm::tlm_response_status expected = tlm::TLM_OK_RESPONSE,
                          unsigned length = 4, bool byte_enable = false) {
        unsigned char data[4];
        for (unsigned i = 0; i < 4; ++i) data[i] = static_cast<unsigned char>(value >> (8 * i));
        unsigned char enable[4] = {0xff, 0xff, 0xff, 0xff};
        tlm::tlm_generic_payload p;
        p.set_command(command);
        p.set_address(address);
        p.set_data_ptr(data);
        p.set_data_length(length);
        p.set_streaming_width(4);
        if (byte_enable) { p.set_byte_enable_ptr(enable); p.set_byte_enable_length(4); }
        sc_time delay(delay_ns, SC_NS);
        initiator->b_transport(p, delay);
        require(p.get_response_status() == expected, "Unexpected TLM response");
        require(delay == SC_ZERO_TIME, "Elapsed delay was returned twice");
        require(!p.is_dmi_allowed(), "DMI must remain disabled");
        value = 0;
        for (unsigned i = 0; i < 4; ++i) value |= std::uint32_t(data[i]) << (8 * i);
        return value;
    }

    void arm() {
        transfer(tlm::TLM_WRITE_COMMAND, wdt::LOAD, 3); // submit 11, ready 26, commit 30
        require(sc_time_stamp() == sc_time(30, SC_NS), "LOAD timing mismatch");
        transfer(tlm::TLM_WRITE_COMMAND, wdt::CTRL, 7); // ready 45, commit 50
        require(sc_time_stamp() == sc_time(50, SC_NS), "ENABLE timing mismatch");
    }

    void reset_driver() {
        reset_n.write(false);
        wait(11, SC_NS); // includes the first rising edge at 10 ns
        reset_n.write(true);
        wait(reset_during_request_);
        wait(5, SC_NS);
        reset_n.write(false);
        wait(30, SC_NS);
        reset_n.write(true);
    }

    void run() {
        wait(11, SC_NS);
        wait(SC_ZERO_TIME);
        if (scenario_ == "expiry") {
            arm();
            wait(29, SC_NS);
            require(!irq.read() && !reset_request.read(), "Early expiry");
            wait(2, SC_NS);
            require(irq.read() && reset_request.read(), "Missing expiry at 80 ns");
            require(transfer(tlm::TLM_READ_COMMAND, wdt::STATUS) == 1, "Missing sticky status");
            transfer(tlm::TLM_WRITE_COMMAND, wdt::STATUS, 1);
            require(!irq.read() && !reset_request.read(), "W1C did not clear outputs");
            wait(30, SC_NS);
            require(!irq.read(), "Expired timer incorrectly retriggered");
        } else if (scenario_ == "kick_boundary") {
            arm();
            wait(10, SC_NS);
            transfer(tlm::TLM_WRITE_COMMAND, wdt::KICK, wdt::KICK_KEY);
            require(sc_time_stamp() == sc_time(80, SC_NS), "Kick did not commit on expiry edge");
            require(!irq.read(), "Expiry won over same-edge kick");
            wait(29, SC_NS);
            require(!irq.read(), "Kicked timer expired early");
            wait(2, SC_NS);
            require(irq.read(), "Kicked timer did not expire at 110 ns");
        } else if (scenario_ == "disable_boundary") {
            arm();
            wait(10, SC_NS);
            transfer(tlm::TLM_WRITE_COMMAND, wdt::CTRL, 6);
            require(sc_time_stamp() == sc_time(80, SC_NS), "Disable timing mismatch");
            wait(40, SC_NS);
            require(!irq.read() && !reset_request.read(), "Disabled timer expired");
            require(transfer(tlm::TLM_READ_COMMAND, wdt::COUNT) == 0, "Disable did not clear count");
        } else if (scenario_ == "reset_pending") {
            reset_during_request_.notify(SC_ZERO_TIME);
            transfer(tlm::TLM_WRITE_COMMAND, wdt::LOAD, 9, 0, tlm::TLM_GENERIC_ERROR_RESPONSE);
            require(sc_time_stamp() == sc_time(30, SC_NS), "Cancelled request timing changed");
            wait(20, SC_NS);
            require(transfer(tlm::TLM_READ_COMMAND, wdt::LOAD) == 4, "Cancelled write survived reset");
            require(!irq.read() && !reset_request.read(), "Reset left outputs asserted");
        } else if (scenario_ == "annotated_delay") {
            require(transfer(tlm::TLM_READ_COMMAND, wdt::LOAD, 0, 7) == 4, "Bad reset LOAD");
            require(sc_time_stamp() == sc_time(40, SC_NS), "Incoming delay was not consumed exactly once");
        } else if (scenario_ == "peq_on_edge") {
            transfer(tlm::TLM_WRITE_COMMAND, wdt::LOAD, 3, 4); // ready 30, commit 40
            require(sc_time_stamp() == sc_time(40, SC_NS), "Same-time PEQ/clock ordering affected commit");
        } else if (scenario_ == "read_counter") {
            arm();
            wait(1, SC_NS);
            require(transfer(tlm::TLM_READ_COMMAND, wdt::COUNT) == 2, "COUNT was not sampled before decrement");
            require(sc_time_stamp() == sc_time(70, SC_NS), "COUNT read timing mismatch");
            wait(11, SC_NS);
            require(irq.read(), "Read changed expiry timing");
        } else if (scenario_ == "invalid") {
            transfer(tlm::TLM_WRITE_COMMAND, wdt::LOAD, 0, 0, tlm::TLM_GENERIC_ERROR_RESPONSE);
            transfer(tlm::TLM_WRITE_COMMAND, wdt::COUNT, 1, 0, tlm::TLM_COMMAND_ERROR_RESPONSE);
            transfer(tlm::TLM_READ_COMMAND, 3, 0, 0, tlm::TLM_ADDRESS_ERROR_RESPONSE);
            transfer(tlm::TLM_READ_COMMAND, wdt::LOAD, 0, 0, tlm::TLM_BURST_ERROR_RESPONSE, 2);
            transfer(tlm::TLM_READ_COMMAND, wdt::LOAD, 0, 0, tlm::TLM_BYTE_ENABLE_ERROR_RESPONSE, 4, true);
            transfer(tlm::TLM_WRITE_COMMAND, wdt::KICK, 1, 0, tlm::TLM_GENERIC_ERROR_RESPONSE);
            transfer(tlm::TLM_WRITE_COMMAND, wdt::CTRL, 8, 0, tlm::TLM_GENERIC_ERROR_RESPONSE);
            require(transfer(tlm::TLM_READ_COMMAND, wdt::LOAD) == 4, "Invalid access changed LOAD");
            require(transfer(tlm::TLM_READ_COMMAND, wdt::CTRL) == 0, "Invalid access changed CTRL");
        } else {
            throw std::runtime_error("Unknown scenario: " + scenario_);
        }
        passed = true;
        sc_stop();
    }
};

int sc_main(int argc, char* argv[]) {
    try {
        const std::string scenario = argc > 1 ? argv[1] : "expiry";
        const std::string trace_path = argc > 2 ? argv[2] : "wdt_trace.csv";
        sc_set_time_resolution(1, SC_NS);
        tlm_lab::trace_sink trace(trace_path);
        sc_clock clk("clk", sc_time(10, SC_NS), 0.5, sc_time(10, SC_NS), true);
        sc_signal<bool> reset_n("reset_n"), irq("irq"), reset_request("reset_request");
        wdt dut("wdt", sc_time(15, SC_NS), trace);
        testbench tb("testbench", scenario);
        dut.clk(clk); dut.reset_n(reset_n); dut.irq(irq); dut.reset_request(reset_request);
        tb.initiator.bind(dut.regs);
        tb.reset_n(reset_n); tb.irq(irq); tb.reset_request(reset_request);
        sc_start(10, SC_US); // independent simulation-time watchdog
        trace.finish();
        if (!tb.passed) throw std::runtime_error("Scenario did not finish before simulated deadline");
        std::cout << "PASS " << scenario << "; " << sc_version()
                  << "; resolution=" << sc_get_time_resolution() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}

