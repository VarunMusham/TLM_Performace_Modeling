"""Process isolation, immutable evidence, reproducibility, and report production."""
import csv
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from . import __version__
from .config import require, validate, write_workload
from .events import read_pilot, normalize, write_jsonl, validate_lifecycles, compare_events
from .metrics import analyze

ROOT = Path(__file__).resolve().parent.parent


def dump(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def git(*args):
    result = subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
                            cwd=ROOT, capture_output=True, text=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else None


def provenance():
    # Hash source bytes even when Git has no clean revision (include untracked source).
    hashes = {}
    for folder in ("tlm_lab", "examples", "rtl", "adapters", "configs", "tools", "docs", "tests"):
        for path in sorted((ROOT/folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                hashes[path.relative_to(ROOT).as_posix()] = digest(path)
    for name in ("CMakeLists.txt", "README.md", ".gitattributes", ".gitignore"):
        hashes[name] = digest(ROOT/name)
    return {"revision": git("rev-parse", "HEAD"), "dirty_status": git("status", "--porcelain"),
            "source_sha256": hashes, "platform_version": __version__}


def process(command, directory, stem, timeout):
    start = time.perf_counter()
    with (directory/f"{stem}.stdout.log").open("xb") as out, (directory/f"{stem}.stderr.log").open("xb") as err:
        p = subprocess.Popen(list(map(str, command)), cwd=directory, stdout=out, stderr=err,
                             start_new_session=os.name != "nt",
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        timed_out = False
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=10)
            else:
                import signal
                os.killpg(p.pid, signal.SIGKILL)
            p.kill()
            p.wait()
    return {"command": list(map(str, command)), "cwd": str(directory), "exit_code": p.returncode,
            "wall_seconds": time.perf_counter()-start, "timed_out": timed_out}


def report(directory, manifest, metrics=None, correlation=None):
    sections = [("Run", manifest), ("Metrics", metrics), ("Correlation", correlation)]
    text = "<!doctype html><html lang='en'><meta charset='utf-8'><title>TLM performance run</title>"
    text += "<style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px;color:#182532}pre{background:#f3f5f7;padding:20px;overflow:auto}a{color:#145caa}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #ccd3db}summary{cursor:pointer;padding:12px 0}</style>"
    text += f"<h1>{html.escape(manifest.get('name', 'TLM run'))}</h1>"
    text += "<table><tr><th>Experiment validity</th><th>RTL correlation</th><th>Termination</th></tr><tr>"
    for key in ("validity", "correlation", "termination"):
        text += f"<td>{html.escape(str(manifest.get(key)))}</td>"
    text += "</tr></table>"
    text += "<p>Ticks are 1 ns. Results apply to this WDT configuration. Real link-IP qualification is pending.</p>"
    if metrics:
        text += "<h2>Measured register performance</h2><table><tr><th>Metric</th><th>Value</th></tr>"
        values = [("Window [start,end), ns", f"[{metrics['window']['start_tick']},{metrics['window']['end_tick']})"),
                  ("Admission cohort completed", metrics["accounting"]["completed"]),
                  ("Failed or cancelled", metrics["accounting"]["failed_cancelled"]),
                  ("Outstanding / censored", metrics["accounting"]["outstanding_censored"]),
                  ("Mean latency, ns", metrics["latency_tick"]["mean"]),
                  ("Maximum latency, ns", metrics["latency_tick"]["max"]),
                  ("Completion-window payload throughput, bytes/ns", metrics["completion_window"]["payload_bytes_per_ns"]),
                  ("Mean watchdog timeout, cycles", metrics["wdt_timeout_cycles"]["mean"])]
        for label, value in values:
            text += f"<tr><td>{html.escape(label)}</td><td>{html.escape(str(value))}</td></tr>"
        text += "</table><p>Latency follows the admission cohort through drain; throughput uses completions within the window.</p>"
        if metrics["small_sample"]:
            text += "<p>Small sample: tail quantiles are descriptive and do not qualify as regression gates.</p>"
    if correlation and correlation.get("first_mismatch"):
        text += "<h2>First mismatch</h2><pre>" + html.escape(json.dumps(correlation["first_mismatch"], indent=2)) + "</pre>"
    for title, value in sections:
        text += f"<details><summary>{title} details</summary><pre>{html.escape(json.dumps(value, indent=2))}</pre></details>"
    text += "<h2>Evidence</h2><ul>"
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "report.html":
            text += f"<li><a href='{html.escape(path.name, quote=True)}'>{html.escape(path.name)}</a></li>"
    (directory/"report.html").write_text(text + "</ul></html>\n", encoding="utf-8")


def check_responses(path, c):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == ["transaction_id", "tick", "status", "value"], "Response columns differ")
        responses = list(reader)
    require(len(responses) == len(c["workload"]), "Incomplete response accounting")
    for i, (op, row) in enumerate(zip(c["workload"], responses), 1):
        require(int(row["transaction_id"]) == i, "Response identity mismatch")
        require(int(row["status"]) == op.get("expect_status", 1), f"Unexpected response: {op['id']}")
        if "expect_value" in op:
            require(int(row["value"]) == int(op["expect_value"]), f"Unexpected read value: {op['id']}")
    return responses


def expectation_check(events, c):
    for expected in c.get("expectations", []):
        selected = [e for e in events if e["event"] == expected["event"]]
        require([int(e["observed_tick"]) for e in selected] == list(map(int, expected["ticks"])),
                f"Expectation failed: {expected['event']} ticks")
        if "values" in expected:
            require([int(e["value"]) for e in selected] == list(map(int, expected["values"])),
                    f"Expectation failed: {expected['event']} values")


def run(c, executable, output_root="runs", timeout=30, rtl=False, allow_unqualified=False,
        iverilog="iverilog", vvp="vvp"):
    validate(c)
    require(math.isfinite(timeout) and timeout > 0, "Host timeout must be finite and positive")
    executable = Path(executable).resolve(strict=True)
    directory = Path(output_root).resolve()/f"{c['name']}-{uuid.uuid4().hex[:12]}"
    directory.mkdir(parents=True, exist_ok=False)
    run_id = directory.name
    trace = c.get("trace", {"mode": "full"})
    dump(directory/"scenario.json", c)
    write_workload(c, directory/"workload.txt")
    # Preserve exact executable bytes so replay does not silently use a rebuilt binary.
    stored_executable = directory/("simulator" + executable.suffix)
    shutil.copy2(executable, stored_executable)
    m = {"schema_version": "1", "run_id": run_id, "name": c["name"], "created_utc": datetime.now(timezone.utc).isoformat(),
         "validity": "invalid_run", "correlation": "uncorrelated", "termination": "initializing",
         "host": {"os": platform.platform(), "python": platform.python_version(), "machine": platform.machine()},
         "provenance": provenance(), "executable_original": str(executable), "executable_sha256": digest(stored_executable),
         "time_resolution_ns": 1, "trace": trace, "processes": [], "loss_count": None,
         "qualification_scope": "This WDT scenario and exact source/binary hashes only",
         "requested_rtl": rtl, "allow_unqualified_systemc": allow_unqualified,
         "build": {}}
    cache = executable.parent/"CMakeCache.txt"
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            if any(line.startswith(k+":") for k in ("CMAKE_CXX_COMPILER", "CMAKE_BUILD_TYPE", "CMAKE_CXX_FLAGS", "SystemCLanguage_DIR")):
                m["build"][line.split(":", 1)[0]] = line.split("=", 1)[1]
    compiler = m["build"].get("CMAKE_CXX_COMPILER")
    if compiler and Path(compiler).exists():
        info = subprocess.run([compiler, "--version"], capture_output=True, text=True, timeout=10)
        m["build"]["compiler_version"] = info.stdout.strip()
    m["host"]["path"] = os.environ.get("PATH", "")
    if rtl:
        for key, tool in (("iverilog", iverilog), ("vvp", vvp)):
            resolved = shutil.which(str(tool))
            if resolved:
                version = subprocess.run([resolved, "-V"], capture_output=True, text=True, timeout=10)
                m["build"][key] = {"path": resolved, "sha256": digest(resolved),
                                    "version": (version.stdout+version.stderr).strip()}
    dump(directory/"adapter.json", json.loads((ROOT/"configs"/"adapter_contract.example.json").read_text()))
    # A checkpoint manifest survives unexpected interruption; final manifest is written once.
    dump(directory/"started.json", m)
    metrics = correlation = None
    try:
        command = [stored_executable, directory/"workload.txt", directory/"raw.csv" if trace["mode"] == "full" else "-",
                   directory/"responses.csv", directory/"native.json", str(trace.get("max_events", 1000000))]
        p = process(command, directory, "simulation", timeout)
        m["processes"].append(p)
        if p["timed_out"]:
            m["termination"] = "wall_timeout"
            raise ValueError("Simulation exceeded host deadline")
        if p["exit_code"]:
            m["termination"] = "simulated_timeout" if p["exit_code"] == 3 else "simulation_failure"
            raise ValueError(f"Simulator exit {p['exit_code']}; see simulation.stderr.log")
        native = json.loads((directory/"native.json").read_text(encoding="utf-8"))
        m["native"] = native
        import re
        qualified = bool(re.search(r"\b2\.3\.4(?:[.\s-]|$)", native["systemc_version"]))
        m["target_toolchain"] = qualified
        require(qualified or allow_unqualified, "Actual SystemC is not 2.3.4; use explicit compatibility override")
        require(native["finished"] is True and native["resolution_ns"] == 1, "Native completion metadata differs")
        check_responses(directory/"responses.csv", c)
        if trace["mode"] == "full":
            rows = read_pilot(directory/"raw.csv")
            m["loss_count"] = max(0, native["event_count"]-len(rows))
            require(len(rows) == native["event_count"], "Trace loss against native counter")
            events = normalize(rows, c, run_id)
            validate_lifecycles(events, c)
            write_jsonl(directory/"events.jsonl", events)
            expectation_check(events, c)
            metrics = analyze(events, int(c["measurement"]["start_tick"]), int(c["measurement"]["end_tick"]))
            metrics["host"] = {"wall_seconds": p["wall_seconds"], "trace_bytes": (directory/"raw.csv").stat().st_size,
                               "simulated_ns_per_wall_second": (int(c["measurement"]["drain_deadline_tick"])+1)/p["wall_seconds"]}
            dump(directory/"metrics.json", metrics)
            with (directory/"metrics.csv").open("x", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["metric", "value", "unit"])
                for key, value in metrics["latency_tick"].items():
                    writer.writerow([f"latency_{key}", value, "count" if key == "count" else "ns"])
                writer.writerow(["payload_throughput", metrics["completion_window"]["payload_bytes_per_ns"], "bytes/ns"])
        else:
            m["loss_count"] = 0
            require(not rtl, "RTL event comparison requires full tracing")
            require(not c.get("expectations"), "Event expectations require full tracing")
        m["validity"], m["termination"] = "valid", "normal_drain"
        if rtl:
            from .rtl import run_reference
            reference = run_reference(c, directory, timeout, m["processes"], iverilog, vvp)
            correlation = compare_events(events, reference)
            if (directory/"rtl_responses.csv").read_text() != (directory/"responses.csv").read_text():
                difference = {"reason": "response_table", "left": "responses.csv", "right": "rtl_responses.csv"}
                correlation["status"] = "fail"
                correlation["mismatch_count"] += 1
                correlation["first_mismatch"] = correlation["first_mismatch"] or difference
                correlation["differences"].append(difference)
            m["correlation"] = correlation["status"] if qualified else "inconclusive"
            if not qualified:
                correlation["status"] = "inconclusive"
                correlation["reason"] = "Non-target SystemC compatibility run"
            dump(directory/"correlation.json", correlation)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError, TypeError) as error:
        if m["validity"] == "valid":
            m["correlation"] = "inconclusive"
        else:
            m["validity"] = "invalid_run"
        if m["termination"] == "initializing":
            m["termination"] = "evidence_failure"
        m["error"] = str(error)
    m["artifacts_sha256"] = {p.name: digest(p) for p in directory.iterdir() if p.is_file()}
    dump(directory/"manifest.json", m)
    report(directory, m, metrics, correlation)
    return directory, m


def verify_run(directory):
    directory = Path(directory).resolve()
    m = json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
    require(m.get("schema_version") == "1" and "artifacts_sha256" in m, "Unsupported run manifest")
    for name, expected in m["artifacts_sha256"].items():
        require(Path(name).name == name, "Invalid artifact path")
        require(digest(directory/name) == expected, f"Artifact changed: {name}")
    return m
