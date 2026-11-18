# Implementation backlog

Status: proposed work after baseline `43ba848`. No ticket below is complete merely
because related WDT code exists. Tickets are issue-ready work packages; split them
into reviewable PRs that preserve tests. Owners are roles, since staffing is unknown.
REQ/NFR IDs are in [requirements](PRODUCT_REQUIREMENTS.md); AT IDs in
[verification](VERIFICATION_PLAN.md). Effort is estimated person-days and overlaps
roadmap ranges; do not add both estimates together.

| ID | Work package / owner | Dependencies | Requirement coverage | Acceptance | Estimate |
|---|---|---|---|---|---|
| B01 | Baseline, intake and qualification policy / TLM+RTL+performance | None | REQ-12/13, NFR-08 | AT01, AT07 preparation | 5-10 |
| B02 | Versioned schemas/resolution/config core / platform | B01 | REQ-01/03, NFR-06 | AT01/02 | 5-8 |
| B03 | Adapter SDK/registry and WDT extraction / platform+TLM | B02 | REQ-01/02/17 | AT01/03 | 8-12 |
| B04 | Canonical capture/identity/resource streams and synthetic fixture / TLM+platform | B03 | REQ-03/05/13, NFR-03 | AT02/04/05 | 8-12 |
| B05 | Concurrent workloads/source-sink feedback / TLM | B03/B04 | REQ-04/15 | AT04 | 5-10 |
| B06 | Generic reducers/statistical policy / platform+performance | B04/B05 | REQ-06, NFR-07 | AT06/17 | 8-12 |
| B07 | Build/run/artifact lifecycle hardening / platform | B02, B03 for provider integration | REQ-08/09, NFR-02/04 | AT09/14 | 6-10 |
| B08 | Importers/partial-order correlation/qualification / RTL+platform | B04/B06/B07 | REQ-07/09 | AT07/08 | 6-10 |
| B09 | First real link adapter and qualification / TLM+RTL | B01/B03/B05/B08 | REQ-12, NFR-08 | AT07/17 | 15-30 plus model fixes |
| B10 | General sweeps/regression/CLI use cases / platform | B06/B07/B08 | REQ-10/11 | AT10/11 | 5-8 |
| B11 | Windows release, docs and CI gates / platform+verification | B09/B10 | NFR-01/05/08 | AT14/17 | 5-8 |
| B12 | Other profiles and multi-IP composition / TLM+RTL+platform | R1 | REQ-12/14/15/17 | AT07/12 | 40-80 plus bridge/model work |
| B13 | Constrained exploration/catalog / performance+platform | R2 | REQ-16/17 | AT13 | 30-60 |
| B14 | Future UI/power/Linux workstreams / scope-specific owners | R3 or separate user decision | REQ-18/19, NFR-01 | AT14/15/16 | Re-estimate |

## Ticket completion details

Customer pilot update (2026-11-18, CLI 1.1.0): external-1 source/testbench adapters,
Python/C++ observers/templates, concurrent boundary reducers, source snapshots,
rebuild replay, generic sweeps and an offline customer distribution implement
parts of B02-B07/B10/B11. SystemC source is vendored with its upstream notices and
hash pin. Protocol-specific SDKs, resource/lineage streams, real-IP qualification,
hermetic toolchains and multi-IP composition remain open; this is not an R1 gate
closure. See [external-1](EXTERNAL_ADAPTERS.md) for the implemented boundary.

Maintenance update (2026-11-18, CLI 1.0.1): a subset of B02/B07/B10 is implemented
for the existing WDT v1 path: strict JSON/evidence checks, atomic non-overwriting
JSON publication, checkpoints before preparation, retained failed/interrupted
attempts/build records, stronger replay checks, and failed-profile summaries.
Fault-injection tests cover these changes. This does not close those tickets:
versioned generic schemas, build attestation, recoverable job scheduling, sweep
cancellation/resume and clean-host dependency capture still require their gates.

**B01:** Store intake evidence for each candidate. Select first profile and KPI
questions. Pin representative WDT v1 raw/canonical/response fixtures, commands,
versions and baseline evidence. Record provisional capacity host and policy
owners. Output: accepted G0/ADR or explicit integration blockers.

**B02:** Introduce `schemas/` and typed versioned records; implement structural
validation plus graph/reference/time/capability semantic checks. Add v1 dispatch
and converter provenance. Schema-test the proposed design specimen. Reject
ambiguous resolutions and unknown options with stable diagnostic pointers.
Output: versioned contract package and golden migration tests.

**B03:** Add registry, Python provider interfaces and C++14 SDK; extract WDT
config/normalizer/metrics/RTL into its adapter. Implement native and external
testbench launch providers. Preserve the legacy executable path. Output: two
launch conformance fixtures and WDT semantic equivalence.

**B04:** Implement logical/attempt/fragment/visit identities, passive scalar
observer, bounded capture with footer/loss counts and chunked indexing. Add
synthetic credit-link fixture and independent expected behavior for small cases.
Output: resource conservation, payload reuse, reset and trace-loss fixtures.

**B05:** Add source/sink endpoints, fixed/generated/offered-replay workloads,
concurrent outstanding windows and branching dependencies. Freeze seeds and
materialized intent; enforce offer/stop/drain policy and admission/rejection
accounting. Output: burst, two-source contention and backpressure scenarios.

**B06:** Build streaming latency/throughput/resource/stall/fairness/retry reducers
and WDT metric plug-in. Implement unavailable/incomplete values, window seeding,
quantile precision and independent-seed summaries. Output: hand-computable
fixtures, published metric definitions and scale benchmark evidence.

**B07:** Link build hashes to binaries/dependencies; journal lifecycle before
preparation; atomically finalize manifests; preserve interrupted and cancelled
attempts; export/reanalyze into separate directories. Separate execution/evidence/
accuracy outcomes. Output: injected build/launch/disk/timeout/partial-artifact
tests and clean-host replay preflight.

**B08:** Define independent raw RTL importer contracts, exact time conversion,
identity mapping and per-domain causal matching. Keep all unmatched counts and
chunk mismatch details; implement approved deterministic/bounded/statistical
policies and qualification records. Output: positive/negative and allowed-reorder
fixtures; required-gate insufficiency returns inconclusive.

**B09:** Implement only capabilities supported by selected intake. Add setup,
datapath workloads, internal probes where permitted, raw RTL monitors and held-out
experiments. Resolve model mechanism gaps separately from wrapper changes.
Output: G3 record for one named real profile, with limitations and reproducible
Windows package. A synthetic stand-in cannot close B09.

**B10:** Implement application services beneath CLI, schema-backed commands,
constrained matrices, resume/retry policy, per-KPI regression direction/bounds,
machine-readable output and useful report summaries. Output: batch summary of
all attempts and no hidden changes to resolved experiments.

**B11:** Package CLI/dependencies/adapter SDK, CI scripts and clean-host install
guide. Test supported Windows compiler profile, long/spaced/non-ASCII paths,
process cleanup and offline artifacts. Audit exports and secrets. Publish release
manifest, limitations and requirements-to-test traceability; no automatic cloud
upload. Output: signed-off R1 checklist and tagged local release when authorized.

**B12:** Repeat B09 qualification per remaining family, implement typed topology
resolution, real bridges and lineage through shared resources/clock domains.
Add system-level RTL or independently approved system reference. Output: G4 with
per-IP plus composition evidence, not inherited single-IP passes.

**B13:** Add resource/catalog models only with declared fidelity, legal-design
constraints, parameter interactions, sensitivity and Pareto ranking using valid
qualified runs. Add task-level mappings as explicit model/workload components.
Output: reproduced architecture decision with uncertainty and constraint evidence.

**B14:** Separate projects: UI consumes the application API; power uses calibrated
state/activity coefficients with units/uncertainty; Linux gains toolchain/packaging
and determinism validation. Each has independent scope and gates before claiming
capability. ONNX/full-software imports need specific workload semantics and models.

## Definition of done for every PR

Requirement/ticket and contract change identified; affected semantic tests pass;
new limitations/capabilities documented; v1 fixture remains valid or migration is
explicit; sample command/output included; no fabricated unavailable metrics;
review notes identify timing/ownership effects. Commit locally in coherent units.
Run targeted suites and the applicable gate, rather than substituting code coverage
percentage for model accuracy. R1 release requires all G3 dependencies, not just
merged tickets.
