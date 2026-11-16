# Platform plan

Draft for review, 2026-11-17.

## Objective

Let a TLM IP developer give RTL engineers repeatable answers about latency,
throughput, contention, and event timing using existing SystemC models. Start
with one demonstrably correlated IP, then extend to UALink, UCIe, PCIe, and
multi-IP paths. Preserve the models' current hybrid timing implementation.

The intended product is a focused alternative for the performance experiments
you need from a larger architecture tool. It is not initially a replacement for
its model catalog, graphical platform authoring, power analysis, or full SoC
software execution. Synopsys describes Platform Architect as a SystemC-based
architecture exploration and performance/power analysis tool; this project takes
a narrower scope. [Product reference](https://www.synopsys.com/verification/virtual-prototyping/platform-architect.html)

## Confirmed requirements

- Windows; Accellera/OSCI SystemC 2.3.4.
- Existing IPs can mix timed callbacks, PEQs, clocked processes, and transaction
  interfaces. No requirement to rewrite them into a pure LT or AT style.
- RTL engineers are the consumers of performance results; TLM engineers own the
  models and explain timing differences.
- A simple new hybrid WDT is the first test IP.
- RTL evidence format is flexible. Prefer semantic transaction and cycle-event
  traces first; retain waveforms for investigating disagreements.

## Proposed workflow

1. **Describe the model.** Register interface types, clock/reset behavior,
   timing ownership, observability, unsupported behavior, and model revision.
2. **Define an experiment.** Fix topology, IP settings, clocks, workload, seed,
   warm-up, measurement window, stop/drain rules, and required metrics.
3. **Validate the configuration.** Reject unsupported settings and incompatible
   timing contracts before simulation.
4. **Build and run.** Launch one simulator process per experiment, retaining
   command, logs, hashes, dependency versions, and exit status.
5. **Observe.** Capture passive boundary events and optional internal queue,
   arbitration, credit, and PEQ events with explicit timestamp semantics.
6. **Analyze.** Produce latency distributions, throughput over time, occupancy,
   stalls, event sequences, and accounting checks.
7. **Correlate.** Compare with an RTL baseline under the same experiment contract.
   Locate the first divergence and qualify which metrics/configurations agree.
8. **Sweep and regress.** Change controlled parameters and compare qualified
   results with earlier revisions; retain evidence for every conclusion.

## Minimum useful platform

| Capability | First useful implementation | Later extension |
|---|---|---|
| Model integration | Compile-time adapter or existing testbench launcher | Reusable socket monitors and adapter catalog |
| Workloads | Scripted directed traffic and seeded generators | Trace replay and dependency-driven workloads |
| Configuration | Versioned JSON and explicit units | Optional UI and richer topology editor |
| Observation | Counters plus bounded/full event trace | Filtered capture and indexed storage |
| Analysis | CLI, CSV, static HTML reports | Interactive timelines and comparisons |
| Correlation | WDT event/transaction comparison | Protocol-specific importers and matching |
| Automation | Local repeatable runs and CTest | Parallel sweeps and CI integration |

## Acceptance criteria

The first platform milestone must reproduce a WDT run from recorded inputs,
explain register and timeout latency, detect an intentionally injected timing
error, and separate a failed experiment from a failed accuracy check. WDT exact
cycle comparison is the proposed first accuracy gate; it requires an independent
RTL reference, which is not supplied yet.

For real link IPs, acceptance is per KPI, workload, and configuration. Exact
agreement can be required for deterministic event timing. Aggregate statistical
metrics need explicit tolerances, adequate sample counts, and repeated seeds
where relevant. There is no agreed blanket percentage tolerance yet.

Measure runtime and trace overhead on the same machine and workload. Report
TLM-versus-RTL speedup only after both complete equivalent work with matching
measurement boundaries. Do not sacrifice timing fidelity to meet a guessed
speedup target.

## Initial limits

No automatic conversion of RTL to TLM, no universal guarantee of cycle accuracy,
no protocol compliance certification, and no distributed simulation in the MVP.
The system can only predict mechanisms represented in the model. Missing credit
returns, arbitration, retries, clock crossings, or queue capacities must appear
as limitations in the result rather than being hidden by tuned constant delays.

## Main risks and responses

| Risk | Response |
|---|---|
| Low-load latency matches while saturation diverges | Include burst, backpressure, queue-full, and sustained-load tests |
| Probes count annotations and elapsed delays twice | Record both timestamps; assign each boundary one timing owner |
| RTL and TLM stimulate different accepted traffic | Compare offered and accepted traffic separately; preserve feedback |
| Tracing changes results or overwhelms storage | Passive hooks, trace-off equivalence check, loss counters, bounded capture |
| C++ ABI/library mismatch on Windows | Record compiler/runtime/bitness/C++ standard; rebuild compatible libraries |
| One WDT success is mistaken for link-IP qualification | Require a real concurrent link IP as a separate milestone |

