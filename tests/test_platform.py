import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

from tlm_lab.config import load, validate
from tlm_lab.events import compare_events, read_jsonl
from tlm_lab.metrics import analyze, distribution, occupancy, union_duration
from tlm_lab.runner import ROOT, run, verify_run, process
from tlm_lab.cli import generated, main


def base():
    return load(ROOT/"configs"/"wdt_scenario.example.json")


def fixture(kind, tick, tx=None, value=0):
    e = {"event": kind, "observed_tick": str(tick), "value": str(value), "scope": "wdt", "attributes": {}}
    if tx:
        e.update(transaction_id=tx, payload_bytes=4)
    return e


class Contracts(unittest.TestCase):
    def test_strict_config(self):
        for mutation in [lambda c: c.update(surprise=1), lambda c: c["parameters"].update(bus_latency_tick=-1),
                         lambda c: c["clock"].update(period_tick=True), lambda c: c["clock"].update(period_tick=11),
                         lambda c: c["workload"][1].update(after_completion_of="missing"),
                         lambda c: c["workload"][0].update(offer_tick=81),
                         lambda c: c["workload"][1].update(offer_tick=12),
                         lambda c: c["reset"][1].update(tick=10),
                         lambda c: c["workload"][0].update(value=2**32),
                         lambda c: c.update(schema_version="draft-1")]:
            c = base()
            mutation(c)
            with self.assertRaises(ValueError):
                validate(c)

    def test_seed_repeatability(self):
        self.assertEqual(generated(123), generated(123))
        self.assertNotEqual(generated(123), generated(124))

    def test_window_cohorts_and_censoring(self):
        e = [fixture("submit", 5, "a"), fixture("commit_read", 12, "a"),
             fixture("submit", 15, "b"), fixture("commit_write", 25, "b"),
             fixture("submit", 26, "c")]
        m = analyze(e, 10, 30)
        self.assertEqual(m["accounting"], {"admitted": 2, "completed": 1, "failed_cancelled": 0,
                                          "outstanding_censored": 1, "conserved": True})
        self.assertEqual(m["latency_tick"]["mean"], 10)
        self.assertEqual(m["completion_window"]["payload_bytes"], 8)
        self.assertAlmostEqual(m["inflight"]["average"], 16/20)
        # Admission exactly at end is excluded; completion exactly at end is excluded.
        m = analyze([fixture("submit", 10, "a"), fixture("commit_read", 20, "a"),
                     fixture("submit", 20, "b"), fixture("commit_read", 21, "b")], 10, 20)
        self.assertEqual(m["accounting"]["admitted"], 1)
        self.assertEqual(m["completion_window"]["transactions"], 0)
        self.assertEqual(m["accounting"]["completed"], 1)

    def test_union_occupancy_quantiles(self):
        self.assertEqual(union_duration([(0, 12), (11, 17), (15, 30)], 10, 20), 10)
        self.assertEqual(occupancy([(0, 2), (15, 0)], 10, 20, 4), {"average": 1, "peak": 2, "capacity": 4})
        self.assertEqual(distribution(list(range(1, 101)))["p99"], 99)
        self.assertIsNone(distribution([])["p95"])

    def test_negative_correlation(self):
        a = [fixture("expiry", 80), fixture("irq", 80, value=1)]
        b = copy.deepcopy(a)
        b[0]["observed_tick"] = "90"
        result = compare_events(a, b)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["first_mismatch"]["reason"], "timing")
        self.assertEqual(result["maximum_discrepancy_tick"], "10")
        self.assertEqual(compare_events(a, a[:-1])["status"], "fail")
        self.assertEqual(compare_events(a, a+a[:1])["status"], "fail")
        self.assertEqual(compare_events(a, list(reversed(a)))["status"], "fail")
        self.assertEqual(compare_events(a, b, 10)["status"], "pass")

    def test_process_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            result = process([sys.executable, "-c", "import time; time.sleep(30)"], Path(temp), "timeout", .05)
            self.assertTrue(result["timed_out"])
            self.assertNotEqual(result["exit_code"], 0)


EXE = Path(os.environ.get("TLM_LAB_EXECUTABLE", ROOT/"build-234"/("wdt_scenario.exe" if os.name == "nt" else "wdt_scenario")))


@unittest.skipUnless(EXE.exists(), "Build wdt_scenario first")
class Integration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def execute(self, c, rtl=True):
        d, m = run(c, EXE, self.temp.name, rtl=rtl)
        self.assertEqual(m["validity"], "valid", m)
        if rtl:
            self.assertEqual(m["correlation"], "pass", m)
        self.assertTrue((d/"report.html").exists())
        verify_run(d)
        return d, m

    def scenario(self, extra=(), load_value=3, ctrl=7):
        c = base()
        c.pop("expectations", None)
        c["workload"] = [
            {"id": "load", "op": "write32", "offer_tick": 11, "address": 4, "value": load_value},
            {"id": "enable", "op": "write32", "after_completion_of": "load", "address": 0, "value": ctrl}]
        for op in extra:
            op = dict(op)
            op.setdefault("id", f"x{len(c['workload'])}")
            if "offer_tick" not in op:
                op.setdefault("after_completion_of", c["workload"][-1]["id"])
            c["workload"].append(op)
        c["measurement"] = {"start_tick": 11, "end_tick": 301, "drain_deadline_tick": 320}
        return c

    def expiry(self, c, ticks):
        c["expectations"] = [{"event": "expiry", "ticks": ticks}]
        return self.execute(c)

    def test_documented_example_and_repeat(self):
        a, ma = self.execute(base())
        b, mb = self.execute(base())
        self.assertEqual((a/"raw.csv").read_bytes(), (b/"raw.csv").read_bytes())
        self.assertEqual(ma["native"]["event_digest"], mb["native"]["event_digest"])
        self.assertEqual(main(["replay", str(a), "--output", self.temp.name]), 0)
        self.assertEqual(main(["regress", str(a), str(b), "--output", str(Path(self.temp.name)/"regress.json")]), 0)
        self.assertEqual(main(["analyze", str(a), "--output", str(Path(self.temp.name)/"analysis.json")]), 0)
        (a/"responses.csv").write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "Artifact changed"):
            verify_run(a)

    def test_load_one_and_max(self):
        self.expiry(self.scenario(load_value=1), [60])
        self.expiry(self.scenario([{"op": "read32", "address": 8, "expect_value": 2**32-2}], load_value=2**32-1), [])

    def test_boundary_kick_disable_w1c(self):
        for address, value, ticks in [(12, 0xA5A55A5A, [110]), (0, 6, []), (16, 1, [80])]:
            with self.subTest(address=address):
                self.expiry(self.scenario([{"op": "write32", "offer_tick": 60, "address": address, "value": value}]), ticks)

    def test_reset_pending_after_release_and_at_expiry(self):
        c = self.scenario()
        c["workload"] = [{"id": "pending", "op": "write32", "offer_tick": 11, "address": 4,
                           "value": 9, "expect_status": -1},
                          {"id": "read", "op": "read32", "after_completion_of": "pending", "address": 4, "expect_value": 4}]
        c["reset"] += [{"tick": 16, "reset_n": False}, {"tick": 21, "reset_n": True}]
        self.expiry(c, [])
        c = self.scenario()
        c["reset"] += [{"tick": 76, "reset_n": False}, {"tick": 81, "reset_n": True}]
        self.expiry(c, [])

    def test_live_load_and_repeated_enable(self):
        self.expiry(self.scenario([{"op": "write32", "address": 0, "value": 7}]), [80])
        self.expiry(self.scenario([{"op": "write32", "address": 4, "value": 5},
                                   {"op": "write32", "address": 12, "value": 0xA5A55A5A}]), [80, 140])

    def test_sticky_status_masks_and_disabled_kick(self):
        c = self.scenario([{"op": "write32", "offer_tick": 81, "address": 0, "value": 6},
                           {"op": "write32", "address": 12, "value": 0xA5A55A5A},
                           {"op": "read32", "address": 8, "expect_value": 0}], ctrl=1)
        c["expectations"] = [{"event": "expiry", "ticks": [80]},
                             {"event": "irq", "ticks": [100, 120], "values": [1, 0]}]
        self.execute(c)

    def test_invalid_access_matrix(self):
        c = self.scenario()
        variants = [(2, "read32", 0, -2, {}), (12, "read32", 0, -3, {}), (8, "write32", 1, -3, {}),
                    (4, "write32", 0, -1, {}), (0, "write32", 8, -1, {}), (16, "write32", 2, -1, {}),
                    (12, "write32", 7, -1, {}), (4, "ignore", 0, -3, {}),
                    (4, "read32", 0, -4, {"length": 2}), (4, "read32", 0, -4, {"streaming_width": 0}),
                    (4, "read32", 0, -5, {"byte_enable": True})]
        c["workload"] = []
        for i, (addr, kind, value, status, extra) in enumerate(variants):
            op = {"id": f"invalid{i}", "op": kind, "address": addr, "value": value, "expect_status": status, **extra}
            op.update({"after_completion_of": f"invalid{i-1}"} if i else {"offer_tick": 11})
            c["workload"].append(op)
        self.expiry(c, [])

    def test_phase_latency_annotation_matrix(self):
        for period, first, latency in [(10, 10, 0), (10, 10, 19), (14, 7, 4), (20, 20, 20)]:
            c = self.scenario()
            c["clock"].update(period_tick=period, first_rising_tick=first)
            release = first+1
            c["reset"][1]["tick"] = release
            c["workload"][0]["offer_tick"] = release
            c["workload"][0]["delay_tick"] = 7
            c["parameters"]["bus_latency_tick"] = latency
            with self.subTest(period=period, first=first, latency=latency):
                self.execute(c)

    def test_randomized_holdout(self):
        for seed in [3, 41, 999]:
            with self.subTest(seed=seed):
                self.execute(generated(seed, 50))

    def test_trace_off_and_limit(self):
        c = base()
        d, m = self.execute(c)
        c["trace"]["mode"] = "off"
        c.pop("expectations")
        d2, m2 = self.execute(c, rtl=False)
        self.assertEqual(m["native"]["event_digest"], m2["native"]["event_digest"])
        self.assertEqual((d/"responses.csv").read_bytes(), (d2/"responses.csv").read_bytes())
        self.assertFalse((d2/"raw.csv").exists())
        c["trace"] = {"mode": "full", "max_events": 2}
        _, m = run(c, EXE, self.temp.name)
        self.assertEqual(m["validity"], "invalid_run")

    def test_simulated_timeout_is_invalid(self):
        c = base()
        c.pop("expectations")
        c["workload"] = c["workload"][:1]
        c["workload"][0]["delay_tick"] = 1000
        _, m = run(c, EXE, self.temp.name)
        self.assertEqual(m["validity"], "invalid_run")
        self.assertEqual(m["termination"], "simulated_timeout")

    def test_missing_rtl_tool_is_inconclusive(self):
        _, m = run(base(), EXE, self.temp.name, rtl=True, iverilog="not-an-installed-tool")
        self.assertEqual(m["validity"], "valid")
        self.assertEqual(m["correlation"], "inconclusive")

    def test_valid_run_can_fail_accuracy(self):
        from tlm_lab.rtl import run_reference
        def corrupted(*args, **kwargs):
            events = run_reference(*args, **kwargs)
            for event in events:
                if event["event"] == "expiry":
                    event["observed_tick"] = str(int(event["observed_tick"])+10)
            return events
        with patch("tlm_lab.rtl.run_reference", side_effect=corrupted):
            d, m = run(base(), EXE, self.temp.name, rtl=True)
        self.assertEqual(m["validity"], "valid")
        self.assertEqual(m["correlation"], "fail")
        comparison = json.loads((d/"correlation.json").read_text())
        self.assertEqual(comparison["first_mismatch"]["reason"], "timing")

    def test_cli_sweep_profile_import_compare(self):
        scenario = Path(self.temp.name)/"input.json"
        scenario.write_text(json.dumps(base()))
        matrix = Path(self.temp.name)/"matrix.json"
        matrix.write_text(json.dumps({"parameters": {"parameters.bus_latency_tick": [0, 15]},
                                     "seeds": [7], "workload_generator": {"count": 10}}))
        common = [str(scenario), "--output", self.temp.name, "--executable", str(EXE)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["sweep", *common, "--matrix", str(matrix), "--jobs", "2", "--rtl"]), 0)
            self.assertEqual(main(["profile", *common, "--rtl"]), 0)
        d, _ = self.execute(base())
        imported = Path(self.temp.name)/"imported.jsonl"
        self.assertEqual(main(["import-rtl", str(d/"rtl.csv"), "--scenario", str(scenario), "--output", str(imported)]), 0)
        comparison = Path(self.temp.name)/"compare.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["compare", str(d/"events.jsonl"), str(imported), "--output", str(comparison)]), 0)


if __name__ == "__main__":
    unittest.main()
