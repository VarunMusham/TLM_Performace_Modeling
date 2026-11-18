# Customer pilot guide

This guide takes you from an extracted folder to a report for your own source and
testbench. Everything runs locally. No package installation, account or upload is
required. Python 3.9+ is the only dependency for the core and portable demo.

## 1. Run your first experiment

Open PowerShell in the extracted lab folder:

```powershell
python tlm-lab.py doctor
python tlm-lab.py demo --open
```

If `python` is not on PATH, try `py -3 tlm-lab.py demo --open` or
`.\tlm-lab.cmd demo --open`. If neither is available, install Python using your
organisation's approved installer. No pip dependencies are needed.

`doctor` distinguishes required tools from optional tools. Missing SystemC,
CMake, Icarus or a compiler does not prevent the portable demo from working.
`--open` opens a local HTML file; omit it on headless hosts. Open the printed
`report` path if your browser does not launch automatically.

| Demo check | Expected |
|---|---|
| Completed requests | 4 |
| Mean admission-to-completion latency | 20 ticks |
| Peak simultaneous requests | 2 |
| Completed payload bytes | 288 |
| Tick duration | 1 ns (1,000,000 fs) |

The slow first request finishes after a later request. This verifies overlap and
completion reordering. It is a synthetic example, not a production-IP prediction.

## 2. Create a source/testbench project

```powershell
python tlm-lab.py init my-ip --template cpp
python tlm-lab.py doctor --adapter my-ip/adapter.json
python tlm-lab.py run my-ip/scenario.json --adapter my-ip/adapter.json --open
```

The C++ example uses CMake, Ninja and a C++14 compiler. Run from your compiler's
developer shell. Replace its build commands with your existing Make, CMake,
vendor simulator or other build invocation. Absolute tool paths are supported.
Windows MSYS2 UCRT64 GCC is the exercised compiler profile; other toolchains need
their own validation.

Use `python tlm-lab.py init my-ip-python --template python` for a starter without
a compiler requirement. `init`
refuses to overwrite an existing folder. Projects may live outside the checkout;
invoke the absolute path to `tlm-lab.py` from any working directory.

## 3. Connect your IP

Keep the first working example as a reference, then:

1. Replace the example model and testbench with your files.
2. Set the adapter ID, model kind, tick resolution, source list and parameter rules.
3. Replace build/run argument arrays with your existing tool commands.
4. Add observations at actual offer, admission and terminal response points. Use
   the supplied SDK, or map your existing CSV column/event names.
5. Emit a completion marker only after successful capture flush and measurement/drain.
6. Set a meaningful workload, window and expected counts. Run `validate`,
   `doctor --adapter`, then `run --adapter`.

The platform copies listed sources and the SDK before building. Build into
`{build_dir}` and write results into `{run_dir}`. Original files are preserved.
List include/data directories in `sources` to preserve their layout. Installed
libraries, simulator licences and environment setup remain your model's
dependencies; describe them in `requirements`.

For long builds or simulations, pass `--build-timeout 600 --timeout 300` to run.
The defaults are 300 seconds per build command and 30 seconds for simulation.
Progress appears on stderr; the final run/report paths remain JSON on stdout.

For SystemC, convert `sc_time_stamp()` into your declared integer tick unit. For
RTL, observe at the defined testbench sampling boundary. Do not add waits, delays
or backpressure in an observer. Annotated time, admission and completion may
differ; instrument the boundary your KPI intends to measure. The WDT's strict
next-clock-edge rule is specific to WDT.

The [adapter reference](EXTERNAL_ADAPTERS.md) defines the full executable contract.
An adapter is necessary: the tool cannot infer arbitrary ports, protocols or model
accuracy merely from having the source and testbench files.

## 4. Interpret the report

Latency follows requests **admitted inside `[start_tick,end_tick)`** until capture
stops. Throughput counts **successful completions inside the window**, including
earlier admissions. Failed/cancelled and unfinished requests are shown separately.
Unfinished work does not become a successful zero-latency sample. Missing payload
sizes make byte throughput unavailable. Missing offer events make offered-traffic
coverage unavailable. Small-sample percentiles do not establish tail confidence.

`valid` means execution and evidence checks passed. It does not establish model
accuracy. Generic comparison checks identity, boundary timing and payload size;
it does not verify payload contents, dependent protocol ordering or internal
state. Qualify those aspects with an independent reference and model-owner tests.

## 5. Sweep, compare and replay

For the Python starter, save this as `my-ip-python/matrix.json`:

```json
{"parameters":{"parameters.lanes":[1,2,4]},"seeds":[1,2]}
```

```powershell
python tlm-lab.py sweep my-ip-python/scenario.json --adapter my-ip-python/adapter.json --matrix my-ip-python/matrix.json --jobs 2
python tlm-lab.py replay runs/RUN
python tlm-lab.py analyze runs/RUN --output runs/reanalysis.json
python tlm-lab.py compare runs/LEFT/events.jsonl runs/RIGHT/events.jsonl --output runs/comparison.json
python tlm-lab.py regress runs/BASELINE runs/CANDIDATE --absolute 0 --relative 0 --output runs/regression.json
```

Use actual run paths printed by the commands. Each sweep point gets an isolated
build/run. Seeds are passed to your testbench; they change traffic only if it uses
them. The portable fixture is deterministic and does not vary traffic by seed.
Regression requires equivalent scenarios and tests absolute latency differences,
including improvements, within the stated tolerance.

External replay rebuilds the **retained source and SDK** with installed host
tools, then compares boundaries. It does not package a hermetic compiler/runtime
environment. WDT replay retains its binary-based behaviour. Parallel sweep
interruption/resume and generic trace-off profiling remain future work.

## 6. Optional native WDT setup

The repo includes an unmodified, hash-pinned SystemC 2.3.4 source archive and its
upstream licence/notices. With CMake, Ninja and a compatible compiler:

```powershell
python tlm-lab.py doctor --wdt
python tlm-lab.py setup-wdt
python tlm-lab.py run configs/wdt_scenario.example.json --open
ctest --test-dir build-pilot -C Release --output-on-failure
```

Setup builds inside `.deps/` and `build-pilot/`, without network downloads or
administrator installation. `--compiler PATH` and `--generator NAME` select the
toolchain. Use a fresh distribution folder when switching compiler families or
generators. Icarus `iverilog`/`vvp` are optional for the WDT RTL gate (`--rtl`) and
required for the full WDT integration suite.

## Troubleshooting

| Symptom | Next step |
|---|---|
| Python not found | Try `py -3` or the `.cmd` launcher; reopen the terminal after installation |
| Required tool missing | Run doctor with the adapter; use the toolchain shell or an absolute tool path |
| Build failure | Open build-N.stderr.log and build-N.stdout.log; check includes/compiler options |
| DLL/runtime launch error | Put your simulator's runtime on PATH; WDT MinGW builds link their runtime statically |
| No transactions.csv | Check run arguments, output path and CSV mapping |
| No completion.json | Fix the testbench error; write the marker after successful flush/drain |
| Capture ends too early | Increase simulation stop/drain time to cover the measurement window |
| Sequence/count/loss error | Repair the observer/exporter; do not remove evidence checks |
| Source changed during build | Generate files under build_dir, rather than rewriting source inputs |
| Artifact changed | Use a new run; analysis/replay rejects modified evidence |
| Output already exists | Choose a new name; results are not overwritten |
| Hard links unsupported | Use a local NTFS folder; some network/FAT filesystems cannot publish atomic artifacts |

For pilot issues, share the command, lab version, adapter ID, `doctor --json`,
error text and selected logs. Run folders contain source snapshots and may contain
proprietary IP; inspect them before sharing. The distribution packager excludes
run folders, local builds, Git metadata and `private/`.
