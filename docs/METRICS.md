# Metrics contract

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

