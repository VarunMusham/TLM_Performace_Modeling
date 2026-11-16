# CLI platform

The version-1 CLI implements WDT experiments, analysis, correlation, sweeps,
replay, and regression. Run from the repository root with Python 3.9+ (standard
library only). Build the native driver with SystemC 2.3.4 and a matching C++14
compiler. Independent RTL comparison requires Icarus `iverilog` and `vvp` on PATH.

## Quick start

```powershell
python -m tlm_lab build --systemc-prefix .deps/systemc-2.3.4-install --compiler C:/msys64/ucrt64/bin/g++.exe
ctest --test-dir build-234 --output-on-failure
python -m tlm_lab validate configs/wdt_scenario.example.json
python -m tlm_lab run configs/wdt_scenario.example.json --rtl
python -m tlm_lab adapters
```

Open the printed run directory's `report.html`. It is a portable static report
with local evidence links. Native executable defaults to
`build-234/wdt_scenario.exe` on Windows; override with `--executable PATH`.
The older `wdt_pilot CASE TRACE` retains its eight fixed sanity cases.

## Scenario contract

The executable example uses schema version `"1"` and adapter `"hybrid_wdt"`.
Unknown fields, duplicate JSON keys, unsupported adapters, and ambiguous timing
are rejected. `adapters` prints the registered capability/timing contract.
Times are nonnegative integer ticks (1 ns), as decimal strings or JSON integers.
Addresses also accept `0x` strings. Data values are unsigned 32-bit integers.

The named clock has an even `period_tick` (at least 2) and positive
`first_rising_tick`. Even periods prevent half-cycle rounding at 1 ns resolution.
`parameters.bus_latency_tick` can be zero. `reset` lists strictly ordered
`{tick, reset_n}` transitions, starting asserted at 0, remaining asserted through
the first edge, then releasing. Rising-edge reset transitions are rejected.
Later sampled reset pulses cancel pending work at its original completion edge.

Each workload operation has a unique logical `id`, `op` (`read32`, `write32`, or
invalid-command test operation `ignore`), and `address`. Writes use `value`.
Choose an absolute `offer_tick` or `after_completion_of` naming the immediately
preceding operation, with optional `offset_tick`. Dependency feedback waits for
the actual response inside each simulator. The validator rejects overlapping
absolute offers; WDT accepts one blocking request at a time. Python does not
schedule individual kernel transactions.

Optional operation fields are `delay_tick`, `length` (0..4), `streaming_width`,
`byte_enable`, `expect_status`, and `expect_value`. Status defaults to 1 (OK);
TLM errors are -1 generic/reset cancellation, -2 address, -3 command, -4 width,
and -5 byte enable. `expectations` lists `{event,ticks,values?}` for complete
ordered reset/expiry/output histories. A failed behavior expectation invalidates
the experiment; it does not substitute for RTL correlation.

`measurement` defines `[start_tick,end_tick)`. Warm-up offers before start are
allowed; every offer must precede end. The driver drains through inclusive
`drain_deadline_tick`, including updates at that edge. Pending work at that
deadline is a simulated timeout. `--timeout SECONDS` independently bounds each
child process on the host and cleans up its process tree. Timeouts never produce
successful zero-throughput results.

`trace.mode` is `full` or `off`. `max_events` bounds full capture; exceeding it
fails instead of dropping evidence. Trace-off retains a response table and native
semantic event count/digest; event metrics are unavailable. Event expectations
and RTL comparison require full capture.

## Evidence and status

Every experiment creates a fresh UUID directory. Commands do not overwrite
existing evidence. The finalized directory contains resolved configuration,
adapter contract, workload, retained executable, logs, native metadata, raw CSV,
canonical string-tick JSONL, responses, metrics JSON/CSV, and `report.html`.
RTL runs also retain reference/testbench sources, compiled simulation, tool logs,
RTL traces/responses, canonical events, and the correlation report.

`started.json` is an interruption checkpoint. Final `manifest.json` records Git
revision/dirty status, source/executable/input hashes, available build-cache and
compiler settings, actual SystemC version, Python/host/PATH, child argument arrays,
working directories, deadlines, wall times, exit statuses, RTL tool versions and
hashes, trace mode/count, termination, validity, and qualification scope.
Source hashes describe files observed at run time; for externally built binaries,
they do not prove which source bytes produced the executable. Rebuild before
making source-level claims. Shared runtime DLLs remain host dependencies.

`artifacts_sha256` checks retained evidence before replay/analysis. Evidence is
hashed before rendering the report. The manifest and report are not cryptographic
signatures and do not authenticate themselves. Replay/profile result metadata
lives outside finalized child run directories.

Validity and accuracy are separate. Validity is `valid` or `invalid_run`;
correlation is `uncorrelated`, `pass`, `fail`, or `inconclusive`. A valid experiment
can fail accuracy. Missing tools/malformed RTL evidence/failed RTL processes are
inconclusive. `--allow-unqualified-systemc` explicitly permits compatibility runs
but cannot award target-version RTL qualification. Without it, non-2.3.4 is invalid.

Exit codes: 0 success; 1 failed/invalid/inconclusive requested experiment or gate;
2 CLI/configuration error. Requested RTL correlation must pass to exit 0.

## Analysis, import, replay, and regression

```powershell
python -m tlm_lab analyze runs/RUN --output runs/reanalysis.json
python -m tlm_lab import-rtl exported.csv --scenario configs/wdt_scenario.example.json --output runs/imported.jsonl
python -m tlm_lab compare runs/RUN/events.jsonl runs/imported.jsonl --output runs/comparison.json
python -m tlm_lab replay runs/RUN
python -m tlm_lab regress runs/BASELINE runs/CANDIDATE --absolute 0 --relative 0 --output runs/regression.json
```

The importer accepts pilot semantic CSV columns and numeric transaction IDs in
workload order, checks complete expected WDT lifecycles, and normalizes logical
IDs. An external monitor must implement the same edge/reset/readiness/post-update
convention. Retain its original CSV; built-in RTL runs do so automatically.
Proprietary waveform parsing is outside this adapter.

Comparison matches logical IDs/event occurrences and checks missing/duplicate
events, values, WDT architectural order, clock domain, and integer ticks. Delta
counts are simulator-local. No fitted shift is applied. `--tolerance-tick N`
selects explicitly bounded timing, never labeled exact. Reports retain the first
mismatch and up to 100 detailed differences.

Latency uses admissions within the window, followed through drain. Throughput
uses successful completions in the window, including earlier admissions. Payload
bytes are 4-byte register operations, not link wire bandwidth. Metrics include
conservation, failed/cancelled/censored work, nearest-rank quantiles, PEQ delay,
edge wait, time-weighted inflight occupancy, busy fraction, WDT timeout cycles,
and output assertion delay from expiry. Unsupported queue/wire/stall values are
unavailable. Intervals are clipped and seeded from pre-window state. Short samples
are labeled. Regression requires equivalent scenarios and applies
`max(absolute, relative*abs(baseline))` to latency KPIs. Tail gates are skipped
below 100 successful samples.

Replay verifies evidence hashes and reruns the retained native binary in a new
directory, checking the semantic digest and any requested RTL gate. Changed RTL
reference bytes cannot silently qualify as the same replay.

## Generated workloads, sweeps, and profiling

```powershell
python -m tlm_lab generate --seed 41 --count 100 --output runs/seed41.json
python -m tlm_lab run runs/seed41.json --rtl
python -m tlm_lab sweep configs/wdt_scenario.example.json --matrix configs/sweep.example.json --jobs 4 --rtl
python -m tlm_lab profile configs/wdt_scenario.example.json --rtl
```

Generation materializes seeded reads, LOAD, enable/disable, kick, W1C, annotations,
and offsets. Materialized inputs remain authoritative if generators change.
Matrices support bus latency, clock period/first edge, and seeds, with optional
`workload_generator.count` to produce traffic per seed. Without a generator,
seeds are metadata for the supplied directed workload. Directed expectations are
retained when parameters change without a generator; revise them explicitly.

Sweep prevalidation precedes simulation launch. Each experiment gets its own
process/directory, bounded by `--jobs` (1..32) and `--max-runs` (default 100).
Summary JSON lists every result. Parallel host runtime is unsuitable for speed
claims. Profile checks identical semantic digests and response tables for a
trace-on/off pair before reporting wall-time ratio. This single noisy measurement
includes process startup and digest work; it is not a trace budget or TLM/RTL
speedup claim.

## Extension boundary

`config.py` validates WDT capabilities and serializes native workloads;
`events.py` normalizes/checks observations; `metrics.py` provides offline functions;
`runner.py` isolates processes/evidence. The C++ observer copies scalar metadata
without waiting or scheduling IP activity. Add an adapter with its own contract,
validator, serializer/launcher, normalizer, and independent fixtures. Arbitrary
external-IP support cannot safely reuse WDT assumptions. Real UALink/UCIe/PCIe
models, concurrent credit/backpressure metrics, and multi-IP topologies require
those models and reviewed timing contracts.
