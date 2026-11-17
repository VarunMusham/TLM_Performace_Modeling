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
from .config import load, validate, require, fields, integer
from .events import read_jsonl, read_pilot, normalize, validate_lifecycles, write_jsonl, compare_events
from .metrics import analyze
from .runner import run, dump, verify_run, ROOT, process
from .storage import load_json


def succeeded(m):
    return m["validity"] == "valid" and (not m.get("requested_rtl") or m["correlation"] == "pass")


def show(directory, m):
    print(json.dumps({"run": str(directory), "validity": m["validity"], "correlation": m["correlation"],
                      "termination": m["termination"], "error": m.get("error")}, indent=2))


def execute(args, c=None):
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
    base = load(args.scenario)
    spec = load_json(args.matrix)
    fields(spec, {"parameters", "seeds", "workload_generator"}, {"parameters"})
    generator = spec.get("workload_generator")
    if generator is not None:
        fields(generator, {"count"}, {"count"})
        count = integer(generator["count"], "generator count", 1, 100000)
    require(isinstance(spec["parameters"], dict), "Matrix parameters must be an object")
    allowed = {"parameters.bus_latency_tick", "clock.period_tick", "clock.first_rising_tick"}
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
        configs.append(validate(c))
    directory = Path(args.output).resolve()/f"sweep-{uuid.uuid4().hex[:12]}"
    directory.mkdir(parents=True, exist_ok=False)
    dump(directory/"matrix.json", spec)
    def task(c):
        try:
            d, m = run(c, args.executable, directory, args.timeout, args.rtl, args.allow_unqualified_systemc)
            return {"run": str(d), "validity": m["validity"], "correlation": m["correlation"], "passed": succeeded(m)}
        except (ValueError, OSError) as e:
            return {"name": c["name"], "passed": False, "error": str(e)}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(task, configs))
    dump(directory/"summary.json", results)
    print(json.dumps({"sweep": str(directory), "runs": len(results), "passed": sum(r["passed"] for r in results)}, indent=2))
    return 0 if all(r["passed"] for r in results) else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="Hybrid TLM performance lab (1 ns ticks)")
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="Configure and build against a SystemC installation")
    b.add_argument("--systemc-prefix", required=True)
    b.add_argument("--build-dir", default="build-234")
    b.add_argument("--compiler")
    b.add_argument("--allow-unqualified-systemc", action="store_true")
    v = sub.add_parser("validate", help="Validate strict scenario and adapter capability contract")
    v.add_argument("scenario")
    sub.add_parser("adapters", help="Show the registered adapter timing/capability contract")
    for name in ("run", "sweep", "profile"):
        r = sub.add_parser(name)
        r.add_argument("scenario")
        r.add_argument("--executable", default="build-234/wdt_scenario.exe" if sys.platform == "win32" else "build-234/wdt_scenario")
        r.add_argument("--output", default="runs")
        r.add_argument("--timeout", type=float, default=30)
        r.add_argument("--rtl", action="store_true")
        r.add_argument("--allow-unqualified-systemc", action="store_true")
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
    args = p.parse_args(argv)
    try:
        if args.command == "validate":
            load(args.scenario)
            print("VALID hybrid_wdt schema 1")
        elif args.command == "adapters":
            print((ROOT/"configs"/"adapter_contract.example.json").read_text())
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
            return 0 if succeeded(m) else 1
        elif args.command == "generate":
            require(1 <= args.count <= 100000, "count must be 1..100000")
            integer(args.seed, "seed", 0, 2**32-1)
            dump(args.output, generated(args.seed, args.count))
        elif args.command == "sweep":
            require(1 <= args.jobs <= 32 and args.max_runs > 0, "Invalid sweep limits")
            return batch(args)
        elif args.command == "profile":
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
            result = compare_events(read_jsonl(args.left), read_jsonl(args.right), args.tolerance_tick)
            dump(args.output, result)
            print(result["status"])
            return 0 if result["status"] == "pass" else 1
        elif args.command == "regress":
            require(all(math.isfinite(v) and v >= 0 for v in (args.absolute, args.relative)),
                    "Regression tolerances must be finite and nonnegative")
            def metric(path):
                d = Path(path)
                m = verify_run(d)
                require(succeeded(m), "Regression requires successful runs and any requested RTL gate")
                return load(d/"scenario.json"), load_json(d/"metrics.json")
            ca, a = metric(args.baseline)
            cb, b = metric(args.candidate)
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
