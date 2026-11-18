# TLM Performance Lab

Run your IP's source and testbench, measure transaction latency and throughput,
and share an offline report. Start with a working example, then connect your own
build and simulator commands through a small adapter manifest.

**Customer pilot · version 1.1.0 · Windows first.** The core and portable demo
need only **Python 3.9+**. No pip packages, service, account or network connection
are required. A pinned SystemC 2.3.4 source archive is included for the native
watchdog example. Your IP still needs its own compiler/simulator and any licences.

## Try it in one command

Download/extract the repository or pilot ZIP, open a terminal in that folder:

```powershell
python tlm-lab.py demo --open
```

The Windows launcher also finds Python for you:

```powershell
.\tlm-lab.cmd demo --open
```

The demo produces a local `report.html`, metrics CSV/JSON, traces and source
snapshots under `runs/`. It demonstrates two concurrent service lanes and
out-of-order completion. Expected results: **4 completions, mean latency 20 ticks,
peak 2 in flight, 288 completed payload bytes**. This is a synthetic learning
example, not a prediction for a real protocol or IP.

## Bring your source and testbench

```powershell
python tlm-lab.py init my-ip --template cpp
python tlm-lab.py doctor --adapter my-ip/adapter.json
python tlm-lab.py run my-ip/scenario.json --adapter my-ip/adapter.json --open
```

The C++ starter needs CMake, Ninja and a C++14 compiler. Use `--template python`
for a starter with no compiler requirement. Then replace the example source and
testbench, list your source files, and edit `adapter.json` to use your existing
build/run commands. Copyable Python and C++ trace observers are in `sdk/`.

**IP-independent integration does require an adapter.** SystemC, RTL simulators,
plain C++ models and other executables can use the same external build/run and
trace contract. The tool does not infer arbitrary ports, workloads, protocol
semantics or model accuracy from source files. Your testbench owns those details;
the platform measures the boundaries you expose. The built-in WDT retains its
separate, tested SystemC/RTL timing contract.

Start with the **[customer guide](docs/CUSTOMER_GUIDE.md)**. For integration,
see the **[external adapter reference](docs/EXTERNAL_ADAPTERS.md)**.

## Native SystemC watchdog example

With CMake, Ninja and a compatible C++ compiler on PATH:

```powershell
python tlm-lab.py doctor --wdt
python tlm-lab.py setup-wdt
python tlm-lab.py run configs/wdt_scenario.example.json --open
```

Setup verifies and builds the bundled SystemC source into this workspace;
no download or administrator installation is performed. For independent WDT RTL
comparison, install Icarus `iverilog`/`vvp` and add `--rtl` to the run command.
See [Windows setup](docs/SETUP_WINDOWS.md) for other compiler profiles.

## Explore and reproduce

```powershell
python tlm-lab.py --help
python tlm-lab.py validate my-ip/scenario.json --adapter my-ip/adapter.json
python tlm-lab.py replay runs/RUN
python tlm-lab.py analyze runs/RUN --output runs/reanalysis.json
python tlm-lab.py compare runs/LEFT/events.jsonl runs/RIGHT/events.jsonl --output runs/comparison.json
```

External adapters support parameter sweeps, offline analysis, retained-source
replay and latency regression. Reports distinguish successful execution from
accuracy qualification. Unknown payload sizes produce unavailable byte throughput;
unfinished work is counted explicitly. Internal queue/credit/stall metrics need
additional IP-specific observations.

## Share with the pilot group

```powershell
python tools/package_pilot.py
```

Share `dist/tlm-performance-lab-1.1.0.zip`. It includes the launcher, guides,
templates, SDK, tests, SystemC source and its licence/notices. It excludes your
`private/`, `runs/`, `.deps/`, build directories and Git metadata. The ZIP contains
a file-hash manifest. Customers extract it and run the demo; no package installation
is needed. Source snapshots inside individual experiment runs may contain customer
IP, so select experiment evidence deliberately when sharing it.

## Development and validation

```powershell
python -m unittest discover -s tests -v
ctest --test-dir build-pilot -C Release --output-on-failure
```

The Python-only tests run without native tools; unavailable native integration
tests are explicitly skipped. See [validation evidence](docs/VALIDATION.md),
[CLI reference](docs/CLI.md), and the [developer handoff](docs/README.md).
The [roadmap](docs/ROADMAP.md) covers future protocol-specific qualification,
resource instrumentation and multi-IP composition; these are not automatic
capabilities of the generic adapter.
