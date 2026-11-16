# RTL correlation and qualification

The platform's credibility comes from evidence. A PEQ-based model is not
automatically cycle accurate: the same queues, resource constraints, arbitration,
and clock behavior must be represented for the question being asked.

## Experiment equivalence

Before comparing results, match reset sequence, register settings, clock periods
and phases, traffic intent, seeds, address/payload distributions, outstanding
limits, downstream responses, warm-up, and measurement boundaries. Record both
model revisions. Fix unsupported features or explicitly exclude them from scope.

Replaying RTL *accepted* transaction timestamps into TLM can hide a TLM
backpressure error. Prefer common offered traffic and equivalent ready/credit
feedback. For feedback-dependent workloads, use the same dependency graph or
closed-loop driver semantics. Label open-loop trace replay separately.

## Evidence strategy

1. Begin with semantic CSV events exported by an RTL monitor: reset, accepted
   register operations, response completion, expiry, IRQ, and reset request.
2. Include cycle domain/epoch, edge convention, transaction identity, and sampled
   values. Define whether signal values are sampled before or after sequential
   updates; normalize that difference explicitly.
3. Use counters to cross-check accounting. Use waveforms to debug a mismatch,
   rather than making proprietary waveform parsing an MVP dependency.
4. Preserve raw artifacts and conversion-tool versions. Alignment uses a shared
   reset or synchronization marker, never a fitted shift chosen to hide errors.

## Comparison modes

**Exact events:** compare event type, logical identity, values, ordering where
specified, and named-domain cycle. Missing, duplicate, or unmatched events are
failures; reordered independent traffic is matched by identity, not row number.
Delta counts are useful for SystemC diagnosis but are not required to equal RTL
simulator scheduling regions.

**Bounded per-transaction timing:** use approved absolute bounds in cycles/ticks,
grouped by operation and traffic class. Always show the maximum discrepancy and
first mismatch. Do not let a passing mean hide individual timing violations.

**Aggregate metrics:** proposed comparison is
`abs(TLM - RTL) <= max(absolute_limit, relative_limit * abs(RTL))`.
The limits are agreed per metric before qualification. At a zero RTL baseline,
the absolute bound applies. Tail metrics require adequate population size.
Distribution differences and load curves matter in addition to averages.

## Qualification sequence

| Stage | Evidence required |
|---|---|
| Model sanity | Independent analytical checks, transaction accounting, deterministic reruns |
| Directed timing | Register latency, timeout edges, reset, kick/expiry collision, invalid access |
| Stress | Burst traffic, outstanding limits, queue capacity, backpressure, starvation/retry where modeled |
| Holdout | Unseen seeds/settings and combined corner cases not used to tune timing |
| Regression | Same checks across model and RTL revisions, with visible changes in coverage |

For the WDT, implement an independent, small clocked RTL reference from
[the reviewed specification](WDT_SPEC.md). Avoid copying C++ state-update code
into the reference. Give both models the same timed register intents and compare
their accepted/committed operations and outputs. The C++ pilot tests are model
sanity checks, not RTL correlation.

For a link IP, add load sweeps, packet-size mix, multiple requesters, credit
return delays, finite buffers, head-of-line blocking, retry policy, and multiple
clock domains as applicable. Protocol version and optional features belong to
the adapter's contract; they are not inferred from the name PCIe/UCIe/UALink.

## Qualification result

Publish validity and correlation separately: `invalid_run`, `uncorrelated`,
`pass`, `fail`, or `inconclusive`. Qualification names the exact model/RTL
revisions, configuration envelope, workload set, metrics, thresholds, and
known gaps. A changed timing mechanism or configuration outside the envelope
requires requalification. Diagnostic failures retain the first mismatch plus
surrounding transactions, resource state, and source trace references.

