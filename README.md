# TLM Performance Lab

A proposed performance-analysis platform for existing, RTL-oriented SystemC IPs,
including hybrid models with PEQ-driven timing. Windows and SystemC **2.3.4** are
the target environment. The first pilot is a small watchdog timer (WDT).

**Status: architecture for review, with a small executable WDT pilot.** The general
platform, RTL importers, correlation engine, sweeps, and graphical interface are
planned; they are not implemented. The pilot is a new example IP, not a model of
your production WDT. No RTL equivalence or simulation-speedup claim has been made.

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
configs/              Illustrative future scenario and adapter contracts
platform/             Planned runner, metrics, and reporting responsibilities
adapters/             Integration template for existing proprietary models
rtl/                  Planned reference model and trace-export boundary
tools/                Local review utilities
.deps/                Ignored, workspace-local third-party dependencies
build/                Ignored build and pilot test traces
runs/                 Ignored future experiment artifacts
private/              Ignored external/proprietary integrations
```

The pilot uses a blocking TLM register interface, an internal PEQ for transaction
readiness, and a clocked watchdog. It demonstrates that timing contracts and
observation points matter more than assigning an entire IP an LT or AT label.

Build and test instructions are in [Windows setup](docs/SETUP_WINDOWS.md).
The JSON configuration files describe the intended platform API; the current
pilot uses fixed parameters and CTest cases, and does not load these files.

