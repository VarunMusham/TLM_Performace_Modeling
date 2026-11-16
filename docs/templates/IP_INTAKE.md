# IP intake and evidence worksheet

Copy once per model/profile into an owner-controlled integration folder. Private
paths/snippets may remain outside public Git. Summarize evidence with revision,
file, symbol and line/section rather than copying proprietary implementation.
Status: `confirmed`, `unknown`, `unsupported`, or `not_applicable`. Unknown answers
are acceptable; attach an owner and resolution action. Never infer protocol
version, timing or observability solely from the module's name.

## A. Ownership and build

| Question to answer | Where to inspect | Answer/evidence |
|---|---|---|
| IP family, exact model revision and protocol revision/options? | Release notes, configuration headers, model owner | UNKNOWN |
| Which block/layer is modeled and what lies outside its boundary? | Top module, design specification, block diagram | UNKNOWN |
| Who can change model code and who supplies RTL evidence? | Repository ownership/release process | UNKNOWN |
| Build/test command from a clean Windows shell? | CMake/Make/batch scripts and existing regression launcher | UNKNOWN |
| Compiler, architecture, C++ standard, SystemC, simulator and DLL dependencies? | Build logs and loaded binaries | UNKNOWN |
| License/environment restrictions; may binaries/traces be archived? | Owner/toolchain policy; record prerequisite names, not secret values | UNKNOWN |
| First minimal successful test and expected output? | Existing directed test, simulation log | UNKNOWN |
| Can code/build dependencies be pinned and hashed? | Repository and dependency manifests | UNKNOWN |

## B. Interfaces and ownership

Inventory each port independently; separate configuration/control from datapath.

| Instance/port | Socket/signal/custom type | Payload/extensions | Initiator/target/peer | Binding/testbench evidence | Concurrent limit |
|---|---|---|---|---|---|
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

For every transport path answer: who allocates/releases payloads, may the callee
retain a reference, is a memory manager used, are extensions copied/cloned,
can responses reorder, what identifies one logical operation across reuse/retry,
what means admission/completion, and what DMI/debug/invalidation paths exist?
For custom phases list legal call/return transitions; do not substitute the TLM
base protocol unless the model actually implements it.

## C. Timing and reset evidence

| Question | Inspection procedure | Answer/evidence |
|---|---|---|
| What consumes incoming annotation? | Follow transport call to each `wait`, PEQ notify, callback and return | UNKNOWN |
| Is time returned annotated, consumed, or both across different boundaries? | Trace one transaction with a nonzero annotation | UNKNOWN |
| Which process advances each state machine? | `SC_METHOD`, `SC_THREAD`, sensitivity, PEQs/events | UNKNOWN |
| Period/phase/resolution and supported frequency changes per domain? | Clock construction, period parameters, reset/CDC logic | UNKNOWN |
| Same-time priority and output visibility? | Clock method ordering, event notifications, signal updates | UNKNOWN |
| Reset behavior for admitted work, queue entries, credits and callbacks? | Reset handlers and tests with outstanding traffic | UNKNOWN |
| Temporal decoupling/quantum policy? | Quantum keeper/local-time use and synchronization sites | UNKNOWN |
| Idle/low-power/training/recovery timing represented? | State transitions and delay ownership | UNKNOWN |

Produce a one-transaction timeline: offer -> admission -> queue/PEQ -> service
-> response -> consumer acceptance. Label observed time, effective time, owners,
domains and unobservable endpoints. Attach both annotated and zero-delay examples.

## D. Performance mechanisms

For each queue, arbiter, credit pool, replay buffer and clock crossing record:
capacity/unit, producer, consumer, service policy, flow/class mapping, exact
allocation/release boundaries, reset policy and observability. Mark whether each
mechanism is implemented, approximated or omitted. Include output backpressure
and source outstanding limits; a model that accepts everything cannot establish
real admission delay without an explicit mechanism.

| Resource ID | Type/unit/capacity | State owner | Update symbols | Probe permission | Approximation/impact |
|---|---|---|---|---|---|
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Can hooks be added inside the model? If no, identify exposed counters/callbacks,
boundary-only metrics and unobservable breakdowns. Never reconstruct hidden
queue/credit behavior by assigning an arbitrary constant delay.

## E. RTL and workload evidence

- RTL top, revision, simulator/build flags, testbench entry point: UNKNOWN.
- Equivalent clocks/reset/configuration and traffic generator: UNKNOWN.
- Monitor signals/interfaces and sampling region: UNKNOWN.
- Common logical identity mapping (including split completions/retry): UNKNOWN.
- Supported raw format and exporter version; one sample trace/counters: UNKNOWN.
- Available directed/stress tests; holdout seeds reserved before tuning: UNKNOWN.
- Target KPIs, expected load envelope, transaction sizes and runtime volume: UNKNOWN.
- Explicit tolerances/precision requirements and decision owner: UNKNOWN.
- First useful question, e.g. latency under credit pressure: UNKNOWN.

## F. Practical source searches

Run within the owner's source root using `rg` where available. These patterns
locate candidates; a hit does not prove behavior, and macro/generated code may
require inspecting expansions and runtime traces.

```powershell
rg -n 'simple_(initiator|target)_socket|tlm_.*socket|b_transport|nb_transport|transport_dbg|get_direct_mem_ptr|invalidate_direct_mem_ptr' .
rg -n 'peq_with|peq_|notify\(|wait\(|SC_METHOD|SC_THREAD|SC_CTHREAD|sensitive|quantumkeeper' .
rg -n 'sc_clock|sc_time|reset|rst_n|posedge|negedge|always_ff' .
rg -ni 'credit|fifo|queue|arbiter|arbitrat|replay|retry|outstanding|backpressure|ready|valid' .
rg -n 'sc_main|int main|add_executable|SystemCLanguage|vsim|xrun|vcs|iverilog|verilator' .
```

Use the existing build first. Run one transaction and inspect its call tree and
monitor timestamps. Repeat with nonzero annotation, stalled sink and reset while
pending. These three perturbations often reveal timing/ownership assumptions that
declarations alone cannot. Do not modify timing as part of information gathering.

## G. Readiness decision

| Level | Required evidence | Missing information consequence |
|---|---|---|
| Can plan adapter | Boundary, build owner, interface inventory | Keep discovery ticket open |
| Can run smoke experiment | Reproducible build; payload/timing/reset ownership; minimal workload | Native integration blocked until known |
| Can report a KPI | Defined endpoints/units and required probes/counters | That KPI is unavailable; other observed KPIs may proceed |
| Can qualify against RTL | Equivalent experiment, raw evidence, identity mapping, approved tolerances | Results remain uncorrelated/inconclusive |
| Can compose models | All binding/bridge/clock/address/ordering semantics | Topology unsupported until explicit bridge/contract exists |

Choose the first real link by readiness, not brand or guessed complexity. Record
selected profile, rejected alternatives and missing dependencies in an ADR.
If none is ready, develop generic infrastructure with a synthetic fixture and
keep the real-IP release gate unmet. Completed by / reviewed by / date: UNKNOWN.
