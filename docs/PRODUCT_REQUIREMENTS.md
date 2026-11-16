# Product requirements and comparable capability target

Status: proposed requirements, with user priorities recorded in [index](README.md).
R0 is the existing WDT baseline. R1 is a qualified single-link CLI release;
R2 covers selected multi-IP paths. R3 adds architecture exploration. R4 contains
optional UI, power and broader ecosystem work. Releases are defined in [roadmap](ROADMAP.md).

## Users and decisions the platform must support

The TLM owner integrates existing models and explains their timing assumptions.
The RTL owner provides equivalent workload execution, monitors and baseline
evidence. The performance engineer asks which mechanism limits a KPI and what
changes improve it. The release maintainer reproduces results across revisions.

Core questions: What is the latency distribution under a stated load? Where does
time accumulate? When do queues or credits limit useful throughput? Which source
is starved? Does a parameter change improve the KPI without violating correctness?
How closely does this model agree with RTL for this configuration? Which modeled
mechanisms justify using the result outside the calibration workload?

The platform measures mechanisms already represented in the model. If a model
omits a mechanism, the owner must add it as an explicit modeling task or restrict
the prediction envelope. Wrapping an IP does not manufacture missing accuracy.

## Comparison boundary

Synopsys advertises SystemC modeling, model libraries, task/trace workloads,
performance and power analysis, parameter exploration, graphical authoring and
CLI automation. Those categories motivate the target; the public feature list
does not establish a benchmark of our implementation. [Official overview](https://www.synopsys.com/verification/virtual-prototyping/platform-architect.html)

| Capability family | Current evidence | Proposed comparable capability | Release |
|---|---|---|---|
| Existing-model execution | One WDT launcher | Registry, native/external adapters, supported toolchain profiles | R1 |
| Workload creation | Sequential register script | Concurrent offered traffic, feedback, trace and dependency graph replay | R1/R2 |
| Performance diagnosis | WDT event/latency report | Per-flow latency, queue/credit/stall diagnosis, saturation and fairness | R1 |
| Repeatable exploration | Small parameter sweeps | Constrained experiment matrices, sensitivity, Pareto tradeoffs and caching | R2/R3 |
| Model composition | Fixed WDT instance | Explicit topology, compatible bridges, routing, shared resources and clocks | R2 |
| Libraries | WDT only | Qualified internal IP catalog plus labeled reusable synthetic components | R1-R3 |
| RTL evidence | Independent WDT reference | Versioned protocol profiles, importers and per-KPI qualification | R1/R2 |
| Team delivery | Local Git/evidence | CLI packages, automated gates, portable evidence bundles | R1/R2 |
| Interactive authoring | None | UI on the same application API and schemas | R4 |
| Power/software/SoC ecosystem | None | Calibrated power states, workload mapping and selected memory/compute models | R3/R4 |

Multi-die exploration requires explicit die-to-die mechanisms; Synopsys's
multi-die offering includes UCIe models. Our R2 requires independently validated
models and bridges for each selected path. [Official multi-die datasheet](https://www.synopsys.com/content/dam/synopsys/verification/datasheets/platform-architect-multi-die-ds.pdf)

Comparable means a developer can perform the agreed experiments, obtain defined
KPIs and root-cause evidence, reproduce them and qualify predictions against RTL.
It does not mean matching every commercial model, supported platform, capacity,
or support offering. A direct runtime/usability comparison requires access to both
tools, equivalent models/workloads and a recorded benchmark protocol.

## Functional requirements

MUST is required for the named release; acceptance IDs refer to [verification](VERIFICATION_PLAN.md).

| ID | Required behavior | Release | Acceptance |
|---|---|---|---|
| REQ-01 | Discover versioned adapters and reject unsupported interface/config combinations | R1 | AT01, AT03 |
| REQ-02 | Preserve hybrid timing, transport ownership, payload lifetime and reset behavior | R1 | AT02, AT03 |
| REQ-03 | Support integer resolution/time domains and explicit annotation ownership | R1 | AT02 |
| REQ-04 | Drive multiple outstanding operations and distinguish offered/admitted/completed traffic | R1 | AT04 |
| REQ-05 | Capture resource visits, queue levels, credits, stalls, retries and logical identity when observable | R1 | AT05 |
| REQ-06 | Compute defined KPI populations, windows, tails and conservation without hiding failures | R1 | AT06 |
| REQ-07 | Compare equivalent RTL/TLM experiments with ordering domains and declared bounds | R1 | AT07, AT08 |
| REQ-08 | Retain reproducible build/input/environment/trace provenance and immutable analysis revisions | R1 | AT09 |
| REQ-09 | Separate execution validity, evidence validity and accuracy qualification | R1 | AT08, AT09 |
| REQ-10 | Support parameter matrices, seed sets, repeated trials, bounded jobs and resumable batches | R1 | AT10 |
| REQ-11 | Expose all R1 flows in CLI with machine-readable output and stable exit codes | R1 | AT11 |
| REQ-12 | Qualify at least one existing link-IP profile; declare UALink/UCIe/PCIe support individually | R1 then R2 | AT07 |
| REQ-13 | Keep WDT baseline and a generic concurrency fixture in regressions | R1 | AT01, AT04 |
| REQ-14 | Compose compatible adapters with explicit topology, bridges and shared-resource accounting | R2 | AT12 |
| REQ-15 | Support branching workload dependencies and open/closed-loop replay with preserved intent | R2 | AT04, AT12 |
| REQ-16 | Compare constrained alternatives with bottleneck evidence, sensitivity and Pareto results | R3 | AT13 |
| REQ-17 | Package qualified profiles, examples, limitations and migration tools as a reusable catalog | R2 | AT01, AT14 |
| REQ-18 | Provide calibrated power/energy estimates with uncertainty and activity provenance | R4 | AT15 |
| REQ-19 | Provide an optional interactive interface using CLI-equivalent application services | R4 | AT16 |

## Nonfunctional requirements

| ID | Requirement | Release | Acceptance |
|---|---|---|---|
| NFR-01 | Windows is release platform; isolate OS/toolchain dependencies for a later Linux qualification | R1 | AT14 |
| NFR-02 | Same pinned build, inputs and seed reproduce semantic observations under declared determinism | R1 | AT02, AT09 |
| NFR-03 | Bound trace buffers and analysis memory; report loss and prevent incomplete exact claims | R1 | AT05, AT17 |
| NFR-04 | Enforce host/simulation/drain timeouts, cancellation, interruption recovery and disk-error handling | R1 | AT09 |
| NFR-05 | Run locally without mandatory cloud services; protect private payloads and restrict exported artifacts | R1 | AT14 |
| NFR-06 | Version contracts independently; preserve v1 read/run compatibility and explicit migrations | R1 | AT01 |
| NFR-07 | Publish measured throughput, memory and probe overhead on a named reference host | R1 | AT17 |
| NFR-08 | Every supported claim links to a test, qualification envelope and known limitations | R1 | AT07, AT14 |

Proposed engineering capacity targets, subject to host selection at G0: analyze
10 million resource/lifecycle events with <=2 GiB peak analysis RSS; maintain a
bounded capture buffer; counters-only median overhead <=5% on a CPU-bound
representative workload with a runtime long enough to dwarf startup. Publish full
trace throughput/overhead rather than assuming the same budget. These are targets,
not measured results. AT17 defines measurement; no hardware-accuracy percentage is
approved by these targets. Requested sample sizes and runtime volume come from intake.

## Release exclusions and constraints

No automatic RTL-to-TLM conversion or universal protocol-compliance claim.
R1/R2 do not require full software boot, analog PHY/channel simulation, commercial
model redistribution, parallel execution of one SystemC kernel, or power analysis.
CLI reports may remain HTML/CSV; developing a web application is deferred.
Linux support is designed into interfaces but is not advertised until tested.
All protocol revisions/options come from supplied model evidence, not a default
assumption that a family name implies the latest or every standard feature.
