# WDT pilot

Implemented: one blocking register target, PEQ readiness delay, clocked counter,
reset cancellation, IRQ/reset outputs, CSV trace, and eight directed cases.
The configurable `wdt_scenario` consumes CLI-generated clocks, reset sequences,
dependency workloads, annotations, drain deadlines and trace budgets. See
[CLI](../../docs/CLI.md). Python/RTL tests add boundary cases and random holdouts.
See [the specification](../../docs/WDT_SPEC.md) before changing timing behavior.

```powershell
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
python tools/check_pilot_traces.py build/traces
```

Configure dependencies first using [Windows setup](../../docs/SETUP_WINDOWS.md).
Run one case manually after building:

```powershell
./build/wdt_pilot.exe kick_boundary build/traces/manual.csv
./build/wdt_pilot.exe kick_boundary -
```

With a multi-configuration generator, the executable is under `build/Release/`
and CTest needs `-C Release`. Fixed pilot tests are sanity checks; request `--rtl`
through the CLI for independent comparison. This is not a production WDT design.

