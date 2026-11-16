# IP profiles and experiment requirements

Status: design for supplied hybrid models; production code and exact revisions
are not yet supplied. Complete [intake](templates/IP_INTAKE.md) before selecting
profile parameters. These are modeling requirements, not normative protocol
definitions or compliance tests. Licensed specifications and IP design documents
control exact encodings, timing constants, optional features and legal behavior.

## Common profile manifest

Record family, specification document IDs/revisions/errata, implemented layer(s),
role/topology, transport boundary, model/RTL revisions, supported traffic classes,
data-size/rate/width units, clock/reset policy, observation points, omissions and
parameter constraints. Distinguish configured, negotiated and measured values.
Do not infer usable payload bandwidth from lane rate alone: define encoding,
packet/flit overhead, idle/training/replay costs and the accounting layer actually
represented by the model. Lane rate, transfers/s, bits/s and bytes/s are different
quantities; adapters own conversions with revision-specific independent fixtures.

Each family needs a control-plane setup and a datapath workload surface. Matching
register accesses alone does not establish datapath performance correlation.
If only a subset/layer is supplied, limit the question to that boundary and model
the external environment explicitly. Electrophysical behavior is outside scope
unless provided as a reviewed latency/error abstraction with provenance.

## WDT profile: reference infrastructure fixture

Use [WDT_SPEC](WDT_SPEC.md) unchanged. Required signals/events: clock/reset,
register submit/readiness/commit/error, timeout, IRQ and reset request. Required
tests include exact-edge reload, enable/disable, W1C, reset cancellation,
annotation and tracing equivalence. Its inflight limit is one. It validates
kernel timing discipline and the release pipeline; it does not qualify link
queues, arbitration or bandwidth. Keep legacy v1 traces as compatibility evidence.

## PCIe profile

Select endpoint/root-port/switch role, spec revision, negotiated width/rate,
traffic classes/virtual channels, packet/flit mode, supported request types,
addressing and model boundary. Determine whether the model represents transaction,
data-link and PHY abstractions or only one of them. Exact options are intake
answers, not inferred from family. [PCI-SIG specification catalog](https://pcisig.com/specification-overview/pci-express-base)

| Mechanism to inventory when modeled | Required observations | Tests/KPIs |
|---|---|---|
| Posted/non-posted/completion paths | Request type, offer/admit, useful bytes, completion fragments/status | Read/write mixes; read round-trip vs posted delivery; split completion accounting |
| Tags/outstanding windows | Allocation/release, request generation/epoch, source stall reason | Tag pressure and reuse, reordered completions, p95/p99 by size/class |
| Flow-control pools | Pool type/unit, allocation/return and capacity | Pool exhaustion/return delay; separate flow-control classes |
| Queues/arbitration/ordering | Queue visits, service owner, traffic/order domains | Contention, priority inversion/starvation, head-of-line blocking |
| Serialization/replay | Transmitted attempts, overhead layer, replay occupancy and triggers | Goodput vs wire rate, replay cost and recovery |
| Power/link state transitions | State enter/exit, traffic acceptance policy, modeled wake latency | Wake/retrain impact if represented; unavailable otherwise |

Never treat posted request acceptance as remote memory visibility without a
declared endpoint guarantee. Completion tags may be reused: join with source and
generation. Fragmented read responses complete logical bytes only once. Separate
protocol correctness checks from performance tolerances. Link electrical compliance
and exhaustive enumeration/OS behavior are not implied by this profile.

## UCIe profile

Identify die-to-die role, protocol mapping, package/profile, revision, supported
streaming/PCIe/CXL mapping if any, module/lane configuration, adapter interface
and modeled PHY boundary. The public UCIe description spans package-level
physical/protocol/software layers; that does not mean every supplied model covers
all of them. [UCIe specifications](https://www.uciexpress.org/specifications)

| Mechanism to inventory when modeled | Required observations | Tests/KPIs |
|---|---|---|
| Protocol mapping and adapter buffering | Mapping ID, fragment/packing boundaries, queue entries | Payload-size mix and packing efficiency; protocol-to-link latency |
| Flow control/backpressure | Ready/admission, buffers/credits and return ownership | Receiver stalls, full buffers, sustained/burst load |
| Module/width/rate and serialization | Negotiated active configuration, transferred/wire bytes | Throughput by direction/configuration; overhead decomposition |
| Retry/error handling | Attempt identity, replay trigger/occupancy | Retry cost, corrected/replayed data, recovery timing |
| Die clocks and crossings | Domain/epoch and crossing service points | Phase/ratio sweep, CDC latency and pressure |
| Initialization/repair/low-power | Modeled state transitions and traffic eligibility | Startup/wake/reconfiguration performance where supported |

Specify which layer owns retry and framing to avoid charging both the carried
protocol and the die-to-die adapter for the same modeled cost. A UCIe connection
does not automatically provide PCIe semantics to a custom streaming payload.
Cross-die bridges need functional mapping and independent performance validation.

## UALink profile

Identify accelerator/switch or other supplied role, exact specification set,
layer boundary, topology/routing and supported operations. Public documents span
multiple revisions; choose the documents the model implements rather than
silently upgrading it. [UALink specification catalog](https://ualinkconsortium.org/specification/)

| Mechanism to inventory when modeled | Required observations | Tests/KPIs |
|---|---|---|
| Supported request/response operations | Logical operation/source/destination, bytes, response status | Size/operation mixes, end-to-end latency, outstanding-window sweep |
| Source/destination injection | Offered/admitted traffic, source queues, receiving acceptance | Injection vs delivered bandwidth; incast and sink saturation |
| Switch paths/contention | Route/hop identity, queue/service/arbitration/ordering domains | Fan-in/fan-out, shared-link contention, fairness and head-of-line effects |
| Flow control and retries | Pool ownership/units, reservations/returns, attempts | Capacity/return-delay sensitivity and replay cost |
| Endpoint service time | Remote operation/service boundaries | Separate link delay from target/accelerator delay |
| Revision-specific optional functions | Explicit capability and cost model | Enable only supported functions with their own workload and RTL evidence |

Do not assign undocumented operations/credit mechanisms to a model. Load/store,
atomic, collective or in-network functions each require evidence that the selected
profile actually implements them. A point-to-point model cannot qualify a routed
fabric simply by multiplying its single-link latency by hop count.

## Selection and per-profile qualification

Choose the first IP with reproducible builds, known ownership, useful probes and
RTL workload access. Do not prescribe PCIe/UALink/UCIe order before intake.
R1 qualifies one selected real profile; all three families need separate records
before the platform advertises them. R2 composition has an additional system
qualification; individual-IP passes alone do not qualify interactions.

Each profile must supply: low-load latency tests, offered-load/saturation curves,
two-flow contention, backpressure/resource limits, reset with pending work,
reordering/retry cases when supported, and reserved holdout seeds/configurations.
Use [qualification template](templates/QUALIFICATION.md) with explicit exclusion
of unsupported mechanisms. Unknown RTL availability makes accuracy uncorrelated,
not automatically failed or passed.
