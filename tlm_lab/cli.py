import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import uuid
import webbrowser
from .config import load, validate, require, fields, integer
from .events import read_jsonl, read_pilot, normalize, validate_lifecycles, write_jsonl, compare_events
from .metrics import analyze
from .runner import run, dump, verify_run, ROOT, process, default_executable
from .storage import load_json


def succeeded(m):
    return m["validity"] == "valid" and (not m.get("requested_rtl") or m["correlation"] == "pass")


def manifest_schema(directory):
    manifest = load_json(Path(directory)/"manifest.json")
    require(isinstance(manifest, dict), "Run manifest must be a JSON object")
    return manifest.get("schema_version")


def show(directory, m):
    print(json.dumps({"run": str(directory), "validity": m["validity"], "correlation": m["correlation"],
                      "termination": m["termination"], "error": m.get("error"), "report": str(directory/"report.html")}, indent=2))


def execute(args, c=None):
    if getattr(args, "adapter", None):
        from .external import run as external_run
        require(not args.rtl, "External adapters use independent boundary-trace comparison; --rtl is the WDT reference gate")
        return external_run(c if c is not None else load_json(args.scenario), args.adapter, args.output,
                            args.timeout, args.build_timeout, progress=lambda message: print(message, file=sys.stderr, flush=True))
    return run(c or load(args.scenario), args.executable, args.output, args.timeout,
               args.rtl, args.allow_unqualified_systemc)


def generated(seed, count=30, template=None):
    seed = integer(seed, "seed", 0, 2**32-1)
    count = integer(count, "count", 1, 100000)
    rng = random.Random(seed)
    c = copy.deepcopy(template) if template else load(ROOT/"configs"/"wdt_scenario.example.json")
    c["name"], c["seed"] = f"wdt_seed_{seed}", seed
    c.pop("expectations", None)
    operations = []
    for i in range(count):
        addr, value = rng.choice([(0, rng.randrange(8)), (4, rng.choice([1, 2, 7, 2**32-1])),
                                  (12, 0xA5A55A5A), (16, 1), (8, 0), (16, 0)])
        read = addr == 8 or rng.randrange(3) == 0 and addr != 12
        op = {"id": f"op{i}", "op": "read32" if read else "write32", "address": addr, "value": value,
              "delay_tick": rng.randrange(12)}
        if i:
            op.update(after_completion_of=f"op{i-1}", offset_tick=rng.randrange(31))
        else:
            op["offer_tick"] = int(c["reset"][1]["tick"])
        operations.append(op)
    c["workload"] = operations
    budget = int(c["reset"][1]["tick"]) + count*(int(c["parameters"]["bus_latency_tick"])+int(c["clock"]["period_tick"])+50)+100
    c["measurement"] = {"start_tick": c["reset"][1]["tick"], "end_tick": str(budget), "drain_deadline_tick": str(budget+100)}
    return validate(c)


def batch(args):
    adapter = None
    if args.adapter:
        from .external import load_adapter, resolve_scenario, run as external_run
        adapter = load_adapter(args.adapter)
        require(not args.rtl, "--rtl is available for the built-in WDT; compare external boundary traces independently")
        base = resolve_scenario(load_json(args.scenario), adapter)
    else:
        base = load(args.scenario)
    spec = load_json(args.matrix)
    fields(spec, {"parameters", "seeds", "workload_generator"}, {"parameters"})
    generator = spec.get("workload_generator")
    require(not adapter or generator is None, "External workload generation belongs in your testbench; remove workload_generator")
    if generator is not None:
        fields(generator, {"count"}, {"count"})
        count = integer(generator["count"], "generator count", 1, 100000)
    require(isinstance(spec["parameters"], dict), "Matrix parameters must be an object")
    allowed = ({"parameters."+name for name in adapter["parameters"]} if adapter else
               {"parameters.bus_latency_tick", "clock.period_tick", "clock.first_rising_tick"})
    require(set(spec["parameters"]) <= allowed, "Unsupported sweep parameter")
    axes = list(spec["parameters"])
    values = [spec["parameters"][k] for k in axes] + [spec.get("seeds", [base.get("seed", 0)])]
    require(all(isinstance(v, list) and v for v in values), "Empty matrix axis")
    total = 1
    for v in values:
        total *= len(v)
    require(total <= args.max_runs, "Sweep exceeds --max-runs")
    configs = []
    for index, combination in enumerate(itertools.product(*values)):
        c = copy.deepcopy(base)
        for key, value in zip(axes, combination):
            group, field = key.split(".")
            c[group][field] = value
        c["seed"] = combination[-1]
        if generator:
            c = generated(c["seed"], count, c)
        suffix = f"_s{index}"
        c["name"] = c["name"][:80-len(suffix)] + suffix
        configs.append(resolve_scenario(c, adapter) if adapter else validate(c))
    directory = Path(args.output).resolve()/f"sweep-{uuid.uuid4().hex[:12]}"
    directory.mkdir(parents=True, exist_ok=False)
    dump(directory/"matrix.json", spec)
    def task(c):
        try:
            d, m = (external_run(c, args.adapter, directory, args.timeout, args.build_timeout) if adapter else
                    run(c, args.executable, directory, args.timeout, args.rtl, args.allow_unqualified_systemc))
            return {"run": str(d), "validity": m["validity"], "correlation": m["correlation"], "passed": succeeded(m)}
        except (ValueError, OSError) as e:
            return {"name": c["name"], "passed": False, "error": str(e)}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(task, configs))
    dump(directory/"summary.json", results)
    print(json.dumps({"sweep": str(directory), "runs": len(results), "passed": sum(r["passed"] for r in results)}, indent=2))
    return 0 if all(r["passed"] for r in results) else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="TLM Performance Lab — run, measure and compare IP testbenches locally",
                                epilog="New here? Run 'demo --open' for a Python-only walkthrough, or 'init my-ip' to start your project.")
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run a complete Python-only example; no compiler or simulator required")
    demo.add_argument("--output", default="runs")
    demo.add_argument("--open", action="store_true", help="Open the local HTML report in your browser")
    init = sub.add_parser("init", help="Create a source/testbench project you can adapt to your IP")
    init.add_argument("directory")
    init.add_argument("--template", choices=("python", "cpp"), default="python")
    doctor = sub.add_parser("doctor", help="Check required and optional tools without building or running your IP")
    doctor.add_argument("--adapter", help="Path to your project's adapter.json")
    doctor.add_argument("--wdt", action="store_true")
    doctor.add_argument("--json", action="store_true")
    setup = sub.add_parser("setup-wdt", help="Build bundled SystemC source and the WDT example without downloads")
    setup.add_argument("--compiler")
    setup.add_argument("--generator", default="Ninja")
    setup.add_argument("--jobs", type=int, default=4)
    b = sub.add_parser("build", help="Configure and build against a SystemC installation")
    b.add_argument("--systemc-prefix", required=True)
    b.add_argument("--build-dir", default="build-234")
    b.add_argument("--compiler")
    b.add_argument("--allow-unqualified-systemc", action="store_true")
    v = sub.add_parser("validate", help="Validate strict scenario and adapter capability contract")
    v.add_argument("scenario")
    v.add_argument("--adapter", help="Validate an external scenario using this adapter manifest")
    adapters = sub.add_parser("adapters", help="List examples or inspect a customer adapter manifest")
    adapters.add_argument("--manifest")
    for name in ("run", "sweep", "profile"):
        r = sub.add_parser(name, help={"run": "Build/run a scenario and write an offline report", "sweep": "Explore a parameter matrix", "profile": "Check WDT trace-on/off equivalence"}[name])
        r.add_argument("scenario")
        r.add_argument("--executable", default=str(default_executable()))
        r.add_argument("--output", default="runs")
        r.add_argument("--timeout", type=float, default=30)
        r.add_argument("--rtl", action="store_true")
        r.add_argument("--allow-unqualified-systemc", action="store_true")
        r.add_argument("--adapter", help="Source/testbench adapter.json; omit for the built-in WDT")
        r.add_argument("--build-timeout", type=float, default=300, help="Host seconds per external build command")
        r.add_argument("--open", action="store_true", help="Open the report after a single run")
        if name == "sweep":
            r.add_argument("--matrix", required=True)
            r.add_argument("--jobs", type=int, default=1)
            r.add_argument("--max-runs", type=int, default=100)
    replay = sub.add_parser("replay", help="Verify evidence, rerun recorded binary, and compare semantic digest")
    replay.add_argument("run_dir")
    replay.add_argument("--output", default="runs")
    replay.add_argument("--timeout", type=float, default=30)
    for name in ("analyze", "compare", "import-rtl", "regress"):
        r = sub.add_parser(name)
        if name == "analyze":
            r.add_argument("run_dir")
        elif name == "compare":
            r.add_argument("left")
            r.add_argument("right")
            r.add_argument("--tolerance-tick", type=int, default=0)
        elif name == "import-rtl":
            r.add_argument("trace")
            r.add_argument("--scenario", required=True)
        else:
            r.add_argument("baseline")
            r.add_argument("candidate")
            r.add_argument("--absolute", type=float, default=0)
            r.add_argument("--relative", type=float, default=0)
        r.add_argument("--output", required=True)
    g = sub.add_parser("generate", help="Generate a reproducible seeded WDT workload")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--count", type=int, default=30)
    g.add_argument("--output", required=True)
    if argv == [] or argv is None and len(sys.argv) == 1:
        p.print_help()
        return 0
    args = p.parse_args(argv)
    try:
        if args.command == "demo":
            from .external import run as external_run
            example = ROOT/"examples"/"portable_queue"
            d, m = external_run(load_json(example/"scenario.json"), example/"adapter.json", args.output)
            show(d, m)
            if args.open:
                webbrowser.open((d/"report.html").as_uri())
            return 0 if succeeded(m) else 1
        elif args.command == "init":
            from .pilot import initialize
            directory = initialize(args.directory, args.template)
            launcher = f'"{sys.executable}" "{ROOT / "tlm-lab.py"}"'
            print(f'Created {directory}\n\nTry the example:\n{launcher} doctor --adapter "{directory / "adapter.json"}"\n'
                  f'{launcher} run "{directory / "scenario.json"}" --adapter "{directory / "adapter.json"}" --open\n\n'
                  'Then replace the source/testbench and edit adapter.json. See docs/CUSTOMER_GUIDE.md.')
        elif args.command == "doctor":
            from .pilot import doctor as diagnose
            result = diagnose(args.adapter, args.wdt)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                for check in result["checks"]:
                    status = "OK" if check["ok"] else "MISSING" if check["required"] else "OPTIONAL"
                    print(f"[{status}] {check['name']}: {check['detail']}")
                    if check["required"] and not check["ok"]:
                        print("  Next: "+check["action"])
                print("\n"+"\n".join(result["requirements"])+"\n\nNext: "+result["next"])
            return 0 if result["ready"] else 1
        elif args.command == "setup-wdt":
            from .setup import setup_wdt
            print(setup_wdt(args.compiler, args.generator, args.jobs))
        elif args.command == "validate":
            if args.adapter:
                from .external import load_adapter, resolve_scenario
                c = resolve_scenario(load_json(args.scenario), load_adapter(args.adapter))
                print(f"VALID {c['adapter']} external-1")
            else:
                load(args.scenario)
                print("VALID hybrid_wdt schema 1")
        elif args.command == "adapters":
            if args.manifest:
                from .external import load_adapter
                print(json.dumps(load_adapter(args.manifest), indent=2))
            else:
                print(json.dumps({"built_in": load_json(ROOT/"configs"/"adapter_contract.example.json"),
                                  "external_examples": [str(ROOT/"examples"/name/"adapter.json") for name in ("portable_queue", "external_cpp")],
                                  "new_ip": "init my-ip --template python|cpp; then edit adapter.json"}, indent=2))
        elif args.command == "build":
            directory = Path(args.build_dir).resolve()
            directory.mkdir(parents=True, exist_ok=True)
            logdir = directory/("configure-" + uuid.uuid4().hex[:12])
            logdir.mkdir()
            command = ["cmake", "-S", ROOT, "-B", directory, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                       "-DCMAKE_PREFIX_PATH=" + str(Path(args.systemc_prefix).resolve())]
            if args.compiler:
                command.append("-DCMAKE_CXX_COMPILER=" + args.compiler)
            command.append("-DTLM_LAB_ALLOW_UNQUALIFIED_SYSTEMC=" + ("ON" if args.allow_unqualified_systemc else "OFF"))
            records = []
            try:
                for stem, cmd in [("configure", command), ("build", ["cmake", "--build", directory, "--parallel", "4"])]:
                    result = process(cmd, logdir, stem, 120, records)
                    require(result["exit_code"] == 0 and not result["timed_out"] and not result.get("error"),
                            f"{stem} failed; see {logdir}")
            finally:
                dump(logdir/"build.json", records)
            print(directory)
        elif args.command == "run":
            d, m = execute(args)
            show(d, m)
            if args.open:
                webbrowser.open((d/"report.html").as_uri())
            return 0 if succeeded(m) else 1
        elif args.command == "generate":
            require(1 <= args.count <= 100000, "count must be 1..100000")
            integer(args.seed, "seed", 0, 2**32-1)
            dump(args.output, generated(args.seed, args.count))
        elif args.command == "sweep":
            require(1 <= args.jobs <= 32 and args.max_runs > 0, "Invalid sweep limits")
            return batch(args)
        elif args.command == "profile":
            require(not args.adapter, "Trace-off equivalence is WDT-specific; external adapters must define their own capture-off behavior")
            c = load(args.scenario)
            c.setdefault("trace", {})["mode"] = "full"
            profile_dir = Path(args.output).resolve()/("profile-"+uuid.uuid4().hex[:12])
            d1, m1 = run(c, args.executable, profile_dir, args.timeout, args.rtl, args.allow_unqualified_systemc)
            off = copy.deepcopy(c)
            off["trace"]["mode"] = "off"
            off.pop("expectations", None)
            d2, m2 = run(off, args.executable, profile_dir, args.timeout, False, args.allow_unqualified_systemc)
            equal = (succeeded(m1) and succeeded(m2) and m1["native"]["event_digest"] == m2["native"]["event_digest"]
                     and m1["native"]["event_count"] == m2["native"]["event_count"]
                     and (d1/"responses.csv").read_bytes() == (d2/"responses.csv").read_bytes())
            result = {"trace_on": str(d1), "trace_off": str(d2), "semantic_equivalence": equal,
                      "method": "native semantic event count/digest plus byte-identical response table",
                      "wall_ratio_on_over_off": (m1["processes"][0]["wall_seconds"]/m2["processes"][0]["wall_seconds"]
                                                 if equal else None),
                      "runtime_scope": "single paired host measurement; no TLM/RTL speedup claim"}
            dump(profile_dir/"profile.json", result)
            print(json.dumps(result, indent=2))
            return 0 if equal else 1
        elif args.command == "replay":
            old_dir = Path(args.run_dir).resolve()
            if manifest_schema(old_dir) == "external-1":
                from .external import verify, run as external_run
                from .transactions import read_events, compare
                old = verify(old_dir)
                require(old["validity"] == "valid", "Cannot replay an invalid experiment as a successful run")
                replay_dir = Path(args.output).resolve()/("replay-"+uuid.uuid4().hex[:12])
                d, m = external_run(load_json(old_dir/"scenario.json"), old_dir/"adapter.json", replay_dir, args.timeout,
                                    source_root=old_dir/"source", sdk_root=old_dir/"sdk")
                comparison = compare(read_events(old_dir/"events.jsonl"), read_events(d/"events.jsonl")) if succeeded(m) else {"status": "fail"}
                dump(replay_dir/"replay.json", {"original": str(old_dir), "reproduced": str(d), "comparison": comparison,
                                               "method": "Rebuild retained source/testbench/SDK using host tools; compare transaction boundaries"})
                show(d, m)
                return 0 if comparison["status"] == "pass" else 1
            old = verify_run(old_dir)
            require(old["validity"] == "valid", "Cannot reproduce an invalid experiment as a successful run")
            executable = old_dir/old.get("executable_artifact", "simulator.exe" if (old_dir/"simulator.exe").exists() else "simulator")
            replay_dir = Path(args.output).resolve()/("replay-"+uuid.uuid4().hex[:12])
            d, m = run(load(old_dir/"scenario.json"), executable, replay_dir, args.timeout,
                       old.get("requested_rtl", False), old.get("allow_unqualified_systemc", False))
            same = succeeded(m) and m.get("native", {}).get("event_digest") == old.get("native", {}).get("event_digest")
            same = (same and m["native"]["event_count"] == old["native"]["event_count"]
                    and (old_dir/"responses.csv").read_bytes() == (d/"responses.csv").read_bytes())
            if old.get("requested_rtl") and same:
                same = (old_dir/"wdt_reference.sv").read_bytes() == (d/"wdt_reference.sv").read_bytes()
            dump(replay_dir/"replay.json", {"original": str(old_dir), "reproduced": str(d), "semantic_digest_matches": same,
                                          "method": "native semantic event count/digest plus byte-identical response table"})
            show(d, m)
            return 0 if same else 1
        elif args.command == "analyze":
            d = Path(args.run_dir)
            if manifest_schema(d) == "external-1":
                from .external import verify, load_adapter, check_capture
                manifest = verify(d)
                require(manifest["validity"] == "valid", "Invalid runs cannot produce trusted metrics")
                _, metrics = check_capture(d, load_adapter(d/"adapter.json"), load_json(d/"scenario.json"))
                dump(args.output, metrics)
                return 0
            manifest = verify_run(d)
            require(manifest["validity"] == "valid", "Invalid runs cannot produce trusted metrics")
            c = load(d/"scenario.json")
            e = read_jsonl(d/"events.jsonl")
            validate_lifecycles(e, c)
            dump(args.output, analyze(e, int(c["measurement"]["start_tick"]), int(c["measurement"]["end_tick"])))
        elif args.command == "import-rtl":
            c = load(args.scenario)
            events = normalize(read_pilot(args.trace), c, "imported-rtl", "rtl")
            validate_lifecycles(events, c, check_timing=False)
            write_jsonl(args.output, events)
        elif args.command == "compare":
            require(args.tolerance_tick >= 0, "Negative tolerance")
            from .storage import parse_json
            with Path(args.left).open(encoding="utf-8") as stream:
                first = parse_json(stream.readline())
            require(isinstance(first, dict), "Expected a canonical event object")
            if first.get("schema_version") == "transaction-1":
                from .transactions import compare, read_events
                result = compare(read_events(args.left), read_events(args.right), args.tolerance_tick)
            else:
                result = compare_events(read_jsonl(args.left), read_jsonl(args.right), args.tolerance_tick)
            dump(args.output, result)
            print(result["status"])
            return 0 if result["status"] == "pass" else 1
        elif args.command == "regress":
            require(all(math.isfinite(v) and v >= 0 for v in (args.absolute, args.relative)),
                    "Regression tolerances must be finite and nonnegative")
            def metric(path):
                d = Path(path)
                if manifest_schema(d) == "external-1":
                    from .external import verify
                    m = verify(d)
                    c = load_json(d/"scenario.json")
                else:
                    m = verify_run(d)
                    c = load(d/"scenario.json")
                require(succeeded(m), "Regression requires successful runs and any requested RTL gate")
                return c, load_json(d/"metrics.json")
            ca, a = metric(args.baseline)
            cb, b = metric(args.candidate)
            require(a.get("schema_version") == b.get("schema_version") and a.get("time_resolution_fs") == b.get("time_resolution_fs"),
                    "Regression metric schema/time resolution differs")
            for key in ("adapter", "clock", "parameters", "reset", "workload", "measurement", "seed"):
                require(ca.get(key) == cb.get(key), f"Regression experiment differs: {key}")
            results = []
            skipped = []
            for key in ("min", "max", "mean", "median", "p95", "p99"):
                if key in {"p95", "p99"} and min(a["latency_tick"]["count"], b["latency_tick"]["count"]) < 100:
                    skipped.append({"metric": "latency_"+key, "reason": "Fewer than 100 samples"})
                    continue
                old, new = a["latency_tick"][key], b["latency_tick"][key]
                require(old is not None and new is not None, "Insufficient latency population")
                limit = max(args.absolute, args.relative*abs(old))
                results.append({"metric": "latency_"+key, "baseline": old, "candidate": new,
                                "limit": limit, "passed": abs(new-old) <= limit})
            dump(args.output, {"status": "pass" if all(r["passed"] for r in results) else "fail", "metrics": results,
                               "skipped": skipped})
            return 0 if all(r["passed"] for r in results) else 1
        return 0
    except KeyboardInterrupt:
        print("ERROR: Interrupted; inspect retained run checkpoints and manifests", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
