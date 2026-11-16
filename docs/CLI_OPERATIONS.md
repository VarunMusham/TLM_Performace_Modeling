# CLI, deployment and operations design

Status: proposed R1/R2, REQ-08/09/10/11, NFR-01/04/05/07. Current working
commands remain documented in [CLI](CLI.md); commands below marked future must
not be advertised as runnable until implemented. User requires Windows and CLI
first; future Linux/UI are architectural constraints, not current deliverables.

## Command and application-service map

| Workflow | Current surface | Future extension |
|---|---|---|
| Inspect capabilities | `adapters` prints WDT contract | `adapters list/show/check`, profile capabilities/prerequisites |
| Resolve/validate | `validate` checks WDT JSON | `validate --json`, `resolve`, `run --dry-run`; diagnostics with field pointers |
| Build and run | `build`, `run` | Build lock/profile, prepared external launch, job resource budgets |
| Observe/analyze | `analyze`, static report in run | Metric selection by prerequisites, analysis IDs, streaming indexed queries |
| Import/compare | `import-rtl`, `compare` | Profile importers, equivalence/policy files, causal mismatch context |
| Qualify | Per-run `--rtl` | `qualify` matrix and envelope record with all required gates |
| Explore | `generate`, `sweep`, `regress`, `profile` | Constrained axes, repeated seeds, resume/retry, sensitivity/Pareto |
| Reproduce/share | `replay` | `export`, `verify`, environment preflight and explicit artifact allowlist |

CLI parses arguments and invokes typed application services. Adapters supply
schemas/capabilities, not arbitrary command-line parser patches. `--json` outputs
one documented result object to stdout; human progress goes to stderr. A batch
has a summary and per-attempt records. Every command prints the output location.
Exit 0 means requested gates passed; 1 means completed but failed required
experiment/accuracy gate; 2 means input/contract error. Add a documented distinct
interruption code while preserving v1 compatibility. Never use exit 0 for a
required-but-unavailable accuracy gate. Diagnose errors with code, stage, location,
cause and action; avoid raw tracebacks for expected user/configuration errors.

## Run and job lifecycle

States: created -> resolving -> preparing -> building -> ready -> running ->
draining -> ingesting -> analyzing -> comparing -> finalizing -> complete.
Any state can end failed/cancelled/interrupted with the evidence available so far.
Preparation/build may be skipped only with verified reusable artifacts.
Host, simulated-time and drain timeouts are distinct. Configured host limits
include child descendants and simulator license-wait time if relevant; record
license failures without storing credentials. Windows uses a process-tree/job
provider with tested descendant cleanup; Linux later uses its native equivalent.

Cancellation is idempotent. Polling status cannot mutate runs. Sweep resume
consults attempt manifests and hashes, reuses only complete valid eligible results,
and starts fresh attempts for failed/incomplete inputs. Concurrent workers reserve
CPU/RAM/disk and simulator license slots before launch. Defaults must be bounded;
users may override with explicit budgets. Independent workers never share mutable
simulation outputs. A deterministic kernel still produces nondeterministic host
timings; keep those comparisons controlled and separate.

## Artifact tree (proposed)

```text
runs/<experiment-id>/<attempt-id>/
  resolved/       scenario, topology, workload, profile and policy
  build/          manifest, commands, dependencies and permitted binaries
  execution/      journal, process metadata, stdout/stderr and native summary
  raw/            immutable model and RTL exports, chunk footer/index
  canonical/      versioned normalized streams and conversion manifests
  analysis/<id>/  metrics, comparison, report and their input hashes
  run.started.json
  run.manifest.json
```

Exact filenames become schemas in B02/B07. Finalization occurs after close/hash
of required evidence. Reanalysis appends a new analysis directory and catalog
entry; it does not rewrite the completed run manifest. Partial runs remain
inspectable. Disk quota checks precede launch; runtime I/O errors terminate or
degrade according to capture policy and forbid completeness claims.

## Reproducibility and privacy

Build provenance records source bytes at build time, generated files, compiler/
link flags, SystemC/SDK and library versions, artifact hashes and relevant
environment. Run provenance references that immutable build. Pin normalizers,
metric definitions and policies as well as binaries. Capture environment using
an allowlist; redact secrets and user-specific private paths from exported bundles.
Store dependency prerequisites when redistribution is not allowed. A replay
preflight explains missing/incompatible runtimes instead of silently rebuilding
with a different toolchain and calling it identical.

Payload contents are excluded by default; scalar IDs, size/class and sanitized
addresses suffice for many KPIs. Import/export does not follow paths outside the
declared bundle root, accept shell snippets from scenarios, or deserialize arbitrary
executable objects. Treat adapter implementations as trusted local code and input
data as data. No external upload or telemetry is required for local operation.
Record source repository references without exposing credentials in URLs/logs.

## Windows release and future Linux port

Qualify the actual production compiler/runtime from intake. Existing MinGW/GCC
2.3.4 evidence is not MSVC or commercial-simulator qualification. Package Python
dependencies and native SDK with reproducible lock/build instructions. Test spaces,
Unicode, long paths, CRLF/LF, atomic renames and file locks. Use argument arrays,
explicit cwd and environment; avoid shell-specific launch logic in core services.

The Linux port adds providers, build packaging and CI matrix entries, then repeats
semantic determinism, cancellation and adapter qualification. A compile success
alone is not portability evidence. Cross-OS equivalence is semantic events/results,
not identical binaries or wall-clock timings. UI later consumes the same services,
resolution rules and artifacts; it may not introduce a second schema authority.

## Optional power and architecture work

After performance qualification, a power extension can integrate state residency
and activity with calibrated coefficients: `energy = sum(P_state * dwell) +
sum(E_event * count)` under a documented nonoverlap model. Coefficients need units,
voltage/frequency/temperature domain, source, validity range and uncertainty.
No calibration -> unavailable energy, not guessed watts. UPF import is a separate
feature requiring supported semantics/tests, not a consequence of collecting
activity. Thermal/electrical modeling needs additional tools and model evidence.

Architecture exploration adds workload mappings, resource models and constraints
that are independently calibrated/qualified. Each candidate retains model fidelity,
legal parameters and unsupported effects; Pareto ranking excludes invalid or
unqualified alternatives when the user's decision requires qualified predictions.
