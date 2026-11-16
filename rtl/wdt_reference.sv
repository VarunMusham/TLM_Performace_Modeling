// Independent clocked reference derived from docs/WDT_SPEC.md.
// The testbench supplies a one-entry bus bridge; no PEQ or TLM code is reused.
`timescale 1ns/1ps
module wdt_reference(
    input logic clk, reset_n, pending,
    input time ready_tick,
    input logic [1:0] command,
    input logic [63:0] address,
    input logic [31:0] write_data, length, width,
    input logic byte_enable,
    output logic responded, cancelled, expired_pulse, reset_pulse,
    output integer status,
    output logic [31:0] read_data,
    output logic irq, reset_request
);
    logic [2:0] control = 0, next_control;
    logic [31:0] reload = 4, counter = 0, next_reload, next_counter;
    logic expired = 0, next_expired;
    logic reset_seen = 0, cancel_pending = 0;
    logic reload_now, valid_write;
    logic commit;
    integer decoded_status;
    logic [31:0] decoded_read;

    // Decode the bus separately from the watchdog transition equations.
    always_comb begin
        decoded_status = 1;
        decoded_read = write_data;
        if (command > 1) decoded_status = -3;
        else if (length != 4 || width < 4) decoded_status = -4;
        else if (byte_enable) decoded_status = -5;
        else if (!(address == 0 || address == 4 || address == 8 || address == 12 || address == 16)) decoded_status = -2;
        else if (command == 0) begin
            case (address)
                0: decoded_read = {29'b0, control};
                4: decoded_read = reload;
                8: decoded_read = counter;
                16: decoded_read = {31'b0, expired};
                default: decoded_status = -3;
            endcase
        end else begin
            case (address)
                0: if (write_data > 7) decoded_status = -1;
                4: if (write_data == 0) decoded_status = -1;
                8: decoded_status = -3;
                12: if (write_data != 32'hA5A55A5A) decoded_status = -1;
                16: if (write_data > 1) decoded_status = -1;
            endcase
        end
    end

    always @(posedge clk) begin
        commit = pending && ($time > ready_tick);
        next_control = control;
        next_reload = reload;
        next_expired = expired;
        next_counter = counter;
        valid_write = reset_n && commit && !cancel_pending && decoded_status == 1 && command == 1;
        reload_now = valid_write && ((address == 0 && !control[0] && write_data[0]) || address == 12);
        if (valid_write) begin
            if (address == 0) next_control = write_data[2:0];
            if (address == 4) next_reload = write_data;
            if (address == 16 && write_data[0]) next_expired = 0;
        end
        if (reload_now) begin
            next_counter = next_control[0] ? reload : 0;
            next_expired = 0;
        end else if (!next_control[0]) next_counter = 0;
        else if (counter != 0) begin
            next_counter = counter - 1;
            if (counter == 1) next_expired = 1;
        end
        if (!reset_n) begin
            next_control = 0;
            next_reload = 4;
            next_counter = 0;
            next_expired = 0;
        end
        control <= next_control;
        reload <= next_reload;
        counter <= next_counter;
        expired <= next_expired;
        irq <= next_expired && next_control[1];
        reset_request <= next_expired && next_control[2];
        reset_pulse <= !reset_n && !reset_seen;
        reset_seen <= !reset_n;
        expired_pulse <= reset_n && !reload_now && next_control[0] && counter == 1;
        responded <= commit;
        cancelled <= commit && (cancel_pending || !reset_n);
        status <= (cancel_pending || !reset_n) ? -1 : decoded_status;
        read_data <= (cancel_pending || !reset_n || decoded_status != 1) ? write_data : decoded_read;
        if (commit) cancel_pending <= 0;
        else if (!reset_n && pending) cancel_pending <= 1;
    end
endmodule
