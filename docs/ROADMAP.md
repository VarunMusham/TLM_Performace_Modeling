# Delivery roadmap

Implementation follows review of the platform and WDT contracts. Estimates are
planning ranges for one developer familiar with the IPs, not commitments. Real
adapter access, RTL monitor effort, and model fixes can dominate elapsed time.

| Milestone | Deliverables | Exit gate | Indicative effort |
|---|---|---|---|
| M0: review and pilot | These documents, WDT model, directed tests, Windows build recipe | Agree WDT semantics, target toolchain, first RTL baseline | 2-4 days including review |
| M1: experiment foundation | Validated scenario schema, runner, run manifest, adapter API, canonical events | Reproduce WDT runs; detect invalid configs, timeouts, missing data | 1-2 weeks |
| M2: WDT correlation | Independent RTL WDT, trace exporter/importer, exact comparator, mismatch report | Exact-cycle directed and holdout cases; injected one-cycle error detected | 1-2 weeks |
| M3: real link-IP pilot | One existing IP adapter, internal probes, workload and metric suite | Agreed RTL comparison across low load and saturation | 2-4+ weeks |
| M4: reusable analysis | Seeded sweeps, comparison reports, CI gates, capture profiling | Reproducible multi-run reports and measured overhead | 1-2 weeks |
| M5: expansion | Additional adapters and multi-IP contention experiments | Per-IP qualification plus composition tests | Scope after M3 |

M2 is required before claiming RTL agreement. M3 is required before treating the
platform as suitable for UALink/UCIe/PCIe performance studies. WDT validates
timing discipline and the workflow but does not exercise link bandwidth,
credits, reordering, retries, or multi-requester arbitration.

## First implementation backlog

1. Finalize WDT register/timing policy and exact output sampling convention.
2. Verify the pilot under the actual SystemC 2.3.4 compiler/runtime combination.
3. Implement scenario validation and capability checks; reject unresolved values.
4. Add immutable manifests and process lifecycle/error handling.
5. Generalize pilot events into the canonical schema and add stable IDs.
6. Implement metrics with independent hand-computable fixtures, including window
   boundaries, unfinished transactions, and overlapping stalls.
7. Build independent RTL reference and a normalized event importer.
8. Implement correlation with deliberate mismatch, missing-event, and reordered
   traffic fixtures. Generate the first human-reviewable comparison report.
9. Add a real link IP and audit its modeled performance mechanisms.

## Test strategy

Use directed, independently expected timestamps for the WDT; analytical fixtures
for metric calculations; semantic fixtures for importers; and RTL comparisons for
accuracy. Test payload reuse, reset/cancellation, nonzero delay, same-edge races,
invalid configuration, trace loss, drain deadlines, and repeatability.

Run full timing checks with tracing on and off. Measure overhead only after
equivalent outputs are demonstrated. Run sweeps in separate processes and bound
parallelism to avoid memory exhaustion or misleading host runtime comparisons.

