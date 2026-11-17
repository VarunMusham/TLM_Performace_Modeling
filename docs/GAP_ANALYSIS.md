# Implementation audit and engineering gaps

Inspected baseline `43ba848`, clean worktree before this documentation change.
Read source, configuration, tests and existing CTest evidence. This review did
not rerun simulation: the recorded baseline has 18 passing CTest entries including
20 unittest methods, with evidence detailed in [VALIDATION](VALIDATION.md).
The current executable path is WDT-specific despite reusable orchestration ideas.

| Source | Implemented behavior | Change needed | Ticket |
|---|---|---|---|
| `tlm_lab/config.py` | Hardcoded WDT adapter, fixed ns resolution, one clock, predicted strict-edge sequential offers | Dispatch to adapter schemas; common clock/window/graph validation; adapter owns timing | B02, B03 |
| `tlm_lab/events.py` | WDT kinds, scope, ID mapped by workload index, fixed 4-byte size, 3-row lifecycle, global architectural order | Generic identity/lineage/resource schema and protocol-defined partial ordering | B04, B08 |
| `tlm_lab/metrics.py` | WDT latency and state inference, inflight capacity 1, offered=accepted | Generic reducers for distinct populations and resources; protocol plug-ins | B06 |
| `tlm_lab/runner.py` | Local processes, retained binary, logs/hash manifest, paired RTL | Adapter launch contracts, recoverable state machine, dependency/build lock, streaming ingestion | B03, B07 |
| `tlm_lab/cli.py` | Sequential generator; selected WDT parameter axes; latency-only regression | Adapter-defined axes, workload graphs, broader KPI gates and resumable batches | B05, B10 |
| `tlm_lab/rtl.py` | Generated WDT testbench and semantic CSV export | Importer plug-ins, independent references, raw evidence equivalence contract | B08 |
| `examples/wdt/wdt.*` | Blocking TLM, PEQ, strict-edge counter, scalar CSV/digest | Keep timing intact; adapt observer surface and wrap as reference adapter | B01-B04 |
| `examples/wdt/scenario.cpp` | Text wire format, one initiator, fixed resolution, blocking workload | Retain v1 bridge; introduce generic native SDK and workload driver | B03, B05 |
| `tests/test_platform.py` | WDT boundaries, metrics and process tests | Add overlap, reordering, credit returns, independent stress/holdout and importer fixtures | B04-B09 |

## Trust and scalability work

1. Source hashes are captured at run time; they are not a build attestation linking
   those bytes to the binary. Introduce build manifests at compilation, retain
   adapter/RTL dependencies and compare them at launch (B07).
2. Copying an executable does not capture its shared runtime or commercial
   simulator environment. Package permitted redistributable dependencies; otherwise
   record prerequisites and diagnose replay incompatibility (B07/B11).
3. CSV/JSONL readers and correlation currently materialize collections. Introduce
   iterators, chunk indexes and bounded join/spill strategies before link-scale
   claims (B04/B06/B08).
4. Tail regression currently skips below 100 samples. That threshold alone does
   not establish adequate tail confidence. Add policy-owned precision/sample
   rules and explicit inconclusive gates (B06/B08).
5. One reference algorithm and a single-outstanding fixture cannot validate
   generic ordering, credit or retry handling. Build a synthetic stress fixture
   and then qualify a real model against independent RTL (B04/B09).
6. Current run directories are unique and hash-checkable, but the manifest/report
   are not authenticated and all failure paths need fault injection. Make final
   publication atomic, retain interrupted runs and version derived artifacts;
   do not market filesystem conventions as tamper-proof storage (B07).
7. Reset, output and timeout metrics inferred from WDT register addresses belong
   to the WDT plug-in, not the core metric engine (B02/B06).

These are observed limitations and required engineering work, not assertions of
unreproduced functional failures. Existing WDT validation remains useful.

Update for CLI 1.0.1 (2026-11-18): WDT JSON/JSONL outputs now publish atomically
without overwriting evidence; attempts are checkpointed before preparation, and
ordinary preparation/launch errors and single-run interruptions retain final
manifests when storage permits. New fault injection tests cover these paths.
Required hash coverage, canonical scalar validation, response timing and replay
response equivalence are checked. Item 6 remains open for host crashes, persistent
storage failure and the broader job lifecycle; other roadmap gaps remain open.

## Migration rather than replacement

Freeze representative v1 scenarios/raw/canonical outputs as golden fixtures.
Introduce a version-dispatch layer; move WDT logic behind one adapter. Run v1 and
new WDT paths against identical binary behavior and compare semantics. Only then
add the synthetic link, then the first real adapter. New resource events must not
force a WDT trace to pretend it has credits, wire traffic or a queue service model.
Changes to scenario, event, metric or qualification semantics require explicit
version increments and conversion provenance.
