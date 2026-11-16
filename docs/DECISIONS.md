# Decisions and open questions

Implementation update: the local qualified path uses SystemC 2.3.4 (official tag,
commit `5fc1469339775b54b1fcc2020ac744a58be5b50e`), MSYS2 UCRT64 GCC 16.1.0,
C++14, Ninja, Python 3.13.5 and Icarus 12.0. The runtime contract is version 1;
see [CLI](CLI.md). Production toolchain and real-IP questions below remain open.
The built-in WDT accuracy gate requires exact event ticks.

## Confirmed by the user

| Item | Decision |
|---|---|
| Primary user | TLM IP developer supporting RTL performance investigations |
| Environment | Windows; OSCI/Accellera SystemC 2.3.4 |
| Model style | Existing hybrid timing, including PEQs; preserve it |
| First IP | Design a simple hybrid WDT for platform testing |
| RTL evidence | Format flexible; user can work with any suitable evidence |
| Dependencies | Download/install allowed; prefer isolated workspace dependencies |

## Proposed defaults, open to review

| Choice | Rationale / consequence |
|---|---|
| C++14 pilot, CMake, Python orchestration | Small portable native example; toolchain must match SystemC |
| CLI and static HTML first | Establish trustworthy data before investing in a dashboard |
| JSON scenario files | Inspectable, versionable, and usable without an initial YAML dependency |
| One process per run | Clear kernel lifecycle, isolation, deterministic configuration |
| Explicit hooks before generic socket interception | Preserve custom timing and expose internal bottlenecks |
| Exact WDT event timing as first correlation target | Small enough to reason about and independently implement |
| Fixed-period WDT clock, one blocking request at a time | Minimal pilot; concurrency is a separate link-IP milestone |

## Questions remaining for implementation review

1. Which production Windows compiler/runtime and build system must adapters use
   (MSVC, MinGW, or a simulator-provided environment)? What is the 2.3.4 path?
2. Is the WDT register map and same-edge priority suitable, or should it mirror
   an existing internal WDT more closely?
3. Which real link IP comes after WDT, and which protocol version/configuration?
4. Can adapters add internal observation hooks, or only wrap exposed interfaces?
5. Which KPI thresholds and configuration envelope will RTL engineers accept?
6. What are typical transaction counts, simulation durations, and trace budgets?
7. Which RTL simulator/monitor export should the first importer support?
8. Are register setup sequences and workload generators already available?

These questions do not block WDT CLI use. Its independent RTL baseline is
implemented; real-IP qualification still requires actual models and agreed limits.

