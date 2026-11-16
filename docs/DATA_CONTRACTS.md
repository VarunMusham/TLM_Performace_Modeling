# Versioned data contracts

Status: proposed v2; **not implemented by the current v1 CLI**. Ticket B02 defines
machine JSON Schemas and parsers from this contract before downstream features.
Use JSON Schema draft 2020-12 for structure and explicit semantic validators for
cross-references/time/causality. Pin validator dependencies and package offline.

## Versioning and object boundaries

Scenario, adapter manifest, event, workload, metric, run manifest, importer and
qualification versions evolve independently. Reject unknown major versions.
Minor additive fields are accepted only in documented extension namespaces;
unknown core fields are errors. Converters produce new artifacts and record
input/output hashes and converter version; raw evidence remains unchanged.
V1 WDT remains readable/runnable with the legacy adapter and explicit conversion.

| Object | Required contents |
|---|---|
| Scenario | schema/version, name, topology/model references, profile, clocks/resolution, reset/setup, workload, window/drain, seed, capture, metrics, qualification policy |
| Model manifest | adapter/model/protocol identities, parameter schemas, ports/capabilities, timing/reset/ownership, dependencies/limitations |
| Workload | operations or generated materialization, source/flow, identity, offer/dependencies, payload metadata, stop/rejection policy |
| Build manifest | exact inputs/commands/toolchain/dependencies, output hashes, compile/link options and environment whitelist |
| Run manifest | scenario/build hashes, model/profile revisions, lifecycle/status, host/tools, processes, clocks, raw artifacts/counts/loss, termination, analysis links |
| Metric result | definition/version, source run/stream hashes, scope/units/window/population, value or unavailable reason, sample/censor counts, precision method |
| Comparison | equivalence checks, policies/order domains, matched/unmatched counts, first causal discrepancy/context, per-KPI status/bounds |
| Qualification | envelope, independent RTL revision, approved policies, test matrix/results, gaps and reviewers |

Strings hold integer ticks, IDs and counters that can exceed JavaScript's exact
integer range. Parameters may use JSON integers where schema bounds are safe.
Parsers reject NaN/Infinity, duplicate keys, fractional integer fields, overflow
and negative unsigned values. Metric ratios carry units and controlled precision;
never convert timestamp identity or ordering to binary floating point.

## Time model

`resolution_fs` is a positive integer number of femtoseconds per kernel tick.
Every clock segment has clock ID, epoch, first edge, period in ticks, edge kind,
valid interval and reset association. Configuration must be exactly representable
at the chosen resolution; reject rounding rather than silently skewing clocks.
Absolute physical time uses integer scaling. Compare different resolutions by
exact integer cross-multiplication; no fitted time shift. Record synchronization
markers and any fixed, justified alignment transform separately.

Kernel observation time, call annotation and logical effective time are distinct.
For an annotated call, effective=observed+annotation. A later callback's observation
already occurs at delivery time. Frequency changes begin a new segment; reset
may begin a new protocol epoch without changing the physical clock segment.
Only attach a cycle number if the event belongs to a defined sampled edge.
Time-based metrics can cross domains; cycle-based metrics require one stated domain.

## Canonical event v2

Required common fields: `schema_version`, `run_id`, `stream_id`, `source`,
`scope`, `event`, `observed_tick`, `effective_tick`, `sequence`. A stream sequence
is monotonic and contiguous in a full capture. Optional `delta` is simulator
diagnostic data; sequence is not a global hardware ordering relation.

| Group | Fields and semantics |
|---|---|
| Timing | annotation_tick, clock_id, clock_epoch, cycle; declared endpoint semantics |
| Identity | logical_id, attempt_id, fragment_id, parent_ids, flow_id, source_epoch |
| Placement | component_id, port_id, channel_id, direction, traffic_class, order_domain |
| Resource | resource_id, visit_id, interval_id, level, capacity, credit_pool, credit_unit |
| Accounting | requested_bytes, transferred_bytes, useful_bytes, wire_bytes; counted layer |
| Outcome | status, reason, protocol_sequence; errors/cancellation distinct from success |
| Metadata | namespaced attributes; no unconstrained raw payload dump by default |

Event families: `request.offered`, `request.admitted`, `request.rejected`,
`response.offered`, `response.accepted`, `operation.completed`,
`operation.failed`, `operation.cancelled`; `queue.enter/leave`,
`service.begin/end`, `resource.level`, `credit.change`, `stall.begin/end`,
`retry.begin/end`, `reset.assert/deassert/sampled`, and `clock.segment`.
An adapter declares which families it can supply and exactly what each means.
Namespaced events such as `wdt.expiry` retain their own schemas.

Logical identity is assigned once at source intent and propagated through peers
or via an explicit trace join. Attempt IDs distinguish retransmission; fragment
IDs and parent lists represent splits/merges. Visit IDs distinguish re-entry to
the same queue. Reused protocol tags combine with epoch/generation to remain
unique. The normalizer must not invent identities from row position except the
explicit legacy WDT conversion, whose serial workload guarantees that mapping.

## Semantic invariants and partial streams

- No completion without admission, except explicitly modeled pre-admission
  rejection; no duplicate terminal logical outcome. Every retry/fragment is
  accounted for without double-counting useful work.
- Endpoints are temporally ordered in effective time under their contract.
  Observed order may differ for annotated callbacks; validate both independently.
- Resource levels stay within capacity, units match, visits/intervals pair,
  reset/cancellation closes or invalidates outstanding state explicitly.
- Queue conservation and credit conservation are adapter-specific equations;
  shared pools must not be counted once per observing component.
- A trace footer records emitted/captured/dropped counts, filters, last sequence
  and final simulation boundary. Sequence gaps are allowed only for a declared
  filtered view with original sequence/provenance preserved.
- A filtered stream cannot prove completeness. Metric prerequisites enumerate
  required families/counters and mark results incomplete when missing.

Events are ordered only inside required domains: same operation, resource visit,
flow/class ordering guarantee or causal edge. Independent completions may reorder
across implementations. Joining by a single global row index is prohibited.

## Persistence and manifest lifecycle

Use append-only raw chunks plus a footer/index. JSONL/CSV are interchange formats;
prototype a SQLite index for time/identity/resource lookup without loading the
whole trace. Introduce Parquet/compression only after measured benefit and define
equivalent read semantics. Index rebuild from immutable chunks must be supported.

Publish `run.started.json` before invoking any preparation that may fail. Journal
state changes; write final manifest to a temp file and atomically rename on the
same filesystem after outputs close/hash. Keep crash/interrupted evidence.
Derived output lives in `analysis/<id>/` and names its analysis version and inputs.
A final manifest is not edited by replay, reanalysis or report generation.
Directory hashes detect accidental alteration, not authentication; add signed
attestations only if a later deployment requirement needs them.

See [design example](design_examples/scenario-v2.json) for a proposed scenario
shape. The example deliberately uses a synthetic fixture and does not prescribe
unknown production-IP parameters. B02 must validate it against the implemented
schema and migrate it if the contract changes.

Additional specimens: [admission event](design_examples/event-v2.json) and
[comparison policy](design_examples/comparison-policy-v2.json). The event is at
an asynchronous admission boundary, so it has no invented clock cycle. Resolution
comes from its run. The policy's zero bounds apply to the synthetic fixture only;
they do not assign tolerances to production IPs. These JSON files are parseable
design examples; schema/semantic acceptance is a B02 deliverable.
