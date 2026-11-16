"""Generate a common-intent testbench and import independent RTL observations."""
from pathlib import Path
import shutil
from .config import address, require
from .events import read_pilot, normalize, write_jsonl, validate_lifecycles
from .runner import ROOT, process


def testbench(c):
    clock, m = c["clock"], c["measurement"]
    reset_lines, last = [], 0
    for change in c["reset"]:
        tick = int(change["tick"])
        reset_lines.append(f"#{tick-last} reset_n = 1'b{int(change['reset_n'])};")
        last = tick
    calls = []
    for i, op in enumerate(c["workload"], 1):
        relative = "after_completion_of" in op
        calls.append("issue(" + ",".join(map(str, [i, {"read32": 0, "write32": 1, "ignore": 2}[op["op"]],
            int(relative), op.get("offset_tick", 0) if relative else op["offer_tick"],
            f"64'd{address(op['address'])}", f"32'd{op.get('value', 0)}", op.get("delay_tick", 0),
            op.get("length", 4), op.get("streaming_width", 4), int(op.get("byte_enable", False))])) + ");")
    return r'''`timescale 1ns/1ps
module tb;
    reg clk = 0, reset_n = 0, pending = 0, commit = 0;
    reg [1:0] command = 0;
    reg [63:0] address = 0;
    reg [31:0] write_data = 0, length = 4, width = 4;
    reg byte_enable = 0;
    time ready_tick = 0;
    wire responded, cancelled, expired_pulse, reset_pulse, irq, reset_request;
    wire [31:0] read_data;
    wire signed [31:0] status;
    wdt_reference dut(.*);
    integer trace_file, response_file, seq = 0, txid = 0;
    reg previous_irq = 0, previous_reset = 0, done = 0;
    event completion;
    task emit(input string kind, input integer id, input reg [63:0] addr, input reg [31:0] value);
        seq = seq + 1;
        $fdisplay(trace_file, "%0d,0,%0d,%0s,%0d,%0d,%0d", $time, seq, kind, id, addr, value);
    endtask
    task issue(input integer id, input integer cmd, input integer relative_offer, input time at_tick,
               input reg [63:0] addr, input reg [31:0] data, input time annotation,
               input reg [31:0] len, input reg [31:0] stream_width, input reg be);
        if (relative_offer) #(at_tick);
        else if (at_tick > $time) #(at_tick - $time);
        txid = id; command = cmd; address = addr; write_data = data;
        length = len; width = stream_width; byte_enable = be;
        pending = 1;
        ready_tick = $time + annotation + LATENCY;
        emit("submit", txid, address, 0);
        #(annotation + LATENCY);
        emit("peq_ready", txid, address, 0);
        @completion;
    endtask
    initial begin
        trace_file = $fopen("rtl.csv", "w");
        response_file = $fopen("rtl_responses.csv", "w");
        if (!trace_file || !response_file) $fatal(1, "Trace open failed");
        $fdisplay(trace_file, "tick,delta,sequence,event,transaction_id,address,value");
        $fdisplay(response_file, "transaction_id,tick,status,value");
    end
    initial begin
        #FIRST;
        forever begin
            // Simulation-only bus bridge decides eligibility before the core edge.
            // The reference core contains no $time or transport scheduling logic.
            commit = pending && ($time > ready_tick);
            clk = 1;
            #(PERIOD/2) clk = 0;
            #(PERIOD/2);
        end
    end
    initial begin
        RESET_SEQUENCE
    end
    initial begin
        OPERATIONS
        done = 1;
    end
    always @(posedge clk) begin
        // Sample after NBA updates. $time remains the integer architectural edge.
        #0.001;
        if (reset_pulse) emit("reset", 0, 0, 0);
        if (responded) begin
            if (cancelled) emit("reset_cancel", txid, address, 0);
            else if (status != 1) emit("access_error", txid, address, 0);
            else emit(command == 0 ? "commit_read" : "commit_write", txid, address, read_data);
            $fdisplay(response_file, "%0d,%0d,%0d,%0d", txid, $time, status, read_data);
        end
        if (expired_pulse) emit("expiry", 0, 0, 0);
        if (irq !== previous_irq) emit("irq", 0, 0, {31'b0, irq});
        if (reset_request !== previous_reset) emit("reset_request", 0, 0, {31'b0, reset_request});
        previous_irq = irq; previous_reset = reset_request;
        if (responded) begin pending = 0; ->completion; end
    end
    initial begin
        #DRAIN; #0.010;
        $fclose(trace_file); $fclose(response_file);
        if (!done) $fatal(1, "Drain deadline exceeded");
        $finish;
    end
endmodule
'''.replace("LATENCY", str(c["parameters"]["bus_latency_tick"])).replace("FIRST", str(clock["first_rising_tick"])) \
   .replace("PERIOD", str(clock["period_tick"])).replace("DRAIN", str(m["drain_deadline_tick"])) \
   .replace("RESET_SEQUENCE", "\n".join(reset_lines)).replace("OPERATIONS", "\n".join(calls))


def run_reference(c, directory, timeout, records, iverilog="iverilog", vvp="vvp"):
    require(shutil.which(str(iverilog)) and shutil.which(str(vvp)), "Icarus iverilog/vvp are required for RTL comparison")
    shutil.copy2(ROOT/"rtl"/"wdt_reference.sv", directory/"wdt_reference.sv")
    (directory/"rtl_tb.sv").write_text(testbench(c), encoding="ascii")
    for stem, command in [("rtl_build", [iverilog, "-g2012", "-s", "tb", "-o", "reference.vvp", "wdt_reference.sv", "rtl_tb.sv"]),
                          ("rtl_simulation", [vvp, "reference.vvp"])]:
        result = process(command, directory, stem, timeout)
        records.append(result)
        require(not result["timed_out"] and result["exit_code"] == 0, f"{stem} failed; inspect {stem}.stderr.log")
    events = normalize(read_pilot(directory/"rtl.csv"), c, directory.name, "rtl")
    write_jsonl(directory/"rtl.events.jsonl", events)
    # Contract disagreements are accuracy failures, not experiment launch failures.
    # The comparator (rather than the importer) diagnoses missing/timing events.
    return events
