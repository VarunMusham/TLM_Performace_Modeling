# Initialization validation

Recorded 2026-11-17. This is validation of the scaffold and pilot, not a claim of
production readiness or RTL equivalence.

## Environment actually exercised

| Component | Observed value |
|---|---|
| OS | Windows, native PowerShell workflow |
| Compiler | MSYS2 UCRT64 GCC 16.1.0, C++14 |
| Build | CMake 4.1.1, Ninja, Release |
| SystemC | **2.3.3**, release version 2.3.3.20181013 |
| Python | 3.13.5, standard library only |
| Target environment | SystemC **2.3.4** on Windows; not yet exercised |

The session could not download the official 2.3.4 archive (network connection
failure). It built the already present 2.3.3 source into the workspace-local
`.deps/` directory. This does not substitute for the requested version. CMake
rejects non-2.3.4 libraries unless the explicit compatibility override is enabled.

## Completed checks

- Built the SystemC compatibility library and WDT executable successfully.
- All **16 CTest runs passed**: eight cases, each with and without CSV tracing.
- All **eight trace checks passed**, including exactly one lifecycle per
  transaction, PEQ timing, strict next-edge completion, expected expiry edges,
  output assertion edges, reset cancellation, and COUNT read semantics.
- Both draft JSON examples parse successfully.
- Local links in all 17 Markdown files resolve.
- A repeated expiry run produced a byte-identical CSV trace.
- The trace checker rejected a synthetic one-cycle expiry error (90 ns instead
  of 80 ns), with observation order preserved in the negative-control fixture.
- A fresh configuration without the override correctly rejected SystemC 2.3.3.

The eight cases are expiry, kick_boundary, disable_boundary, reset_pending,
invalid, annotated_delay, read_counter, and peq_on_edge. Trace-on/off runs pass
the same directed behavioral assertions; this is not an exhaustive equivalence
proof for arbitrary workloads. C++ tests use explicit failure checks, not
assertions that disappear under `NDEBUG`.

Generated traces are in `build/traces/`. CTest details are in
`build/Testing/Temporary/LastTest.log`. Artifacts and downloaded/built dependencies
are ignored by source control rules. The planned full run manifest is not yet
implemented; executable output identifies the actual SystemC version.

## Remaining validation

- Repeat build and tests with the actual SystemC 2.3.4 production toolchain.
- Complete additional WDT boundary cases listed in the specification.
- Implement the independent RTL reference and compare normalized event traces.
- Test a real link IP under contention, finite queues, credits, and backpressure.
- Establish workload-specific KPI tolerances and a measured runtime/trace budget.

No throughput speedup, RTL correlation percentage, or accuracy qualification is
reported. The broader runner, metric engine, schema validation, and report UI
remain planned components.

