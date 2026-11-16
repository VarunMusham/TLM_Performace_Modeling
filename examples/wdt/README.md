# WDT pilot

Implemented: one blocking register target, PEQ readiness delay, clocked counter,
reset cancellation, IRQ/reset outputs, CSV trace, and eight directed cases.
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
and CTest needs `-C Release`. Results are model sanity checks until an independent
RTL implementation has been compared. This IP is not a production WDT design.

