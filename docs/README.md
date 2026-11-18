# Developer handoff: hybrid TLM performance platform

For pilot customers, start with the [customer guide](CUSTOMER_GUIDE.md) and
[external adapter reference](EXTERNAL_ADAPTERS.md). CLI 1.1.0 adds source/testbench
adapters, a Python-only demo, C++ starter, boundary metrics and offline SystemC
setup. The design documents below describe a broader future program; external-1
does not close protocol qualification or multi-IP composition requirements.

Design baseline: 2026-11-17. Implementation inspected at `43ba848`.
This pack specifies the next development program; it does not declare the
proposed contracts implemented. Runtime instructions remain in [CLI](CLI.md).

## User decisions and scope

- First production release: performance analysis and RTL correlation of existing
  hybrid IPs, followed by multi-IP systems.
- Target families: UALink, UCIe, PCIe; WDT is the executable foundation fixture.
- Windows first, with a future Linux port. CLI first; interactive UI later.
- Actual IP interfaces, protocol revisions, internal probes, and RTL environments
  are unknown. The owner will determine them from code using the intake worksheet.
- Team size and delivery date are unspecified. Roadmap effort is an estimate,
  not a staffed schedule. Source/model access remains a dependency.

## Reading and implementation order

| Order | Document | Developer outcome |
|---|---|---|
| 1 | [Product requirements](PRODUCT_REQUIREMENTS.md) | Understand scope, users, requirement IDs, and what comparable means |
| 2 | [Implementation audit](GAP_ANALYSIS.md) | Know which code is reusable and which WDT assumptions must move |
| 3 | [IP intake worksheet](templates/IP_INTAKE.md) | Extract interface and RTL evidence from each existing model |
| 4 | [Architecture](ARCHITECTURE.md) | Understand modules, process boundaries and migration |
| 5 | [Adapter contract](ADAPTER_CONTRACT.md) | Implement a native or external adapter without changing IP timing |
| 6 | [Data contracts](DATA_CONTRACTS.md) and [timing](TIMING.md) | Implement versioned schemas, identity, time and trace semantics |
| 7 | [Workloads and topology](WORKLOAD_TOPOLOGY.md) | Build concurrent traffic and compose compatible models |
| 8 | [Protocol profiles](PROTOCOL_PROFILES.md) | Define IP-specific mechanisms, probes and experiments |
| 9 | [Metrics](METRICS.md) and [correlation](CORRELATION.md) | Compute defensible results and compare independent evidence |
| 10 | [Verification plan](VERIFICATION_PLAN.md) | Implement acceptance suites and qualification gates |
| 11 | [CLI and operations design](CLI_OPERATIONS.md) | Deliver reliable runs, packaging, evidence and diagnostics |
| 12 | [Roadmap](ROADMAP.md) and [implementation backlog](BACKLOG.md) | Select tickets with dependencies and completion criteria |
| 13 | [Decision register](DECISIONS.md) and [sources](REFERENCES.md) | Resolve unknowns and preserve the basis of decisions |

Supporting artifacts: [qualification record](templates/QUALIFICATION.md),
[architecture decision template](templates/ADR.md), and a
[proposed scenario-v2 example](design_examples/scenario-v2.json).
The v2 example is a design specimen, **not accepted by the current CLI**.
The [data contract](DATA_CONTRACTS.md) also links event and comparison-policy
specimens so developers can review field shapes before implementing schemas.

## Document authority and change rules

`PRODUCT_REQUIREMENTS` defines scope; `ROADMAP` defines ordering and release gates;
contract documents define proposed behavior; `BACKLOG` links implementation work
to acceptance tests. `CLI` describes current runnable behavior and `VALIDATION`
records observed results. Design changes must update the affected requirement,
contract, ticket and test together. A new release note identifies supported
adapters/profiles, schema versions and qualification envelopes.

Status vocabulary: **implemented** means present in inspected code; **validated**
means exercised by identified evidence; **proposed** means work to build;
**unknown** means evidence not provided; **deferred** means outside the release.
Unknown is never interpreted as supported, absent, or zero cost.

## Start here on day one

1. Reproduce the current WDT build/tests using [Windows setup](SETUP_WINDOWS.md).
2. Complete one intake per IP and select the first link by available evidence.
3. Implement B01-B04 from [BACKLOG](BACKLOG.md), retaining WDT v1 behavior.
4. Exercise concurrency with the synthetic credit-link fixture while the first
   real model is being integrated. Label its results synthetic.
5. Release a real-IP capability only after its independent qualification gate.

No blanket Platform Architect equivalence percentage is used. Progress is the
number of accepted capabilities and qualified experiments in the declared scope.
