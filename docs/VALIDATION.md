# Current CLI validation

Customer pilot validation, **2026-11-18 / CLI 1.1.0**: all **18 CTest entries**
pass using the native `build-pilot` installation, including **71 unittest methods**.
The 25 new external-adapter tests cover concurrent/out-of-order boundary metrics,
warm-up/drain/censoring, rejected/failed traffic, unknown payload sizes, malformed
contracts, source snapshots, missing build tools, timeouts, interruption, trace
loss, external sweeps, replay after original source changes, CLI diagnostics,
custom CSV mappings, and a real C++ source/testbench build.

The distribution test builds deterministic ZIPs, verifies every manifest hash,
checks excluded local directories, extracts into a separate folder with spaces,
and runs the demo there without package installation. Project paths with spaces
and Unicode are exercised. The Windows `.cmd` launcher validates the example.

Offline `setup-wdt` built the vendored SystemC 2.3.4 archive from scratch after
checking SHA-256. GCC runtime DLL imports are absent from the resulting native
WDT executable (Windows/UCRT system DLLs remain). Native/RTL tests pass under the
existing Windows GCC/Icarus toolchain. The generic report was visually inspected
in an isolated headless Chrome rendering. No clean-host MSVC or commercial-simulator
qualification is claimed. Customer-specific protocol accuracy remains the model
owner's integration/qualification work.

Pilot evidence is under ignored `runs/customer-pilot*/` and `runs/setup-*/`.
The shareable ZIP is produced by `python tools/package_pilot.py`; generated ZIPs,
builds, customer sources and run artifacts are not committed to the source repo.
The official SystemC source archive and its licence/notices are committed under
`vendor/systemc/` for offline installation.

Maintenance validation, **2026-11-18 / CLI 1.0.1**: the existing SystemC 2.3.4
native build and all 18 CTest entries pass with **46 unittest methods** (20
existing plus 26 failure/input/evidence tests). The added suite exercises atomic
publication and a competing writer, partial writes, malformed JSON/canonical
fields, incomplete hash coverage, retained preparation/launch/build failures,
child cleanup on interruption, failed profiles, replay response mismatches,
numeric-string seeds, late clocks, response timing and deterministic mismatch
ordering. These orchestration changes do not modify WDT or RTL timing code.

The documented 16-run RTL sweep and trace-on/off profile were rerun successfully.
Maintenance evidence is retained under ignored `runs/hardening-20261118/`.
Use `python -m unittest discover -s tests -p test_hardening.py -v` to exercise the
26 added tests without a SystemC or RTL installation. Full qualification still
requires the CTest/integration environment below.

Validated 2026-11-17 on Windows with MSYS2 UCRT64 GCC 16.1.0, C++14,
CMake 4.1.1/Ninja, Python 3.13.5, Icarus 12.0 (development build), and actual
**SystemC 2.3.4**, official tag commit
`5fc1469339775b54b1fcc2020ac744a58be5b50e`. Source was not patched; the GCC
assembly preprocessing flag is documented in [Windows setup](SETUP_WINDOWS.md).

## Verified baseline before implementation

The original repository had no commits and all 26 scaffold/pilot files were
untracked. Existing build artifacts used SystemC 2.3.3. Before changing source,
the build, all 16 CTests, and all eight trace checks were rerun successfully.
The original state was preserved in local commit `cecc95c`.

## Implemented checks

- SystemC 2.3.4 builds both native executables without the compatibility override.
- All **18 CTest entries pass**: the original 16 trace-on/off cases, the platform
  suite, and the eight-trace checker integrated as a dependent CTest.
- The platform suite has **20 passing unittest methods**, with parameterized
  fixtures for configuration validation, metric windows/cohorts/censoring,
  occupancy seeding, interval unions, nearest-rank quantiles, and conservation.
- Independent RTL comparison covers the example, LOAD=1/max, live LOAD changes,
  repeated enable, kick/disable/W1C at expiry, sticky masks, disabled kick,
  reset at expiry, sampled-reset cancellation surviving release, invalid access
  responses, zero latency, annotations, and varied clock periods/phases.
- Three 50-operation holdout seeds (3, 41, 999) pass exact RTL comparison.
- Byte-identical repeated native traces, verified binary replay, offline analysis,
  regression gating, importer/comparator CLI paths, and artifact tamper detection
  pass. Trace-on/off semantic event digests and response tables match.
- Host timeout cleanup, simulated deadline, bounded trace failure, missing RTL
  tools, and valid-run/failed-accuracy separation are tested.
- Synthetic timing, missing, duplicate, and reordered events fail comparison.
  The one-cycle negative control reports a 10 ns first divergence.
- A fresh CMake configuration still rejects SystemC 2.3.3 without the override.
- Local links in all 18 Markdown files resolve; `git diff --check` passes.
- The documented 16-run sweep (four bus latencies, two periods, two generated
  seeds, four workers) passes all exact RTL gates. Paired trace profiling passes
  semantic equivalence; the noisy single wall-time ratio is not a performance claim.

Reproduce with:

```powershell
python -m tlm_lab build --systemc-prefix .deps/systemc-2.3.4-install --compiler C:/msys64/ucrt64/bin/g++.exe
ctest --test-dir build-234 --output-on-failure
python -m tlm_lab run configs/wdt_scenario.example.json --rtl
python -m tlm_lab sweep configs/wdt_scenario.example.json --matrix configs/sweep.example.json --jobs 4 --rtl
python -m tlm_lab profile configs/wdt_scenario.example.json --rtl
```

Evidence is under ignored `runs/`, CTest traces under `build-234/traces`, and
test logs under `build-234/Testing/Temporary/LastTest.log`. Temporary unittest
run directories are cleaned after assertions. The final CLI guide describes
retention, hash verification, status meanings, and reproducibility limitations.

## Qualification limits

This validates the CLI and original WDT contract for exercised configurations.
It is not exhaustive/formal equivalence, production-IP qualification, a measured
speedup, or a statistically established trace budget. Production MSVC/commercial
simulators and real link-IP concurrency, queues, credits, retries, backpressure,
multi-clock crossings and multi-IP topology remain unqualified. Those require
actual model access and agreed per-KPI limits.

## Historical initialization record

The record below predates the CLI implementation and target-version validation.

# Initialization validation (historical)

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

