# Decision and assumption register

Updated 2026-11-17 for the developer handoff. User-confirmed choices are requirements;
proposed technical choices remain reviewable with source evidence. Unknowns do not
block generic infrastructure unless the dependency below says they do.

## Confirmed

| ID | Decision and source | Consequence |
|---|---|---|
| D01 | User: first release analyzes/correlates existing IPs, then multi-IP | R1 real-link qualification precedes broad SoC scope |
| D02 | User: Windows now, possible Linux port | Isolate OS providers; qualify Windows first |
| D03 | User: CLI now, UI later | Implement application services and reports; defer GUI |
| D04 | Existing user requirement: SystemC 2.3.4 and hybrid/PEQ timing | Preserve model timing; don't force pure LT/AT rewrite |
| D05 | User targets UALink, UCIe, PCIe; WDT is base | Individual profiles and interaction-level qualification |
| D06 | User: interfaces unknown; document how owner answers from code | [Intake worksheet](templates/IP_INTAKE.md) is mandatory integration input |
| D07 | User requests local Git commits and final push to specified GitHub repository | Commit/review docs and push without rewriting remote history |

## Proposed engineering defaults

| ID | Default | Rationale / reconsideration condition |
|---|---|---|
| A01 | Python orchestration, native C++14 SDK; compatible models share one SystemC kernel | Reuse current stack; support existing external simulator launchers |
| A02 | Versioned JSON Schema plus semantic validators; v1 dispatch | Avoid ambiguous unsupported configuration; preserve baseline |
| A03 | Scalar passive hooks before transparent general monitors | Payload/timing ownership must be demonstrably preserved |
| A04 | Integer kernel ticks and resolution in fs; segmented domains | Support fast link models without floating-point identity |
| A05 | JSONL chunks and SQLite indexing first | Inspectability/bounded analysis; profile before adding formats |
| A06 | Local operation without mandatory services/cloud | Fits private IP workflow; enterprise deployment remains future scope |
| A07 | Select first link by evidence readiness | No assumed priority among protocol families |
| A08 | Exact WDT/synthetic directed checks; explicit per-KPI production policies | No blanket percentage tolerance |
| A09 | Synthetic credit-link fixture before production concurrency claims | Generic independent validation without inventing a protocol model |

## Open decisions and how to resolve them

| ID | Question/evidence needed | Owner role | Needed by / blocked work | Safe interim action |
|---|---|---|---|---|
| Q01 | Actual sockets/custom payloads/ownership and timing | TLM owner via intake B/C | G0, native adapter | SDK and synthetic fixture |
| Q02 | Protocol documents/revisions, optional mechanisms and boundary | Model owner via intake A/D | Profile schema and qualification | No family-specific numerical defaults |
| Q03 | Permission for hooks and observable internals | Model owner via resource inventory | Resource KPI claims | Boundary-only metrics where defined |
| Q04 | RTL top/simulator, workload control, raw monitors/identity | RTL owner via intake E | G3 accuracy pass | Uncorrelated TLM experiments |
| Q05 | Production compiler/runtime/SystemC installation and licenses | Integration owner via build evidence | Clean-host native integration | Retain tested MinGW baseline; external launch design |
| Q06 | KPI envelope, numeric tolerances and required precision | Performance+RTL owners | Qualification policy before tuning | Exact analytical fixtures only |
| Q07 | Reference host, trace volumes and capacity budgets | Platform/performance owners | AT17 and release capacity statement | Proposed 10M events/2 GiB and 5% counters-only targets |
| Q08 | First real profile and model availability | Project owner after intake | P3 sequencing | P1/P2 proceed independently |
| Q09 | Team size and delivery date | Project owner | Calendar commitment | Person-effort ranges only |
| Q10 | Private data export/redistribution and internal CI environment | Repository/IP owner | Packaging/export and private qualification CI | No mandatory upload; record local evidence |
| Q11 | Required bridges/topologies and model compatibility | System/TLM owner | R2 scope | Qualify a shared-resource synthetic topology |
| Q12 | UI/power/software-workload priority | User/product owner | R4 budgeting | Preserve extension seams; no UI implementation now |

Document accepted changes with [ADR template](templates/ADR.md), source evidence,
affected schemas/tickets/tests and migration. A reviewer may narrow a qualification
envelope, but cannot turn missing evidence into a pass.
