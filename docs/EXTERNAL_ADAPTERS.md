# Source/testbench adapter reference

Implemented in CLI 1.1.0. The `external-1` contract is independent of WDT v1 and
the larger proposed v2 architecture. It provides common execution and boundary
evidence for executable testbenches; it does not infer source ports or add missing
timing mechanisms. Use the [Python](../examples/portable_queue/adapter.json) or
[C++](../examples/external_cpp/adapter.json) template as a starting point.

## Manifest

Pass it explicitly: `run scenario.json --adapter project/adapter.json`.
`validate` and `doctor` do not import or execute customer code. `run` executes
declared commands with the invoking user's normal permissions; use trusted
project manifests. This runner is not a code sandbox.

| Field | Meaning |
|---|---|
| schema_version | Exactly `external-1` |
| adapter_id, version, description | Stable adapter/model identity and description |
| model_kind | synthetic, simulation, rtl or hardware; descriptive, not qualification |
| time_resolution_fs | Positive integer femtoseconds per observed tick |
| sources | Relative files/directories to snapshot, retaining their layout |
| parameters | Scalar type, optional default/minimum/maximum/enum/description |
| build | Optional list of argument arrays, executed sequentially |
| run | Required argument array for the testbench/simulator |
| trace | Optional file, CSV column mapping and event-name mapping |
| completion_file | Default completion.json |
| requirements | Human-readable dependencies/environment notes |
| tools | Labels mapped to executable alternatives for doctor |

Parameter types: `integer` (unsigned), `number` (finite), `boolean`, `string`.
Unknown parameters are rejected; omitted values need defaults. These are scalar
rules, not full JSON Schema. Workload and cross-parameter validation belong to
the testbench. Sources must stay inside the manifest's folder; symlinks and parent
traversal are rejected. Limit: 10,000 source files. Keep generated outputs outside
the source selection. Changing a retained source during build invalidates a run.
Installed libraries/tools may be referenced explicitly but are not copied.

## Command arguments

Commands are arrays, never shell strings. Each element remains one argument,
including paths with spaces. No implicit shell interpretation occurs. Invoke the
intended interpreter explicitly if your build requires a shell script.

| Placeholder | Value |
|---|---|
| `{python}` | Current Python executable |
| `{source_dir}` | Retained source snapshot |
| `{sdk_dir}` | Retained SDK, with python/ and cpp/ subdirectories |
| `{build_dir}` | Run-specific build directory |
| `{run_dir}` | Run directory for results/logs |
| `{scenario}` | Materialized scenario JSON path |
| `{exe_suffix}` | .exe on Windows; empty elsewhere |
| `{param_NAME}` | Validated scalar parameter value |
| `{start_tick}`, `{end_tick}`, `{drain_deadline_tick}` | Window and drain settings |
| `{seed}` | Materialized unsigned 32-bit seed |

Use doubled braces for literal braces. Conversions, attribute access and unknown
placeholders are rejected. Do not put credentials in arguments: commands are
retained as evidence. Command working directory is the run directory.

## Scenario

```json
{
  "schema_version":"external-1", "name":"my_experiment", "adapter":"my_adapter",
  "parameters":{}, "workload":[], "seed":1,
  "measurement":{"start_tick":"0","end_tick":"100","drain_deadline_tick":"150"},
  "expectations":{"completed":4,"outstanding":0}
}
```

Times are nonnegative integer ticks; require `start < end <= drain`. Workload is
an array interpreted by your testbench. Ports, payloads, dependencies, feedback,
generation and protocol semantics belong there; Python orchestration does not
schedule individual kernel transactions. Optional expectations check all-trace
counts: offered, admitted, completed, failed_cancelled, rejected, outstanding.
Use expected counts to detect missing intended stimulus: complete capture alone
cannot prove that the intended workload ran.

## Transaction CSV

Default file: `transactions.csv`, UTF-8:

```csv
sequence,tick,event,transaction_id,payload_bytes
1,0,offer,request_1,64
2,2,accept,request_1,64
3,12,complete,request_1,64
```

Sequence starts at 1 and is contiguous. Ticks never decrease. IDs identify logical
operations, not payload pointers; do not reuse an ID during capture. Admissions
may overlap and independent completions may reorder. Capture must include
pre-window state, normally by starting at the beginning of simulation.

| Event | Semantics |
|---|---|
| offer | Optional offer; at most once, before admission |
| accept | Admission into the measured boundary; at most once |
| complete | Successful terminal outcome after accept |
| fail / cancel | Failed/cancelled terminal outcome after accept |
| reject | Terminal refusal after offer, without accept |

At most one terminal outcome is allowed; no later rows may use that ID. Admission
without offer is supported, but offered-traffic coverage becomes unavailable.
Unfinished admissions are censored and counted; offers without admission/rejection
are reported separately.

`payload_bytes` is useful payload at that event. Blank means unknown; zero means
known zero. Byte throughput is unavailable if any successful in-window completion
has an unknown size. It is not wire bandwidth. Split/merge/retry lineage, dependent
protocol ordering, payload contents, internal resources and clocks/epochs require
a richer contract; do not relabel unrelated operations as end-to-end measurements.

Existing CSVs can use `trace.columns`: map all five canonical keys to raw header
names. Extra raw columns are retained but not interpreted. `trace.event_map` maps
raw labels to the six supported kinds. Export other event types separately.

## Successful capture marker

Write completion.json after successful simulation and trace flush:

```json
{"schema_version":"capture-1","finished":true,"event_count":3,"loss_count":0,"stop_tick":"150"}
```

Count must match CSV rows, loss must be zero, `end <= stop <= drain`, and no event
may exceed stop. Missing markers, process failures, timeouts, truncated rows,
sequence gaps and violated expectations invalidate results.

Copyable observers: [Python](../sdk/python/tlm_trace.py) and
[C++14](../sdk/cpp/tlm_trace.hpp). They record observations without controlling
simulation time. The C++ helper accepts CSV-safe IDs and known byte sizes; use
your own CSV writer for other conventions. Capture failure should terminate the
experiment, rather than silently dropping evidence.

## Metrics, replay and comparison

Events use `transaction-1`; metrics use `transaction-metrics-1`. Latency follows
the admission cohort to capture stop. Throughput uses successful completions in
`[start,end)`. Inflight occupancy is time weighted and seeded from pre-window
events. Completion bytes come from terminal events. Quantiles use nearest rank;
small samples are labelled.

Sources, SDK, commands, tool hashes where available, logs, raw/canonical capture
and results are retained. Replay rebuilds retained sources/SDK using host tools.
Shared libraries, licences and other external dependencies remain prerequisites;
this is not hermetic build attestation.

Comparison matches `(transaction_id,event)`, checking ticks and payload sizes
while allowing independent same-tick ordering. It requires equal resolution and
reports boundary agreement only. It cannot award WDT's `--rtl` qualification or
prove payload/protocol equivalence. Trace-off profiling remains WDT-specific.
External parameter sweeps and latency regression are available; workload
generation remains inside the customer testbench.
