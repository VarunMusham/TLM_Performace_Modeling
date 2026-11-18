"""Customer onboarding, local diagnostics, templates and offline HTML reports."""
import html
import json
from pathlib import Path
import shutil
import sys
from .config import require
from .runner import ROOT
from .storage import dump, exclusive_text, load_json


def render_report(directory, manifest, metrics):
    escape = lambda value: html.escape(str(value), quote=True)
    def value(number):
        return "Unavailable" if number is None else f"{number:,.4g}" if isinstance(number, float) else str(number)
    def scaled(number, units):
        if number is None:
            return None, units[-1][1]
        for denominator, unit in units:
            if number >= denominator:
                return number/denominator, unit
        return number, units[-1][1]
    content = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
               f"<title>{escape(manifest['name'])} · TLM Performance Lab</title>",
               "<style>body{margin:0;background:#f2f5f9;color:#172b43;font:16px system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:32px 24px}header{border-bottom:2px solid #cbd5e1;padding-bottom:24px}h1{font-size:2.3rem;margin:10px 0}h2{margin-top:32px}.eyebrow{color:#49607a;letter-spacing:.1em;font-size:.8rem}.status{padding:8px 14px;border-radius:20px;background:#dcefe3;display:inline-block}.bad{background:#ffe2df}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:24px 0}.card,section{background:white;border:1px solid #d8e0eb;border-radius:10px;padding:20px}.card strong{display:block;font-size:1.7rem;margin-top:8px}.muted{color:#526579}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:10px;border-bottom:1px solid #e0e5ec}pre{overflow:auto;background:#edf2f7;padding:16px}a{color:#075cac}summary{cursor:pointer}.bar{background:#2763ae;height:16px;border-radius:3px;min-width:1px}.bins td:first-child{width:150px}li{margin:8px 0}code,h1,p,a{overflow-wrap:anywhere}@media(max-width:640px){main{padding:20px 16px}.cards{grid-template-columns:1fr}.eyebrow{letter-spacing:.05em}.bins td:first-child{width:auto}td,th{padding:8px 6px}section{overflow-x:auto}}</style></head><body><main>",
               "<header><div class='eyebrow'>TLM PERFORMANCE LAB · LOCAL EXPERIMENT REPORT</div>",
               f"<h1>{escape(manifest['name'])}</h1>",
               f"<span class='status {'bad' if manifest['validity'] != 'valid' else ''}'>{escape(manifest['validity'])}</span>",
               f"<p>Adapter <strong>{escape(manifest['adapter_id'])}</strong> · {escape(manifest['model_kind'])} model · capture {escape(manifest['termination'])}</p>",
               "<p class='muted'>Boundary performance measurements. Accuracy against your real IP or RTL requires independent validation.</p></header>"]
    if manifest.get("error"):
        content += ["<h2>What needs attention</h2><section>", f"<p>{escape(manifest['error'])}</p>",
                    f"<p>Stopped during <strong>{escape(manifest['stage'])}</strong>. Open the relevant build or simulation log below, fix the input or tool setup, and start a new run.</p></section>"]
    if metrics:
        accounting, latency, completion = metrics["accounting"], metrics["latency_tick"], metrics["completion_window"]
        throughput, throughput_unit = scaled(completion["payload_bytes_per_second"],
                                             [(10**9, "GB/s"), (10**6, "MB/s"), (1000, "kB/s"), (1, "bytes/s")])
        tick_size, tick_unit = scaled(int(metrics["time_resolution_fs"]),
                                     [(10**15, "s"), (10**12, "ms"), (10**9, "µs"), (10**6, "ns"), (1000, "ps"), (1, "fs")])
        content.append("<div class='cards'>")
        for label, number in (("Completed admission cohort", accounting["completed"]), ("Mean latency · ticks", latency["mean"]),
                              ("Payload throughput · "+throughput_unit, throughput),
                              ("Peak requests in flight", metrics["inflight"]["peak"])):
            content.append(f"<div class='card'>{escape(label)}<strong>{escape(value(number))}</strong></div>")
        content.append("</div><h2>How to read these results</h2><section>")
        content.append(f"<p>One tick = {escape(value(tick_size))} {escape(tick_unit)}. The measurement window is [{escape(metrics['window']['start_tick'])}, {escape(metrics['window']['end_tick'])}); capture stops at {escape(metrics['window']['stop_tick'])}.</p>")
        content.append("<p>Throughput prefixes use decimal units: 1 GB/s = 1,000,000,000 bytes/s.</p>")
        content.append("<p>Latency follows requests admitted inside the window through completion. Throughput counts successful completions inside the window, including requests admitted earlier.</p>")
        if metrics["small_sample"]:
            content.append("<p><strong>Small sample:</strong> percentiles describe this run; they do not establish tail confidence.</p>")
        if accounting["outstanding_censored"]:
            content.append("<p><strong>Unfinished requests:</strong> latency excludes unfinished work. Increase the drain deadline before drawing conclusions about tail latency.</p>")
        if not metrics["offer_visibility_complete"]:
            content.append("<p>Offer events are incomplete; offered rate and admission-wait coverage cannot describe all traffic.</p>")
        if completion["unknown_payload_sizes"]:
            content.append("<p>Some completions have no payload size, so byte throughput is unavailable.</p>")
        content.append("</section><h2>Request accounting</h2><section><table><tr><th>Admission cohort</th><th>Requests</th></tr>")
        for label, key in (("Admitted", "admitted"), ("Completed successfully", "completed"), ("Failed or cancelled", "failed_cancelled"), ("Still outstanding at capture stop", "outstanding_censored")):
            content.append(f"<tr><td>{label}</td><td>{accounting[key]}</td></tr>")
        content.append("</table></section>")
        histogram = metrics["latency_histogram"]
        if histogram:
            maximum = max(item["count"] for item in histogram)
            content.append("<h2>Latency distribution</h2><section><table class='bins'><tr><th>Ticks [start,end)</th><th>Completed requests</th><th>Count</th></tr>")
            for item in histogram:
                content.append(f"<tr><td>{item['start_tick']}–{item['end_tick']}</td><td><div class='bar' style='width:{100*item['count']/maximum:.2f}%'></div></td><td>{item['count']}</td></tr>")
            content.append("</table></section>")
        content.append("<h2>Available observations</h2><section><p>Transaction admission, completion, failures and concurrency are measured from the testbench trace. Internal queues, credits, stalls, power and wire bandwidth need their own probes.</p></section>")
    content.append("<h2>Evidence and next steps</h2><section><p>Use metrics.csv for spreadsheets, events.jsonl for comparison, and the logs for diagnosis. All processing stays on this machine.</p><ul>")
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "report.html":
            content.append(f"<li><a href='{escape(path.name)}'>{escape(path.name)}</a></li>")
    content.append("</ul><details><summary>Run metadata</summary><pre>"+escape(json.dumps(manifest, indent=2))+"</pre></details></section></main></body></html>")
    with exclusive_text(directory/"report.html") as stream:
        stream.write("\n".join(content))


def initialize(directory, template="python"):
    directory = Path(directory).resolve()
    require(not directory.exists(), f"Folder already exists: {directory}. Choose a new folder to preserve your files.")
    source = ROOT/"examples"/("portable_queue" if template == "python" else "external_cpp")
    shutil.copytree(source, directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    readme = """# Your IP pilot project

1. Run the supplied example first using the commands printed by `init`.
2. Replace model.py/model.hpp and testbench.py/testbench.cpp with your source and testbench.
3. Edit adapter.json: source files, build/run argument arrays, parameters and tick resolution.
4. Instrument your testbench's actual offer/admission/completion points using sdk/python or sdk/cpp.
5. Change model_kind from synthetic when this uses your real model. Review timing assumptions.
6. Run doctor, validate, then run. Open the generated report.html.

The SDK is copied into each run automatically. Build outputs and source snapshots
live in separate run folders. Your original source files are not modified.
See docs/CUSTOMER_GUIDE.md and docs/EXTERNAL_ADAPTERS.md in the lab distribution.
"""
    (directory/"README.md").write_text(readme, encoding="utf-8")
    return directory


def doctor(adapter_path=None, wdt=False):
    seen = set()
    checks = [{"name": "Python 3.9+", "required": True, "ok": sys.version_info >= (3, 9),
               "detail": sys.executable, "action": "Install Python 3.9 or newer"}]
    if adapter_path:
        from .external import load_adapter, source_files
        adapter = load_adapter(adapter_path)
        try:
            files = source_files(adapter, Path(adapter_path).resolve().parent)
            checks.append({"name": "Source/testbench files", "required": True, "ok": True, "detail": f"{len(files)} selected", "action": ""})
        except (ValueError, OSError) as error:
            checks.append({"name": "Source/testbench files", "required": True, "ok": False, "detail": str(error), "action": "Fix adapter.json sources"})
        commands = [*adapter.get("build", []), adapter["run"]]
        for label, alternatives in adapter.get("tools", {}).items():
            resolved = next((shutil.which(tool) for tool in alternatives if shutil.which(tool)), None)
            seen.update(alternatives)
            checks.append({"name": label, "required": True, "ok": bool(resolved), "detail": resolved or " / ".join(alternatives)+" not found",
                           "action": "Install one of these tools or use its absolute path: "+", ".join(alternatives)})
        for tool in sorted({command[0] for command in commands if "{" not in command[0]}):
            if tool in seen:
                continue
            seen.add(tool)
            resolved = shutil.which(tool)
            checks.append({"name": tool, "required": True, "ok": bool(resolved), "detail": resolved or "Not on PATH",
                           "action": f"Install {tool} or use its absolute path in adapter.json"})
        requirements = adapter.get("requirements", [])
    else:
        requirements = ["The portable demo needs only Python. Native IPs need their own compiler/simulator dependencies."]
    for tool in ("cmake", "ninja", "g++", "cl", "iverilog", "vvp"):
        if tool in seen:
            continue
        resolved = shutil.which(tool)
        required = wdt and tool in {"cmake", "ninja"}
        checks.append({"name": tool, "required": required, "ok": bool(resolved), "detail": resolved or "Not on PATH",
                       "action": f"Add {tool} to PATH if your selected model requires it"})
    if wdt:
        compiler = shutil.which("g++") or shutil.which("cl")
        checks.append({"name": "C++ compiler for WDT", "required": True, "ok": bool(compiler), "detail": compiler or "Not on PATH",
                       "action": "Use your MSYS2 UCRT64 or Visual Studio developer shell; pass --compiler to setup-wdt if needed"})
    return {"ready": all(check["ok"] for check in checks if check["required"]), "checks": checks, "requirements": requirements,
            "next": "python tlm-lab.py demo --open" if not adapter_path else "Run validate and then run with --adapter PATH"}
