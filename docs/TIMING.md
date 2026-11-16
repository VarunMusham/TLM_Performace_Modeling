# Timing and observation contract

The platform accepts hybrid models. Classification as LT or AT is metadata,
not an admission requirement. TLM's coding styles do not by themselves determine
an IP's accuracy. A PEQ schedules a payload for the current simulation time plus
its supplied delay; this is the relevant primitive for observing the user's
models. [TLM LRM, coding styles and section 9.3](https://www.accellera.org/images/downloads/standards/systemc/TLM_2_0_LRM.pdf)

## Project rules

These are proposed platform conventions, not additional SystemC standard rules.

- Store time as integer kernel-resolution ticks, with the resolution in the run
  manifest. Preserve 64-bit precision through JSON/JavaScript boundaries using
  decimal strings where necessary. Do not use floating-point nanoseconds as IDs
  or as the basis for equality comparisons.
- Record observed kernel time separately from annotation and effective time.
  A transport event may have `effective_tick = observed_tick + delay_tick`.
  A PEQ callback is already occurring at its scheduled time: do not add the
  original PEQ delay again.
- Store delta count and monotonically increasing observation sequence for
  debugging same-time events. Sequence orders observations in one run; it is not
  an RTL cycle number or a cross-model matching key.
- Associate cycle observations with a named clock, epoch, edge convention, and
  period. A timestamp on a clock crossing cannot be divided by one global period
  to obtain a meaningful cycle for every domain. Frequency changes need segments.
- Attribute each latency interval to one pair of semantic endpoints. Nested
  intervals and overlapping stalls are not automatically additive.
- Record synchronization and temporal-decoupling policy. For initial correlation,
  use a synchronized workload driver; enabling local-time lookahead later requires
  evidence that it preserves interactions and ordering for that adapter.

## Canonical event draft

| Field | Meaning |
|---|---|
| schema_version, run_id | Event contract and producing experiment |
| source, event, scope | Component, semantic boundary, and traffic/resource scope |
| observed_tick, effective_tick, delay_tick | Kernel observation, logical timing, annotation |
| delta, sequence | Same-time debug ordering |
| transaction_id, parent_id, attempt_id | Stable identity, split/merge lineage, retry attempt |
| clock_id, epoch, cycle | Optional clock-domain interpretation |
| direction, channel, traffic_class | Optional classification |
| payload_bytes, wire_bytes | Separate useful data and modeled transport overhead |
| value, reason, attributes | Resource level, stall cause, or adapter-specific metadata |

Fields that do not apply are absent, not fabricated. The implemented WDT
normalizer and semantic validator are in `tlm_lab/events.py`; canonical tick,
delta, sequence, epoch and cycle values are decimal strings. The raw WDT CSV
retains the smaller pilot format described in its specification. Other adapters
must provide protocol-specific normalization and validation.

Stable transaction IDs must survive payload reuse. Use an adapter-owned sequence
or a managed extension only where ownership is agreed. For retries, distinguish
one logical operation from its attempts. Splits and merges require lineage;
pointer values and trace row position are not reliable correlation keys.

## Probe locations

For a PEQ-driven pipeline, useful boundaries are request offered, accepted,
PEQ scheduled, PEQ delivered, queue entered, service started, service completed,
response offered, and response accepted. Add resource-level changes for queues
and credits. A socket can reveal external latency but cannot reconstruct hidden
arbitration or service time. Internal breakdown requires internal hooks.

For same-timestamp behavior, specify precedence in the model contract. Never
assume insertion order in a trace establishes a hardware priority. The WDT uses
a strict next-edge rule and an explicit reset/write/decrement priority to avoid
relying on the order in which a PEQ process and clock process happen to run.

## Timing review checklist

Check nonzero incoming annotation, zero-delay PEQ delivery, elapsed versus returned
delay, same-time completions, payload reuse, retry/cancellation, reset during work,
cross-domain events, and clock changes where supported. Compare tracing enabled
and disabled. Confirm events, outputs, and final state are identical; only host
runtime should change.

