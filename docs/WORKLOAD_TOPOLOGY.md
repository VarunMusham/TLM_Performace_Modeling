# Workload and topology design

Status: proposed R1/R2; REQ-04/10/14/15. Current scripts are serial WDT workloads.

## Workload semantics

Each logical operation specifies source, destination/address region, flow/class,
operation kind, payload metadata, earliest offer or dependency set, and identity.
Admission is an adapter-defined handshake, not merely the driver's function call.
Offers that cannot be admitted remain pending according to an explicit policy
(`wait`, `reject`, or protocol-supported drop). A source never emits an unbounded
queue unless that queue and its memory cap are modeled intentionally.

Support directed operations, deterministic seeded generators, offered trace
replay and dependency graphs. Graph edges carry conditions such as response
acceptance, successful completion, failure alternative or barrier. Reject cycles
unless represented by an explicit bounded repeat construct; expand/freeze the
iteration policy and seed derivation. A blocked operation reports unmet
dependencies and source throttling as separate reasons from DUT backpressure.

| Driver mode | Meaning | Required labels/evidence |
|---|---|---|
| Open-loop | Offer schedule independent of responses | Offered/accepted/dropped counts and source-buffer policy |
| Closed-loop | New operations depend on actual responses or outstanding window | Dependency graph, admission counters, feedback latency |
| Offered-trace replay | Replay intended offers with identical backpressure policy | Input hash, mapping/version and unapplied offers |
| Accepted-trace replay | Drive externally observed admissions | Diagnostic-only admission assumptions; cannot validate backpressure |

Native source/sink drivers enforce outstanding limits, credits where owned by the
source, and response readiness inside the kernel. Random streams are derived from
root seed plus stable component/flow IDs; adding a flow must not reshuffle unrelated
flows' streams. Record PRNG algorithm/version and materialized inputs when feasible.
Prevalidation checks structural feasibility, never predicts an arbitrary IP's
actual completion times using the WDT formula.

## Windows, stopping and drain

Reset/setup precede warm-up; warm-up may include measured mechanism initialization.
Measurement is `[start,end)`. Stop generating new root offers at end, then drain
admitted work to deadline. Specify whether already queued but unadmitted offers
are withdrawn or drained; report them separately. Dependent responses required
to finish admitted logical work may continue; they are not new root offers.
Specify atomic same-time boundary rules by semantic time, not host event order.

Completion-window throughput includes successful work from pre-window admissions.
Admission-cohort latency follows in-window admissions through drain. Unfinished
admissions are censored and gate policy determines whether the experiment is
invalid or analytically incomplete. Drain expiry always prevents a clean pass
when completion evidence is required. Keep the timeout mechanism independent of
the DUT watchdog/IP being measured.

## Minimum experiment families

| Family | Controls | Evidence/question |
|---|---|---|
| Isolated | One operation, controlled sink, nonzero annotation | Endpoint latency and timing ownership |
| Offered-load curve | Rates below/near/above capacity; fixed sizes and seed set | Throughput knee, admission delay, queue growth |
| Burst/size mixture | Burst length, interburst gap, size/class mix | Tail latency and buffering |
| Outstanding sweep | Number of in-flight requests/tags/source windows | Concurrency needed to fill the link |
| Credit/backpressure | Pool depth, return delay, sink stalls | Credit-limited throughput, resource occupancy |
| Contention | Two+ flows/requesters sharing a resource; priority/weights | Fairness, starvation, head-of-line delay |
| Retry/recovery | Controlled error policy, replay pressure, reset under load | Wire cost, duplicate prevention, recovery latency |
| Clock variation | Domain periods/phases and supported changes | Quantization/crossing effects |
| Holdout | Combined settings and reserved seeds | Prediction outside the tuning workload |

Feature-dependent families are skipped only with a stated model/profile reason,
not silently passed. Each test links to mechanism probes and qualification policy.

## Synthetic infrastructure fixture

Build an original `credit_link_fixture` independent of production protocols:
two sources, finite ingress queues, configurable service time/serialization,
round-robin or explicit fixed-priority arbitration, finite shared credits,
delayed returns, controllable sink backpressure, optional retried attempts and
ordered/reordered completion. Use separate service/return clock options.
This fixture establishes generic concurrency accounting; it is not a PCIe,
UALink or UCIe model. A small independent reference/analytical queue fixture
provides exact expectations for selected directed cases.

For fixed service time S and one server, completed work cannot exceed the
service capacity after initialization; a finite credit window K and return
round-trip R creates a throughput ceiling near K/R under the fixture's declared
semantics. Derive exact expected edges from the fixture contract, not from these
steady-state bounds. Test K=1, queue-full, simultaneous credit return/admission,
and reset of all reservations. Document arbitration tie-breaking explicitly.

## R2 topology contract

Topology is a typed graph of instances, named ports, connections, address/routing
maps, clocks/resets and shared resources. Validate direction, payload/phase
compatibility, width/unit/rate domains, clock crossing, address overlap,
routing reachability and queue ownership. Structural loops are not automatically
deadlocks; analyze declared dependency/resource cycles and test runtime progress.

First composition: two sources -> shared finite fabric/bridge -> one qualified
link -> controllable destination. Next add a second qualified IP across an
explicit compatible bridge. WDT can supervise a control-path scenario but does
not stand in for high-throughput shared-resource testing. Endpoint-to-endpoint
lineage must survive every bridge and fragment/retry transformation.

Give each physical resource one accounting owner. End-to-end useful bytes count
at the final consumer once; per-hop wire bytes count at their own links. Do not
sum hop payload throughput into system goodput or add overlapping queue/service
intervals into a false end-to-end latency decomposition.
