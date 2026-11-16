# Adapter SDK and integration contract

Status: proposed R1 design; current implementation is the WDT special case.
Requirements REQ-01/02/03/05/12/17; tickets B02-B04/B09.

## Registry and package

Each package contains `adapter.json`, a parameter JSON Schema, workload operation
definitions, event mapping, timing/ownership notes, build profile, launch provider,
normalizer, metric capabilities, fixtures and qualification references. Adapter
ID, adapter version, model revision and protocol profile revision are independent.
Discovery reads manifests; it does not import or execute untrusted Python code.
Only locally registered trusted adapters may launch code.

The manifest must declare: supported transport kinds and port roles; payload and
extension ownership; clock/reset bindings; legal parameter ranges and constraints;
topology compatibility; protocol revision/options; available event families;
supported observations/metrics; unsupported mechanisms; runtime dependencies and
entry points; deterministic/seed behavior; maximum outstanding capacities; and
evidence retention restrictions. A claim such as `internal_probes=true` is too
coarse: enumerate queues, counters, credit pools and semantic boundaries.

## Python control interface (proposed signatures)

```python
class AdapterProvider:
    def describe(self) -> AdapterManifest: ...
    def validate(self, resolved: Scenario) -> list[Diagnostic]: ...
    def prepare(self, resolved: Scenario, staging: Path) -> PreparedRun: ...
    def launch_spec(self, prepared: PreparedRun) -> LaunchSpec: ...
    def normalize(self, raw: ArtifactReader, context: RunContext) -> Iterator[Event]: ...
    def validate_semantics(self, events: EventReader, context: RunContext) -> ValidationResult: ...
```

`PreparedRun` lists relative artifacts and hashes, never hidden global state.
`LaunchSpec` has argv array, cwd, allowlisted environment, timeouts, executable
fingerprint, expected outputs and success markers. `Diagnostic` has stable code,
severity, JSON pointer/source location and remediation. Prepare occurs before
simulation; normalization/metric functions run offline. Provider callbacks never
schedule individual simulation transactions over Python/RPC.

Two launch providers are required: compile-time native integration for models
that can share a compatible SystemC kernel, and external executable/testbench
integration for existing simulator environments. An external adapter must still
provide the same evidence contract. Separate executables do not constitute a
causally correct composed simulation; composition requires a shared kernel or an
explicit synchronization design, which is deferred for distributed kernels.

## Native SDK boundary

Provide C++14 headers under proposed `native/include/tlm_lab/`. A native adapter
constructs/binds the IP, exports workload endpoints, maps clock/reset/setup,
publishes observation capabilities and reports terminal counters/metadata.
Its driver executes workload feedback in the simulator. Example interface shapes:

```cpp
struct Observation;                 // owned scalar snapshot, no payload pointer
struct Observer {
    virtual void record(const Observation&) noexcept = 0;
    virtual bool failed() const noexcept = 0;
    virtual ~Observer() = default;
};
// Adapter-owned endpoint methods follow the actual model's blocking,
// nonblocking or signal contract; there is no universal blocking submit shim.
```

The noexcept capture method sets a latched error/loss state on failure. A separate
driver control point terminates the experiment; observer hooks must not wait,
notify IP events, change delays, retain payload references or mutate DUT state.
Counters, off/digest, selected and full capture share semantics. Buffer exhaustion
has an explicit policy: fail exact capture or mark a filtered/sampled diagnostic
stream; never silently overwrite and award exact qualification.

## Transport-specific preservation rules

| Interface | Required adapter behavior | Verification |
|---|---|---|
| `b_transport` | Record entry, annotation, defined admission, exit and return annotation; preserve waiting thread and ownership | Nonzero delay, reuse, reset, error completion |
| Base-protocol `nb_transport` | Record call/return direction, phase, delay and sync enum; preserve all legal transitions and memory-manager lifetime | ACCEPTED/UPDATED/COMPLETED, immediate/annotated completion, legal overlaps |
| Custom TLM protocol | Register its own transition/ownership schema | Model-owner legal/illegal transition fixtures |
| Signals | Define offer/admission/completion at named edges and pre/post-update sampling; preserve ready/valid behavior | Sink stall, reset and edge coincidences |
| DMI/debug/invalidation | Preserve if supported; otherwise reject dependent experiments explicitly | Forwarding and invalidation tests; DMI observability policy |

Do not call a blocking target concurrently merely because the workload engine
supports concurrency. Each endpoint declares admissible outstanding operations,
initiator instances and serialization rules. Protocol extensions are observed only
through agreed scalar snapshots. Logical IDs cannot be payload addresses.
For split/merge/retry, record lineage and attempt identity at the owner boundary.

Timing ownership must follow [TIMING](TIMING.md): classify every boundary as
consuming or annotating time and record the actual synchronization policy.
Internal PEQ delivery is already at its effective time. A wrapper must not add
the PEQ delay again or force every model into WDT's strict-next-edge policy.

## Onboarding deliverables and done criteria

1. Complete [intake](templates/IP_INTAKE.md) with source evidence and limitations.
2. Add manifest/schema and reproducible build profile; capability rejection tests.
3. Add minimal workload, native/external launch path and complete counter summary.
4. Add scalar probes/normalizer; prove transport and reset behavior unchanged.
5. Provide RTL mapping/importer and directed, stress, holdout evidence.
6. Publish [qualification](templates/QUALIFICATION.md), supported configs and one
   runnable CLI example; install on a clean supported host.

The platform can accept an adapter with boundary-only visibility. It must show
internal metrics as unavailable and cannot assign causal bottlenecks to resources
that it never observes. Synthetic adapters carry `model_kind=synthetic`; their
performance is never relabeled as UALink/UCIe/PCIe predictions.
