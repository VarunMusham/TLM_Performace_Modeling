# Architecture

All components below are proposed except the standalone WDT example.

```mermaid
flowchart LR
    C[Scenario and model contract] --> R[Python experiment runner]
    R --> S[SystemC simulation process]
    W[Workload / replay driver] --> A[IP adapter]
    A --> I[Existing hybrid TLM IP]
    W --> S
    A --> S
    I --> S
    S --> E[Events, counters, manifest]
    E --> M[Metrics and diagnostics]
    T[RTL events / counters] --> N[RTL normalization]
    N --> K[Correlation engine]
    E --> K
    M --> O[HTML / CSV report]
    K --> O
```

## Simulation boundary

Keep SystemC execution, workload feedback, and IP timing in one native simulation
process. Python configures and launches it and analyzes outputs after execution;
it does not schedule individual simulation transactions. Independent scenarios
run in separate processes. Parallel sweeps do not imply parallelizing one
SystemC kernel.

Use C++14 for the initial example and a matching SystemC library. A production
adapter may need the standard and compiler already required by its IP. Prefer
compile-time linking over a binary plugin ABI in the first version. Support an
external executable adapter when an IP must remain in its existing build or
commercial simulator environment.

## Adapter responsibilities

Each adapter declares ports and protocols, configuration fields, clock/reset
bindings, address map, extension ownership, timing rules, supported workload
operations, and probe locations. Capabilities are explicit: a boundary-only
model must not claim internal queue or credit visibility.

Do not enforce TLM base-protocol phases on custom protocols. For standard
`nb_transport` interfaces, record both call and return behavior, including
updated phases, timing annotations, and completion status. For `b_transport`,
record entry/return and whether the callee waited or returned annotated delay.
For signal interfaces, define the sampled edge and update visibility.

Inline monitors must forward all relevant transport paths and preserve binding,
DMI invalidation, debug transport, extensions, and payload lifetime. Begin with
explicit observation hooks inside the adapter where a transparent monitor cannot
be demonstrated. Inspecting a raw payload pointer after completion is forbidden;
copy small metadata at observation time.

## Observation and storage

Use a small C++ observer interface with an optional no-op implementation. Hooks
must not call `wait`, schedule IP events, change delays, acquire payload ownership,
or alter functional state. Expensive formatting is optional and can be deferred.
Snapshot IDs and scalar metadata, not proprietary payload content by default.

Proposed modes are counters-only, selected events, and full event trace. Record
mode and loss counts. Any data loss invalidates metrics that depend on the missing
events. A bounded trace never silently overwrites evidence while reporting exact
results. The pilot's synchronous CSV writer is for small tests, not the eventual
high-throughput capture path.

Start with CSV/JSON artifacts for inspection. Add an indexed format only after
profiling representative traffic volume. Maintain event schema versions and
migration rules independently of model versions.

## Runner and reproducibility

An immutable run directory should hold resolved configuration, workload/seed,
model and RTL revisions, adapter revision, build commands, toolchain and SystemC
versions, executable/input hashes, trace configuration, clock definitions, host
details, logs, termination reason, raw data, metric output, and comparison report.
Capture dirty-source hashes when a clean revision is unavailable.

Use argument arrays for subprocesses, explicit working directories, timeouts,
unique output directories, and process-tree cleanup. Record wall-clock timeout
separately from simulated timeout, normal drain, assertion, crash, and
configuration failure. A partial run is not a successful zero-throughput result.

## Analysis and presentation

Pure offline functions calculate metrics from canonical observations. Raw traces
are immutable; derived tables identify source run and analysis version. The
report shows run validity, scope of RTL qualification, workload, major KPIs,
latency/stall breakdown, and links to the first mismatch. Unsupported or
unobservable metrics are marked unavailable, never filled with zero.

The first UI is a CLI plus a portable HTML report. A dashboard is a later layer
over the same artifacts and APIs, after timing and correlation are trustworthy.

