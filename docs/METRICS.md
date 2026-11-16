# Metrics contract

Status: definitions below are the proposed generic R1/R2 contract. Current
`metrics.py` implements only the WDT subset described in [CLI](CLI.md).
REQ-05/06, tickets B04/B06. Use [data contracts](DATA_CONTRACTS.md) for identity,
resource events and units. Every reducer publishes prerequisites and quality flags.

## Generic implementation and availability

Metrics run offline as reducers over canonical streams, grouped by component,
flow/class, direction, resource and clock domain as appropriate. Each output
includes definition version, endpoint pair, unit, population, window, numerator,
denominator, sample count, failed/cancelled/censored counts and source hashes.
Unknown observations return `unavailable` with a reason code; no-probe is not zero.
Partial capture yields `incomplete`; qualification consumes only adequate results.

| KPI | Required events/state | Rule and pitfall |
|---|---|---|
| Admission delay | offered/admitted linked by logical intent | Admitted minus offered; report rejected/unadmitted population separately |
| Operation latency | admission and declared final completion | One value per logical operation, not each fragment/retry |
| Response delivery | response.offered/accepted | Isolates consumer backpressure from producer service |
| Useful throughput | successful final delivery and useful bytes | Bytes delivered in window/duration; no double counting retries |
| Wire utilization/throughput | physical transmission intervals or wire counters at one layer | Include defined overhead/replay; specify direction and rate convention |
| Queue wait | enter/leave for same resource visit | Pair by logical/attempt/visit identity; multiple visits remain separate |
| Occupancy | initial resource level plus all level changes | Integral of level over window; report unit, peak and capacity |
| Service utilization | service begin/end with interval identity | Union on a single-capacity resource; capacity-weighted busy slots for multi-server |
| Credit pressure | initial pool state and allocation/returns; stall reasons | No-credit duration is not automatically stalled duration when no traffic waits |
| Stalls | begin/end paired per resource/reason | Overall fraction is interval union, not sum of overlapping reasons |
| Retry overhead | attempts, successful logical bytes, wire bytes | Extra attempts and transmitted bytes per useful completion |
| Fairness | per-flow delivered rate in same window | Jain index `(sum x)^2/(n*sum x^2)`; all-zero -> unavailable; report starvation too |
| End-to-end | source intent/final consumer lineage | Latency across hops; don't sum overlapping critical-path intervals |
| WDT timeout/output | adapter-specific arm/reload/expiry/output | Exact cycles/decision-edge semantics remain in WDT plug-in |

Use full timestamps for equality/accounting even if charts bin time. Bin interval
boundaries are half-open; split integrals exactly across bins. If capture begins
after time zero, require a state snapshot for resources and outstanding operations.
Without it, dependent metrics are unavailable until state is established.

## Worked analytical fixture (required regression)

Window `[10,30)` ticks. A admitted at 5 completes at 12 with 4 useful bytes;
B admitted at 15 completes at 25 with 8 bytes; C admitted at 26 remains pending.
The admission cohort is B and C: admitted=2, completed=1, censored=1; observed
completed latency=10 ticks. Completion-window bytes=12, rate=0.6 bytes/tick.
Inflight occupancy area is `1*2 + 1*10 + 1*4 = 16`, average 0.8, peak 1.
This observed latency distribution is conditional on completed work; C prevents
an unqualified latency pass under a policy requiring complete drain.

Two stall reasons `[11,18)` and `[15,25)` occupy 7 and 10 ticks. Their union is
14 ticks, overall fraction 0.7; summing 17/20 is incorrect. A completion exactly
at 30 contributes to admission-cohort follow-through but not window throughput.
Additional fixtures must cover initial level >0, capacity changes, multi-server
overlap, fragment merge, tag reuse and credit reset.

## Statistical and numerical policy

Nearest-rank quantiles are `sorted[ceil(p*N)-1]`; median is explicitly the midpoint
of central samples for even N. Record both conventions. Full exact quantiles may
use external sort; approximate sketches must name algorithm, parameters and
error guarantees and cannot silently replace exact acceptance measurements.
Integer accounting remains exact; specify decimal rounding for displayed ratios.

Separate within-run samples from independent seed repetitions. A million correlated
packets from one seed are not a million independent trials. Qualification policy
sets minimum trials, effective sample reasoning and desired confidence/precision.
For stochastic KPIs use a declared independent-seed interval/bootstrap method
with its own reproducible seed. Tail precision needs order-statistic/binomial or
another reviewed method; `N >= 100` alone is not a universal p99 acceptance rule.
No sufficient samples/precision -> inconclusive, not a skipped passing gate.
Deterministic exact-cycle fixtures use equality, not statistical confidence.

Hardware KPIs and host KPIs are distinct result namespaces. Host profile reports
startup, build, simulation, capture, ingest and analysis separately, with RAM/disk
and environment. A speedup ratio requires equivalent completed work, boundaries,
capture policy, tool settings and accuracy evidence on the same controlled host.

Every metric identifies its endpoints, scope, units, window, population, and
trace requirements. A number without these definitions is not comparable to RTL.

Use a half-open measurement window `[start, end)` after an explicitly configured
warm-up. Stop offering traffic at the configured end; drain admitted work up to
a separately bounded deadline. Report outstanding and censored work. Do not
silently discard slow transactions and improve the latency distribution.

| Metric | Definition and interpretation |
|---|---|
| Admission delay | Accepted time minus offered time; measures source-visible backpressure |
| Transaction latency | Chosen completion boundary minus chosen admission boundary |
| End-to-end latency | Final consumer acceptance minus original operation offer |
| Queue wait | Service-start minus queue-entry for the same visit |
| Service time | Service-end minus service-start; adapter must define the resource |
| Payload throughput | Successfully completed useful bytes in the window / window duration |
| Wire throughput | Modeled transmitted bytes including defined overhead / duration |
| Offered / accepted rate | Offered / admitted count or bytes per duration, reported separately |
| Occupancy | Time-weighted queue level: sum(level * dwell time) / window duration |
| Utilization | Union of resource-busy intervals / window duration |
| Stall fraction | Union of stalled intervals / duration for each reason and overall |
| WDT timeout | Expiry edge minus enabling/reloading edge, in WDT-domain cycles |
| WDT response time | IRQ/reset output assertion minus defined cause; report delta visibility separately |

Seed occupancy and busy/stall state at window start and clip intervals at both
ends. Summing simultaneous stall reasons can exceed total stall time; show overlap
or an explicit exclusive attribution policy. Report peak occupancy and capacity
alongside average occupancy. Little's law is a steady-state diagnostic, not a
proof of correctness during transient or draining traffic.

For latency, default to the **admission cohort**: transactions admitted inside
the window, followed through drain. State the number completed, failed, and still
outstanding. Throughput uses the **completion window**, including completions
from earlier admissions. Keep these populations visibly distinct.

Report count, min, max, mean, median, p95, and p99 using a documented quantile
method (proposed: nearest-rank, rank `ceil(p*N)`). Label small samples; do not use
p99 as an acceptance gate without adequate observations. Use independent seeds
and confidence intervals for stochastic workloads; deterministic WDT timing
requires exact event checks rather than statistical confidence claims.

Check conservation per scope: admitted equals completed plus failed/cancelled
plus outstanding, with explicit retry and split/merge accounting. Define whether
bytes mean requested, transferred, enabled, or successful payload bytes. Retries
consume wire capacity without multiplying useful completed payload.

Separate host performance (wall time, memory, trace bytes, simulated-time/wall-time
ratio) from modeled hardware performance. Build time is recorded separately.
Tracing overhead is compared against an otherwise identical no-trace run.

