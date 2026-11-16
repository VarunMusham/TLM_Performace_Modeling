# TLM Performance Lab

A CLI performance-analysis platform for RTL-oriented SystemC IP experiments,
including hybrid models with PEQ-driven timing. Windows and SystemC **2.3.4** are
the target environment. The first pilot is a small watchdog timer (WDT).

**Status: executable WDT CLI platform on SystemC 2.3.4.** Implemented: strict
scenario validation, configurable hybrid WDT, immutable evidence, canonical
events, metrics, HTML/CSV reports, independent Verilog correlation, seeded
workloads, sweeps, replay, regression gates, and trace-on/off profiling.
The WDT is an original example, not a production WDT. Qualification is per run;
real link-IP integration and graphical authoring remain future work.

```powershell
python -m tlm_lab run configs/wdt_scenario.example.json --rtl
python -m tlm_lab --help
```

See the [CLI guide](docs/CLI.md) for setup, commands, contracts, and limits.

For continued platform development, start with the
[developer handoff](docs/README.md). It includes requirements, implementation
audit, IP code-inspection worksheet, adapter/data/workload contracts, protocol
profiles, release gates, acceptance tests and an implementation backlog.
Future designs are explicitly distinguished from current WDT capabilities.

## Review these first

1. [Platform plan](docs/PLAN.md): scope, intended workflow, and success criteria.
2. [Architecture](docs/ARCHITECTURE.md): integration without changing IP timing.
3. [WDT specification](docs/WDT_SPEC.md): registers and exact timing decisions.
4. [RTL correlation](docs/CORRELATION.md): how to establish useful agreement.
5. [Delivery roadmap](docs/ROADMAP.md): milestones, dependencies, and exit gates.
6. [Decisions and questions](docs/DECISIONS.md): confirmed inputs and assumptions.

Supporting contracts: [timing and observation](docs/TIMING.md),
[metrics](docs/METRICS.md), [Windows setup](docs/SETUP_WINDOWS.md),
[validation status](docs/VALIDATION.md), and [references](docs/REFERENCES.md).

## Folder layout

```text
docs/                 Reviewable plan and engineering contracts
examples/wdt/         Small hybrid SystemC WDT and self-checking testbench
configs/              Runnable WDT scenario, adapter contract and sweep examples
tlm_lab/              CLI, runner, validation, metrics, and correlation
platform/             Platform entry-point documentation
adapters/             Integration contract for additional proprietary models
rtl/                  Independent Verilog WDT reference
tests/                Analytical, CLI, and RTL holdout tests
tools/                Local review utilities
.deps/                Ignored, workspace-local third-party dependencies
build/                Ignored build and pilot test traces
runs/                 Ignored immutable experiment artifacts and reports
private/              Ignored external/proprietary integrations
```

The pilot uses a blocking TLM register interface, an internal PEQ for transaction
readiness, and a clocked watchdog. It demonstrates that timing contracts and
observation points matter more than assigning an entire IP an LT or AT label.

Build and test instructions are in [Windows setup](docs/SETUP_WINDOWS.md).
The CLI validates JSON scenarios and launches `wdt_scenario` through its native
workload adapter. The legacy `wdt_pilot` retains eight fixed CTest scenarios.

