"""Source/testbench adapters: isolated build/run commands and portable evidence."""
import copy
import csv
from datetime import datetime, timezone
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import string
import subprocess
import sys
import uuid
from . import __version__
from .config import fields, integer, require
from .events import write_jsonl
from .runner import ROOT, digest, process, git
from .storage import dump, load_json
from . import transactions

VERSION = "external-1"
TOKENS = {"python", "source_dir", "build_dir", "run_dir", "scenario", "exe_suffix", "sdk_dir",
          "start_tick", "end_tick", "drain_deadline_tick", "seed"}


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def relative_path(name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name, "Use relative paths with forward slashes")
    path = PurePosixPath(name)
    require(not path.is_absolute() and ".." not in path.parts and str(path) == name and name != ".", f"Unsafe artifact/source path: {name}")
    return Path(*path.parts)


def parameter(value, spec, name):
    kind = spec["type"]
    if kind == "integer":
        value = integer(value, name, spec.get("minimum", 0), spec.get("maximum", 2**63-2))
    elif kind == "number":
        require(finite_number(value), f"{name}: expected a finite number")
        require(spec.get("minimum", -math.inf) <= value <= spec.get("maximum", math.inf), f"{name}: outside parameter bounds")
    elif kind == "boolean":
        require(type(value) is bool, f"{name}: expected a boolean")
    else:
        require(isinstance(value, str), f"{name}: expected a string")
    if "enum" in spec:
        require(value in spec["enum"], f"{name}: choose one of {spec['enum']}")
    return value


def load_adapter(path):
    path = Path(path).resolve(strict=True)
    a = load_json(path)
    required = {"schema_version", "adapter_id", "version", "description", "model_kind", "time_resolution_fs",
                "sources", "parameters", "run"}
    fields(a, required | {"build", "trace", "completion_file", "requirements", "tools"}, required)
    require(a["schema_version"] == VERSION, "Adapter schema_version must be external-1")
    require(isinstance(a["adapter_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", a["adapter_id"]), "Invalid adapter ID")
    require(a["model_kind"] in ("synthetic", "simulation", "rtl", "hardware"), "Unknown model_kind")
    require(all(isinstance(a[key], str) and a[key] for key in ("version", "description")), "Adapter version/description are required")
    integer(a["time_resolution_fs"], "time_resolution_fs", 1)
    require(isinstance(a["sources"], list) and a["sources"], "List the source/testbench files or directories to retain")
    for name in a["sources"]:
        relative_path(name)
    require(isinstance(a["parameters"], dict), "parameters must be an object")
    for name, spec in a["parameters"].items():
        require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name), "Invalid parameter name")
        fields(spec, {"type", "default", "minimum", "maximum", "enum", "description"}, {"type"})
        require(spec["type"] in ("integer", "number", "boolean", "string"), f"Unsupported parameter type: {name}")
        if "enum" in spec:
            require(isinstance(spec["enum"], list) and spec["enum"], f"{name}: enum must be nonempty")
        for bound in ("minimum", "maximum"):
            if bound in spec:
                require(spec["type"] in ("integer", "number") and finite_number(spec[bound]), f"{name}: invalid {bound}")
                if spec["type"] == "integer":
                    integer(spec[bound], f"{name}.{bound}")
        require(spec.get("minimum", -math.inf) <= spec.get("maximum", math.inf), f"{name}: inverted bounds")
        if "default" in spec:
            parameter(spec["default"], spec, name)
    require(isinstance(a.get("build", []), list), "build must be an array of argument arrays")
    for command in [*a.get("build", []), a["run"]]:
        require(isinstance(command, list) and command and all(isinstance(arg, str) and arg for arg in command),
                "Commands must be nonempty argument arrays, never shell strings")
        for argument in command:
            for _, token, fmt, conversion in string.Formatter().parse(argument):
                require(token is None or token in TOKENS | {"param_"+name for name in a["parameters"]} and not fmt and not conversion,
                        f"Unsupported command placeholder: {token}")
    trace = a.get("trace", {})
    fields(trace, {"file", "columns", "event_map"})
    relative_path(trace.get("file", "transactions.csv"))
    relative_path(a.get("completion_file", "completion.json"))
    outputs = [trace.get("file", "transactions.csv"), a.get("completion_file", "completion.json")]
    reserved = {"source", "sdk", "build", "adapter.json", "scenario.json", "started.json", "manifest.json",
                "events.jsonl", "metrics.json", "metrics.csv", "report.html"}
    require(len(set(outputs)) == 2 and all(relative_path(name).parts[0] not in reserved for name in outputs),
            "Trace/completion paths collide with reserved run artifacts")
    if "columns" in trace:
        fields(trace["columns"], transactions.COLUMNS, transactions.COLUMNS)
        require(all(isinstance(value, str) and value for value in trace["columns"].values()), "Invalid trace column mapping")
        require(len(set(trace["columns"].values())) == len(transactions.COLUMNS), "Trace columns must be distinct")
    require(isinstance(trace.get("event_map", {}), dict), "event_map must be an object")
    require(all(isinstance(value, str) and value in transactions.KINDS for value in trace.get("event_map", {}).values()),
            "event_map values must name supported transaction events")
    require(isinstance(a.get("requirements", []), list) and all(isinstance(v, str) for v in a.get("requirements", [])),
            "requirements must be descriptive strings")
    require(isinstance(a.get("tools", {}), dict), "tools must map labels to executable alternatives")
    for label, alternatives in a.get("tools", {}).items():
        require(isinstance(alternatives, list) and alternatives and all(isinstance(tool, str) and tool for tool in alternatives),
                f"tools.{label}: expected executable names or paths")
    return a


def resolve_scenario(c, adapter):
    c = copy.deepcopy(c)
    fields(c, {"schema_version", "name", "adapter", "parameters", "workload", "measurement", "expectations", "seed"},
           {"schema_version", "name", "adapter", "measurement"})
    require(c["schema_version"] == VERSION, "External scenario schema_version must be external-1")
    require(c["adapter"] == adapter["adapter_id"], "Scenario adapter ID does not match the selected adapter.json")
    require(isinstance(c["name"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", c["name"]), "Invalid scenario name")
    values = c.setdefault("parameters", {})
    require(isinstance(values, dict) and values.keys() <= adapter["parameters"].keys(), "Unknown parameter; inspect adapter.json parameters")
    for name, spec in adapter["parameters"].items():
        require(name in values or "default" in spec, f"Missing required parameter: {name}")
        values[name] = parameter(values.get(name, spec.get("default")), spec, f"parameters.{name}")
    require(isinstance(c.setdefault("workload", []), list), "workload must be an array interpreted by your testbench")
    c["seed"] = integer(c.get("seed", 0), "seed", 0, 2**32-1)
    measurement = c["measurement"]
    fields(measurement, {"start_tick", "end_tick", "drain_deadline_tick"}, {"start_tick", "end_tick", "drain_deadline_tick"})
    start, end, drain = (integer(measurement[key], key) for key in ("start_tick", "end_tick", "drain_deadline_tick"))
    require(start < end <= drain, "Require start_tick < end_tick <= drain_deadline_tick")
    for key in measurement:
        measurement[key] = str(int(measurement[key]))
    expected = c.get("expectations", {})
    fields(expected, {"offered", "admitted", "completed", "failed_cancelled", "rejected", "outstanding"})
    for key, value in expected.items():
        integer(value, f"expectations.{key}")
    return c


def source_files(adapter, root):
    root = Path(root).resolve()
    files = {}
    for name in adapter["sources"]:
        path = root/relative_path(name)
        require(path.exists(), f"Source not found: {path}. Update adapter.json sources.")
        candidates = [path, *path.rglob("*")] if path.is_dir() else [path]
        for candidate in candidates:
            require(not candidate.is_symlink() and candidate.resolve().is_relative_to(root), f"Source escapes project: {candidate}")
            if candidate.is_file() and "__pycache__" not in candidate.parts:
                files[candidate.relative_to(root).as_posix()] = candidate
                require(len(files) <= 10000, "More than 10,000 source files; narrow adapter.json sources")
    require(bool(files), "No source files selected")
    return files


def check_capture(directory, adapter, c):
    completion = load_json(directory/relative_path(adapter.get("completion_file", "completion.json")))
    keys = {"schema_version", "finished", "event_count", "loss_count", "stop_tick"}
    fields(completion, keys, keys)
    require(completion["schema_version"] == "capture-1" and completion["finished"] is True, "Testbench did not confirm successful capture completion")
    count = integer(completion["event_count"], "event_count", 1)
    require(integer(completion["loss_count"], "loss_count") == 0, "Capture lost events; results cannot be trusted")
    stop = integer(completion["stop_tick"], "stop_tick")
    start, end, drain = (int(c["measurement"][key]) for key in ("start_tick", "end_tick", "drain_deadline_tick"))
    require(end <= stop <= drain, "Capture must cover measurement end and stop by the drain deadline")
    events = transactions.import_csv(directory/relative_path(adapter.get("trace", {}).get("file", "transactions.csv")), adapter, directory.name)
    require(len(events) == count, "Trace row count differs from the testbench completion marker")
    metrics = transactions.analyze(events, start, end, stop)
    for key, expected in c.get("expectations", {}).items():
        require(metrics["all_transactions"][key] == int(expected), f"Expectation failed: {key} expected {expected}, observed {metrics['all_transactions'][key]}")
    return events, metrics


def artifact_hashes(directory):
    hashes = {}
    for path in directory.rglob("*"):
        require(not path.is_symlink() and path.resolve().is_relative_to(directory), "Run contains a symlink/outside artifact")
        if path.is_file() and path.relative_to(directory).as_posix() not in {"manifest.json", "report.html"}:
            hashes[path.relative_to(directory).as_posix()] = digest(path)
    return hashes


def run(scenario, adapter_path, output_root="runs", timeout=30, build_timeout=300, source_root=None, sdk_root=None, progress=None):
    adapter_path = Path(adapter_path).resolve()
    adapter = load_adapter(adapter_path)
    c = resolve_scenario(scenario, adapter)
    require(all(math.isfinite(value) and value > 0 for value in (timeout, build_timeout)), "Timeouts must be finite and positive")
    directory = Path(output_root).resolve()/f"{c['name']}-{uuid.uuid4().hex[:12]}"
    directory.mkdir(parents=True)
    manifest = {"schema_version": VERSION, "name": c["name"], "run_id": directory.name,
                "platform_version": __version__, "created_utc": datetime.now(timezone.utc).isoformat(),
                "python_version": sys.version, "tools_sha256": {},
                "validity": "invalid_run", "correlation": "uncorrelated", "termination": "preparation_failure",
                "stage": "preparing", "adapter_id": adapter["adapter_id"], "model_kind": adapter["model_kind"],
                "time_resolution_fs": str(adapter["time_resolution_fs"]), "processes": [],
                "qualification_scope": "Generic transaction boundaries; no automatic IP or RTL qualification"}
    dump(directory/"started.json", manifest)
    metrics, interrupted = None, False
    try:
        if progress:
            progress(f"Preparing {directory.name}; evidence: {directory}")
        manifest["platform_revision"] = git("rev-parse", "HEAD")
        manifest["platform_dirty_status"] = git("status", "--porcelain")
        manifest["platform_source_sha256"] = {path.name: digest(path) for path in sorted((ROOT/"tlm_lab").glob("*.py"))}
        dump(directory/"adapter.json", adapter)
        dump(directory/"scenario.json", c)
        inputs = directory/"source"
        inputs.mkdir()
        for name, path in source_files(adapter, source_root or adapter_path.parent).items():
            target = inputs/relative_path(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        manifest["source_sha256"] = {path.relative_to(inputs).as_posix(): digest(path) for path in inputs.rglob("*") if path.is_file()}
        build_dir = directory/"build"
        build_dir.mkdir()
        shutil.copytree(sdk_root or ROOT/"sdk", directory/"sdk", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        context = {"python": sys.executable, "source_dir": str(inputs), "build_dir": str(build_dir),
                   "run_dir": str(directory), "scenario": str(directory/"scenario.json"), "exe_suffix": ".exe" if os.name == "nt" else "",
                   "sdk_dir": str(directory/"sdk"), "seed": c["seed"], **c["measurement"],
                   **{"param_"+name: value for name, value in c["parameters"].items()}}
        for index, command in enumerate([*adapter.get("build", []), adapter["run"]]):
            building = index < len(adapter.get("build", []))
            manifest["stage"] = "building" if building else "simulating"
            stem = f"build-{index}" if building else "simulation"
            if progress:
                progress(f"{directory.name}: {stem}...")
            argv = [argument.format_map(context) for argument in command]
            tool = shutil.which(argv[0])
            if tool:
                manifest["tools_sha256"][tool] = digest(tool)
            result = process(argv, directory, stem, build_timeout if building else timeout, manifest["processes"])
            manifest["termination"] = "build_failure" if building else "simulation_failure"
            if result["timed_out"]:
                manifest["termination"] = "wall_timeout"
            require(result["exit_code"] == 0 and not result["timed_out"] and not result.get("error"),
                    f"{stem} failed: {result.get('error', 'inspect '+stem+'.stderr.log')}")
        manifest["stage"], manifest["termination"] = "analyzing", "evidence_failure"
        if progress:
            progress(f"{directory.name}: checking capture and calculating metrics...")
        require(all(digest(inputs/relative_path(name)) == expected for name, expected in manifest["source_sha256"].items()),
                "Build/testbench modified retained source files; generate outputs under build_dir or run_dir")
        events, metrics = check_capture(directory, adapter, c)
        write_jsonl(directory/"events.jsonl", events)
        dump(directory/"metrics.json", metrics)
        with (directory/"metrics.csv").open("x", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["metric", "value", "unit"])
            for key, value in metrics["latency_tick"].items():
                writer.writerow(["latency_"+key, value, "count" if key == "count" else "tick"])
            for key, value in metrics["completion_window"].items():
                writer.writerow([key, value, "see metrics.json"])
        manifest.update(validity="valid", termination="normal_drain", stage="complete")
    except KeyboardInterrupt:
        interrupted = True
        manifest.update(error="Interrupted by user", termination="interrupted")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
        manifest["error"] = str(error)
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["artifacts_sha256"] = artifact_hashes(directory)
    dump(directory/"manifest.json", manifest)
    from .pilot import render_report
    render_report(directory, manifest, metrics)
    if interrupted:
        raise KeyboardInterrupt
    return directory, manifest


def verify(directory):
    directory = Path(directory).resolve()
    manifest = load_json(directory/"manifest.json")
    require(isinstance(manifest, dict) and manifest.get("schema_version") == VERSION, "Unsupported external run manifest")
    hashes = manifest.get("artifacts_sha256")
    require(isinstance(hashes, dict) and hashes, "Missing evidence hashes")
    for name, expected in hashes.items():
        path = directory/relative_path(name)
        require(not path.is_symlink() and path.resolve().is_relative_to(directory), "Artifact escapes the run directory")
        require(digest(path) == expected, f"Artifact changed: {name}")
    if manifest.get("validity") == "valid":
        require({"started.json", "adapter.json", "scenario.json", "events.jsonl", "metrics.json", "metrics.csv"} <= hashes.keys(),
                "Missing required evidence hashes")
        adapter = load_adapter(directory/"adapter.json")
        require({adapter.get("trace", {}).get("file", "transactions.csv"), adapter.get("completion_file", "completion.json")} <= hashes.keys(),
                "Missing raw capture hashes")
        require(isinstance(manifest.get("source_sha256"), dict) and manifest["source_sha256"], "Missing source snapshot hashes")
        for name, expected in manifest.get("source_sha256", {}).items():
            require(hashes.get("source/"+name) == expected, "Retained source hash differs")
    return manifest
