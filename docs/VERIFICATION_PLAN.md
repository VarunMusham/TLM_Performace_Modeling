# Verification, qualification and release evidence

Status: proposed generic suites. Current observed WDT results remain in
[VALIDATION](VALIDATION.md). This plan does not upgrade that scope. Each AT suite
must include independent expected behavior; mirroring implementation is insufficient.

| Test ID | Required independent evidence and negative control | Gate |
|---|---|---|
| AT01 | v1 compatibility, schema migration, unknown/duplicate fields, registry rejection; golden WDT semantic replay | G1 |
| AT02 | Nonzero/consumed/returned annotation, zero-delay PEQ, same-edge priority, fractional-time rejection, multi-clock epoch and reset; tracing preserves semantics | G1/G2 |
| AT03 | Blocking/nonblocking/custom/signal contracts; payload reuse/lifetime, DMI/debug forwarding or explicit rejection; native/external launch | G1 |
| AT04 | Synthetic one/two-source service capacity, finite outstanding/queues/credits, delayed returns, burst/stall/dependency graphs and stop/drain conservation | G2 |
| AT05 | Initial resource state, paired visits/intervals, retries/fragments, credit conservation, bounded buffers, filtered/full trace prerequisites and loss injection | G2 |
| AT06 | Hand-computable latency/window/occupancy/union/fairness, failed/censored cohorts, exact/approx quantile distinction, independent-seed precision | G2 |
| AT07 | Per-profile RTL/TLM equivalent setup, low-load/saturation/contention/backpressure and reserved holdout; explicit scope/limits | G3/G4 |
| AT08 | Inject one-cycle error, loss/duplicates, wrong epoch/bytes, ambiguous identity; allow independent reorder, reject causal reorder; zero-baseline tolerance and insufficient-tail evidence | G2/G3 |
| AT09 | Clean replay, stale binary/dependency, timeout/cancel/process descendants, disk full, write failure, crash before/after prepare/finalize, interrupted resume, artifact corruption | G1/G3 |
| AT10 | Matrix constraints, seed derivation, job/resource limits, cache invalidation, resume excludes successful attempts without rewriting them, failed attempts remain visible | G3 |
| AT11 | CLI JSON/exit codes, dry-run, unsupported metrics, empty result, paths, reproducible command/evidence bundle; reports match underlying numerators | G3 |
| AT12 | Shared-resource composed path with explicit bridges, cross-domain timing, lineage, contention, reset across components, routing/address failures and drain deadlock diagnostic | G4 |
| AT13 | Known small constrained space with independently checked optimum/Pareto set; sensitivity recovers injected controlling parameter; invalid/unqualified alternatives excluded | G5 |
| AT14 | Supported Windows package on clean host, compiler/ABI prerequisites, long/spaced/non-ASCII paths, offline use, export allowlist/secrets; Linux tested only when claimed | G3 and port gate |
| AT15 | Independent energy/state-duration fixture, calibrated coefficients/units, uncertainty, no double-counted power domains and missing calibration -> unavailable | G6 power |
| AT16 | UI operations produce identical resolved input and result artifacts to CLI; cannot alter immutable evidence or silently skip gates | G6 UI |
| AT17 | Trace/analysis memory and throughput, paired mode overhead, repeated trials and host metadata; complete counts survive capture pressure | G2/G3 |

## Suite layering and ownership

Unit tests cover pure schema and reducer functions with analytical fixtures.
Adapter contract tests cover ownership/timing and capability validation. Native
integration tests cover kernel scheduling and workload feedback. Qualification
tests run independent RTL/reference and apply predeclared policies. Capacity tests
measure large workloads separately from functional regressions. Keep proprietary
tests/data in access-controlled infrastructure; public/synthetic suites still run
without production IPs. Unavailable proprietary tests are reported as not run,
never converted into a production qualification pass.

PR gates: affected unit/contract tests and WDT compatibility; nightly/internal
gates: real-IP directed/stress/holdout across approved configurations; release
gates: complete declared matrix, clean supported-host replay and capacity report.
Seeded random tests supplement directed and independent analytical tests; record
seed and materialized intents for every failure. A reduced reproducer preserves
the same causal failure and its parent run reference.

## AT17 measurement protocol

Select and record a reference host (CPU/RAM/storage/OS), build options, runtime
dependencies, concurrency and power policy. Use a representative workload whose
simulation dominates startup; report startup separately. Warm up the environment,
then run at least five paired repetitions per capture mode with alternated/randomized
order and fixed workload/seed sets. Report median, spread, raw samples, peak RSS,
disk volume and events/second. Verify complete counters/digest before comparing
overhead. Never time trace-on and trace-off at different traffic outcomes.

For the proposed 10-million-event capacity target, separately bound resident
capture buffer, analysis RSS, outstanding operation state and disk spill. Increase
trace size at fixed outstanding capacity to expose accidental O(total events)
memory growth. Compare chunked and small exact fixtures for semantic equivalence.
If the <=2 GiB or <=5% counters-only targets are missed, report the measurement
and tune or revise the documented target through an ADR; don't call it passed.

## Accuracy acceptance

At G0, the performance and RTL owners approve per-KPI bounds and sample precision.
Model development may calibrate against a named training set. Reserve holdout
configurations/seeds and combined corner cases before tuning. Per-profile records
must distinguish deterministic exact cases, bounded timing and statistical results.
Qualification cannot be averaged across failing configurations to claim a pass.
Review outliers and first divergence; a good mean cannot excuse missing operations.

R1 needs one real existing link, not just WDT plus synthetic tests. R2 needs
interaction-level evidence in addition to component evidence. Full electrical or
protocol compliance is a different activity and is never implied by these gates.

## Evidence bundle for each gate

Include requirement/test IDs, resolved inputs, source/build/reference revisions,
commands/tool versions, raw/canonical counts and loss, metric definitions,
policy hashes, run status, KPI/accuracy verdicts, mismatches/waivers and owner review.
Waivers narrow the advertised envelope; they do not transform failed required
evidence into a pass. Copy the [qualification template](templates/QUALIFICATION.md).
