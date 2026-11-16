# Hybrid WDT pilot specification

This is a small, original test IP. Review these semantics before creating the
independent RTL reference. The model is implemented in
[wdt.cpp](../examples/wdt/wdt.cpp); directed tests are in
[testbench.cpp](../examples/wdt/testbench.cpp).

## Interfaces and hybrid timing

- One 32-bit little-endian TLM register target using `b_transport` from an
  `SC_THREAD`; one outstanding call. The initiator owns the payload until return.
- A configurable bus readiness delay, implemented by `peq_with_get`.
- A positive-edge clock, synchronous active-low reset, and level IRQ/reset-request
  outputs. The reset request is an output for the environment, not self-reset.
- No DMI, debug access, nonblocking interface, byte enables, bursts, or concurrent
  initiators in this pilot. These restrictions do not apply to the future adapter
  framework. A concurrent call is reported as an unsupported-use error.

For a call at time `t` with incoming annotation `d` and bus latency `L`, the PEQ
becomes ready at `r = t + d + L`. The operation commits on the first rising edge
**strictly after** `r`. Register state changes and reads occur at that edge.
`b_transport` returns after the edge's update with delay zero. Thus the caller
must not wait the incoming annotation again after return.

For periodic edges at integer multiples of `P`, commit time is
`(floor(r / P) + 1) * P`, within the active clock sequence. The example has
1 ns resolution, 10 ns clock period, first rising edge at 10 ns, and 15 ns bus
latency. A request at 11 ns is ready at 26 ns and commits at 30 ns. A request
ready at 30 ns commits at 40 ns regardless of process scheduling order.

This strict-edge rule is a deliberate pilot contract. It is not a claim about
an actual APB/AXI implementation. An RTL reference must implement the same rule,
or both models must be revised to a different reviewed bus protocol.

## Register map

All accesses must be aligned, exactly four bytes, with streaming width at least
four and no byte enables. Invalid accesses complete at the normal scheduled
edge with an error; they do not change register state. The watchdog continues
counting during unsuccessful accesses.

| Address | Register | Access | Reset | Semantics |
|---|---|---|---|---|
| 0x00 | CTRL | R/W | 0 | bit 0 ENABLE, bit 1 IRQ_ENABLE, bit 2 RESET_ENABLE |
| 0x04 | LOAD | R/W | 4 | Nonzero unsigned reload count in WDT cycles |
| 0x08 | COUNT | R | 0 | Counter snapshot before that edge's decrement |
| 0x0c | KICK | W | N/A | Key `0xA5A55A5A` reloads and clears expired status |
| 0x10 | STATUS | R/W1C | 0 | Bit 0 EXPIRED; writing 1 clears it |

CTRL reserved bits, STATUS reserved bits, LOAD=0, and incorrect kick keys produce
a generic error. Writes to COUNT and reads of KICK produce command errors.
Unknown/unaligned addresses produce address errors; unsupported widths produce
burst errors; byte enables produce byte-enable errors. No memory contents are
exposed through DMI.

## Counter and output behavior

The ENABLE transition 0->1 loads COUNT from LOAD, clears EXPIRED, and skips
decrement on that edge. A valid KICK does the same while enabled. While disabled,
KICK clears EXPIRED and leaves COUNT zero. Writing LOAD while running changes
the next reload value; it does not change the current count.

On each subsequent enabled rising edge with COUNT>0, decrement once. Reaching
zero sets EXPIRED and emits one expiry event. The count saturates at zero; there
is no auto-reload or repeat expiry. For LOAD=N, expiry is N edges after an
enable/reload edge. A repeated CTRL write with ENABLE already set does not reload.

Disabling clears COUNT but leaves sticky EXPIRED. The output equations are
`irq = EXPIRED && IRQ_ENABLE` and
`reset_request = EXPIRED && RESET_ENABLE`, independent of ENABLE. Thus disable
does not acknowledge an already pending interrupt. W1C clears EXPIRED but does
not reload; a new enable transition or kick is required to restart an expired
counter. Signal values become visible in the SystemC update phase following the
clock method; emitted output events record the decision at that clock edge.

## Same-edge priority and reset

1. Sample reset. If asserted, clear CTRL/COUNT/STATUS and restore LOAD=4.
2. Complete any matured register request. A request that encountered a sampled
   reset while pending is cancelled with an error, even if reset has since ended.
   Otherwise apply its register access and read snapshot.
3. If not resetting or reloading, decrement an enabled nonzero counter.
4. Derive IRQ and reset-request levels, then notify the waiting initiator.

A same-edge kick or newly enabling write suppresses decrement. Disable suppresses
expiry. A STATUS W1C coinciding with the final decrement loses to the new expiry.
Reset has priority over all register effects. Cancelled requests retain their PEQ
entry and complete at their original scheduled edge; they are not freed early.
This avoids a queued reference to an expired transaction context. Reset does not
abort the caller immediately.

## Directed test cases

Every case starts reset low, samples reset at 10 ns, deasserts at 11 ns, and uses
a separate simulator process. Assertions use explicit failures in Release builds.

| Case | Independent expectation |
|---|---|
| expiry | LOAD=3 commits at 30 ns, enable at 50 ns, expiry at 80 ns; W1C clears outputs |
| kick_boundary | Kick commits at 80 ns and prevents that expiry; next expiry at 110 ns |
| disable_boundary | Disable commits at 80 ns and prevents expiry |
| reset_pending | Reset at 16 ns is sampled at 20 ns; pending write errors at 30 ns; LOAD stays 4 |
| annotated_delay | Read at 11 ns + 7 ns annotation + 15 ns bus delay commits at 40 ns |
| read_counter | COUNT read commits at 70 ns, returns 2 before decrement; expiry remains 80 ns |
| peq_on_edge | Readiness at 30 ns cannot commit until 40 ns |
| invalid | Bad register operations report errors and preserve intended state |

CTest runs each case with tracing enabled and disabled. Further qualification
tests should cover LOAD=1/max, different clock phases/latencies, live LOAD changes,
CTRL mask changes, W1C exactly at expiry, reset at expiry, and randomized sequences.
The current directed tests are a starting set, not exhaustive verification.

These additional cases are now exercised by `tests/test_platform.py`, including
the independent RTL reference. Configurable experiments use `scenario.cpp`
through the [CLI](CLI.md); the eight fixed pilot cases remain unchanged.

## Pilot trace format

CSV fields are `tick,delta,sequence,event,transaction_id,address,value`. Resolution
is 1 ns in the example; IDs restart per run, with 0 for nontransaction events.
Events are submit, peq_ready, commit_read, commit_write, access_error,
reset_cancel, reset, expiry, irq, and reset_request. Address/value are decimal;
irrelevant fields contain zero. These fixed pilot conventions must not be
mistaken for the richer proposed canonical schema.

The synchronous CSV observer reads time and scalar values only and schedules no
simulation activity. Trace I/O failure fails the run. Pass `-` as the trace path
to disable it. `tools/check_pilot_traces.py` checks event timing and transaction
accounting on the eight generated traces.

