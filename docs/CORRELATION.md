# RTL correlation and qualification

Status: WDT exact comparison exists; the following production policy is proposed
for R1/R2. REQ-07/09/12/14; B08/B09/B12. Use the
[qualification record](templates/QUALIFICATION.md) for every supported profile.

## Qualification pipeline

1. Validate experiment equivalence: model/configuration, offered intent,
   seed/feedback policy, clock/reset, initial state, endpoints and measurement.
2. Preserve raw RTL export plus exporter/simulator versions and source references.
3. Normalize with a versioned adapter map and independently validate lifecycle,
   counters, capture completeness and identity uniqueness. Do not tune a shift
   or infer missing events to make results match.
4. Compare the ordered causal skeleton first: logical requests, acceptance,
   outcomes, fragments/retries and required ordering domains. Independent
   transactions may reorder; a single global row order is not the criterion.
5. Compare each timing/KPI under a policy chosen before inspecting holdout data.
6. Save mismatch neighborhoods, relevant resource state and all unmatched counts.
   Report maximum and tail discrepancies even if an aggregate gate passes.
7. Bind passing evidence to revisions, configuration ranges and exclusions;
   invalidate affected qualification when mechanisms or policy change.

## Identity and alignment

Preferred join key is logical source/epoch/ID plus attempt/fragment and endpoint.
If RTL exposes only tags, exporter records tag generation and mapping to intent.
If identity cannot be uniquely reconstructed, mark exact transaction matching
inconclusive; aggregate comparison may proceed only under its own explicit policy.
Stable sorting must not invent a causal relationship between independent events.
Repeated same-kind events require visit/attempt identity, not occurrence index
unless the profile contract proves that index meaningful (legacy WDT only).

Align by a shared reset/synchronization marker and exact resolution conversion.
Record any sampling-region normalization. Missing markers, unknown epochs or
ambiguous clock conversion prevent exact timing claims. A one-cycle fitted shift
that reduces error is a discrepancy to investigate, not automatic calibration.

## Policy and result structure

| Gate type | Policy fields | Verdict |
|---|---|---|
| Exact | events/values/order domains, common time/edge convention | Any unmatched or required unequal observation fails |
| Bounded timing | endpoint, absolute cycle/tick bound, direction and scope | Every applicable transaction must satisfy bound |
| Aggregate | KPI, absolute/relative bound, population, sample/precision requirement | `abs(TLM-RTL) <= max(abs_limit, rel_limit*abs(RTL))` after evidence gate |
| Statistical | estimator, independent trials, uncertainty and predeclared decision rule | Adequate precision required; otherwise inconclusive |
| Regression | baseline revision and KPI, one/two-sided direction, threshold | Separate from RTL accuracy; improvement can still violate accuracy |

No default percentage tolerance is supplied for production links. At G0 the
model/RTL/performance owners select thresholds according to the engineering
decision. A policy can require exact architectural counts with bounded service
timing and statistical aggregate rates. Missing a required gate never turns the
overall result into pass. Collect profile-level exclusions explicitly.

Execution failure or incomplete required evidence -> inconclusive accuracy;
valid evidence with mismatch -> fail; no RTL evidence -> uncorrelated. Passing
exact WDT does not set `rtl_correlated=true` for every future adapter. Preserve
execution/evidence/qualification statuses independently in CLI output.

## Diagnostic artifact

`comparison.json` includes left/right artifact hashes, importer/policy versions,
equivalence checks, matched/unmatched/duplicate totals, every failed gate summary,
earliest causal divergence with surrounding operations/resources, maximum timing
error and full mismatch artifact references. Bound report previews while storing
all mismatches in chunked data. A summary with only the first 100 rows cannot
stand in for complete accounting. Counter disagreements are separate diagnostics.

RTL baseline generation must be independent of TLM state-update implementation.
Use common offered intents, not TLM-computed accepted/completion times. Accepted
RTL replay is useful for diagnosis but cannot qualify source-visible backpressure.
Keep directed training/calibration workloads separate from holdout workloads;
changing model timing to satisfy holdout consumes that holdout and requires new
unseen evidence.

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

