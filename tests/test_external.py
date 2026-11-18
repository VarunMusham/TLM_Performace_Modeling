"""Customer project, generic evidence, offline packaging and onboarding tests."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tlm_lab.cli import main
from tlm_lab import external, transactions
from tlm_lab.events import write_jsonl
from tlm_lab.pilot import doctor, initialize
from tlm_lab.runner import ROOT
from tlm_lab.setup import extract_source
from tlm_lab.storage import dump, load_json
from tools.package_pilot import package


def event(kind, tick, txid, size=4):
    return {"schema_version": "transaction-1", "run_id": "fixture", "sequence": "0", "observed_tick": str(tick),
            "time_resolution_fs": "1000000", "event": kind, "transaction_id": txid, "payload_bytes": size}


def ordered(*events):
    for index, row in enumerate(events, 1):
        row["sequence"] = str(index)
    return list(events)


class GenericMetrics(unittest.TestCase):
    def test_overlap_reordering_window_and_censoring(self):
        events = ordered(event("accept", 5, "warm"), event("accept", 12, "a"), event("complete", 15, "warm"),
                         event("accept", 16, "censored"), event("complete", 25, "a"))
        metrics = transactions.analyze(events, 10, 20, 30)
        self.assertEqual(metrics["accounting"], {"admitted": 2, "completed": 1, "failed_cancelled": 0,
                                                "outstanding_censored": 1, "conserved": True})
        self.assertEqual(metrics["latency_tick"]["mean"], 13)
        self.assertEqual(metrics["completion_window"]["known_payload_bytes"], 4)
        self.assertEqual(metrics["inflight"]["peak"], 2)
        self.assertAlmostEqual(metrics["inflight"]["average"], 1.7)
        self.assertFalse(metrics["offer_visibility_complete"])
        self.assertIsNone(metrics["offered"])

    def test_rejection_failure_unaccepted_offer_and_unknown_bytes(self):
        events = ordered(event("offer", 0, "rejected"), event("reject", 0, "rejected"),
                         event("offer", 1, "waiting"), event("offer", 2, "failed"), event("accept", 3, "failed"),
                         event("fail", 4, "failed"), event("offer", 5, "ok"), event("accept", 5, "ok"),
                         event("complete", 8, "ok", None))
        metrics = transactions.analyze(events, 0, 10, 10)
        self.assertEqual(metrics["offered"], 4)
        self.assertEqual(metrics["rejected_offer_cohort"], 1)
        self.assertEqual(metrics["unaccepted_offer_cohort"], 1)
        self.assertEqual(metrics["accounting"]["failed_cancelled"], 1)
        self.assertIsNone(metrics["completion_window"]["payload_bytes_per_second"])
        self.assertEqual(metrics["completion_window"]["transactions"], 1)

    def test_illegal_lifecycles_cannot_compare_as_success(self):
        cases = [ordered(event("complete", 2, "a")),
                 ordered(event("accept", 1, "a"), event("accept", 2, "a")),
                 ordered(event("accept", 1, "a"), event("offer", 2, "a")),
                 ordered(event("accept", 1, "a"), event("reject", 2, "a")),
                 ordered(event("accept", 1, "a"), event("complete", 2, "a"), event("cancel", 3, "a"))]
        for events in cases:
            with self.subTest(events=events), self.assertRaises(ValueError):
                transactions.compare(events, events)

    def test_independent_equal_tick_order_is_allowed_and_timing_error_fails(self):
        a = ordered(event("accept", 1, "a"), event("accept", 1, "b"), event("complete", 4, "a"), event("complete", 4, "b"))
        b = ordered(copy.deepcopy(a[1]), copy.deepcopy(a[0]), copy.deepcopy(a[3]), copy.deepcopy(a[2]))
        self.assertEqual(transactions.compare(a, b)["status"], "pass")
        b[-1]["observed_tick"] = "5"
        self.assertEqual(transactions.compare(a, b)["first_mismatch"]["reason"], "timing")
        self.assertEqual(transactions.compare(a, b, 1)["status"], "pass")

    def test_resolution_sequence_and_capture_stop_are_checked(self):
        base = ordered(event("accept", 0, "a"), event("complete", 5, "a"))
        for mutation in (lambda e: e[1].update(sequence="3"), lambda e: e[1].update(time_resolution_fs="1000"),
                         lambda e: e[1].update(payload_bytes=True), lambda e: e[1].update(observed_tick=5.5)):
            rows = copy.deepcopy(base)
            mutation(rows)
            with self.assertRaises(ValueError):
                transactions.analyze(rows, 0, 10, 10)
        with self.assertRaisesRegex(ValueError, "after capture stop"):
            transactions.analyze(base, 0, 2, 4)


class CustomerWorkflow(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = initialize(self.root/"customer space ü", "python")
        self.adapter_path = self.project/"adapter.json"
        self.scenario_path = self.project/"scenario.json"
        self.adapter = load_json(self.adapter_path)
        self.scenario = load_json(self.scenario_path)

    def update_adapter(self):
        self.adapter_path.write_text(json.dumps(self.adapter), encoding="utf-8")

    def run_project(self):
        return external.run(self.scenario, self.adapter_path, self.root/"runs")

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(list(map(str, args)))

    def test_python_only_demo_has_known_results_and_snapshots(self):
        directory, manifest = self.run_project()
        self.assertEqual(manifest["validity"], "valid", manifest)
        self.assertEqual(external.verify(directory), manifest)
        metrics = load_json(directory/"metrics.json")
        self.assertEqual(metrics["accounting"]["completed"], 4)
        self.assertEqual(metrics["latency_tick"]["mean"], 20)
        self.assertEqual(metrics["completion_window"]["known_payload_bytes"], 288)
        self.assertAlmostEqual(metrics["inflight"]["average"], .8)
        self.assertEqual(metrics["inflight"]["peak"], 2)
        self.assertAlmostEqual(metrics["admission_wait_tick"]["mean"], 6.25)
        self.assertTrue((directory/"source"/"model.py").is_file())
        self.assertTrue((directory/"sdk"/"cpp"/"tlm_trace.hpp").is_file())
        self.assertIn("Latency distribution", (directory/"report.html").read_text(encoding="utf-8"))

    def test_launcher_works_outside_checkout_with_spaces_and_unicode(self):
        result = subprocess.run([sys.executable, str(ROOT/"tlm-lab.py"), "run", str(self.scenario_path),
                                 "--adapter", str(self.adapter_path), "--output", str(self.root/"runs")],
                                cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)["validity"], "valid")

    def test_validation_never_executes_customer_commands(self):
        marker = self.project/"must-not-exist"
        self.adapter["build"] = [["{python}", "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", str(marker)]]
        self.update_adapter()
        self.assertEqual(self.cli("validate", self.scenario_path, "--adapter", self.adapter_path), 0)
        self.assertFalse(marker.exists())

    def test_arbitrary_adapter_identity_and_non_ns_resolution(self):
        self.adapter.update(adapter_id="customer_dma", model_kind="simulation", time_resolution_fs="1000")
        self.scenario["adapter"] = "customer_dma"
        self.update_adapter()
        directory, manifest = self.run_project()
        self.assertEqual(manifest["validity"], "valid", manifest)
        self.assertEqual(load_json(directory/"metrics.json")["time_resolution_fs"], "1000")

    def test_bad_parameters_and_reserved_paths_rejected_before_launch(self):
        for mutation in (lambda a: a.update(run="python tb.py"), lambda a: a.update(run=["{unknown}"]),
                         lambda a: a.update(trace={"file": "scenario.json"}), lambda a: a.update(sources=["../outside.py"]),
                         lambda a: a.update(completion_file="../outside.json")):
            original = copy.deepcopy(self.adapter)
            mutation(self.adapter)
            self.update_adapter()
            with self.assertRaises(ValueError):
                external.load_adapter(self.adapter_path)
            self.adapter = original
        self.update_adapter()
        for values in ({"lanes": 0}, {"lanes": True}, {"lanes": 65}, {"unknown": 1}):
            c = copy.deepcopy(self.scenario)
            c["parameters"] = values
            with self.assertRaises(ValueError):
                external.resolve_scenario(c, self.adapter)

    def test_missing_build_tool_retains_failed_attempt(self):
        self.adapter["build"] = [["nonexistent-customer-compiler"]]
        self.update_adapter()
        directory, manifest = self.run_project()
        self.assertEqual(manifest["termination"], "build_failure")
        self.assertEqual(manifest["validity"], "invalid_run")
        self.assertIn("error", manifest["processes"][0])
        self.assertTrue((directory/"report.html").exists())
        external.verify(directory)

    def test_missing_completion_is_invalid_even_after_exit_zero(self):
        self.adapter["run"] = ["{python}", "-c", "pass"]
        self.update_adapter()
        _, manifest = self.run_project()
        self.assertEqual(manifest["termination"], "evidence_failure")
        self.assertEqual(manifest["validity"], "invalid_run")

    def test_external_host_timeout_retains_failure_and_process(self):
        self.adapter["run"] = ["{python}", "-c", "import time; time.sleep(30)"]
        self.update_adapter()
        directory, manifest = external.run(self.scenario, self.adapter_path, self.root/"runs", timeout=.05)
        self.assertEqual(manifest["termination"], "wall_timeout")
        self.assertTrue(manifest["processes"][0]["timed_out"])
        external.verify(directory)

    def test_interrupted_external_run_is_retained(self):
        with patch("tlm_lab.external.process", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_project()
        directory = next((self.root/"runs").iterdir())
        manifest = external.verify(directory)
        self.assertEqual(manifest["termination"], "interrupted")
        self.assertEqual(manifest["validity"], "invalid_run")

    def test_build_cannot_silently_modify_retained_sources(self):
        self.adapter["build"] = [["{python}", "-c", "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_text(p.read_text()+'\\n# changed\\n')", "{source_dir}/model.py"]]
        self.update_adapter()
        _, manifest = self.run_project()
        self.assertEqual(manifest["termination"], "evidence_failure")
        self.assertIn("modified retained source", manifest["error"])

    def test_capture_loss_and_expectation_failure_are_invalid(self):
        self.scenario["expectations"]["completed"] = 99
        _, manifest = self.run_project()
        self.assertIn("Expectation failed", manifest["error"])
        self.scenario["expectations"]["completed"] = 4
        directory, _ = self.run_project()
        completion = load_json(directory/"completion.json")
        completion["loss_count"] = 1
        (directory/"completion.json").write_text(json.dumps(completion))
        with self.assertRaisesRegex(ValueError, "lost events"):
            external.check_capture(directory, self.adapter, self.scenario)
        with self.assertRaisesRegex(ValueError, "Artifact changed"):
            external.verify(directory)

    def test_replay_uses_retained_source_and_offline_analysis_matches(self):
        directory, _ = self.run_project()
        (self.project/"model.py").write_text("raise RuntimeError('changed original source')")
        self.assertEqual(self.cli("replay", directory, "--output", self.root/"replays"), 0)
        analysis = self.root/"analysis.json"
        self.assertEqual(self.cli("analyze", directory, "--output", analysis), 0)
        self.assertEqual(load_json(analysis), load_json(directory/"metrics.json"))
        self.assertEqual(self.cli("regress", directory, directory, "--output", self.root/"regression.json"), 0)

    def test_customer_sweep_prevalidation_and_all_attempt_summary(self):
        matrix = self.root/"matrix.json"
        dump(matrix, {"parameters": {"parameters.lanes": [1, 2, 4]}, "seeds": [1]})
        self.assertEqual(self.cli("sweep", self.scenario_path, "--adapter", self.adapter_path,
                                  "--matrix", matrix, "--jobs", "2", "--output", self.root/"sweeps"), 0)
        summary = load_json(next((self.root/"sweeps").glob("sweep-*/summary.json")))
        self.assertEqual(len(summary), 3)
        self.assertTrue(all(row["passed"] for row in summary))

    def test_existing_project_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            initialize(self.project)

    def test_malformed_run_manifests_get_cli_diagnostics(self):
        directory = self.root/"bad-run"
        directory.mkdir()
        dump(directory/"manifest.json", None)
        self.assertEqual(self.cli("replay", directory), 2)
        self.assertEqual(self.cli("analyze", directory, "--output", self.root/"analysis.json"), 2)
        self.assertEqual(self.cli("regress", directory, directory, "--output", self.root/"regress.json"), 2)

    def test_doctor_distinguishes_optional_and_required_dependencies(self):
        with patch("tlm_lab.pilot.shutil.which", return_value=None):
            self.assertTrue(doctor()["ready"])
            self.assertFalse(doctor(ROOT/"examples"/"external_cpp"/"adapter.json")["ready"])

    def test_csv_column_and_event_mapping(self):
        trace = self.root/"raw.csv"
        trace.write_text("seq,time,phase,id,bytes,extra\n1,0,begin,a,8,ignored\n2,10,end,a,8,ignored\n")
        self.adapter["trace"] = {"columns": {"sequence": "seq", "tick": "time", "event": "phase",
                                               "transaction_id": "id", "payload_bytes": "bytes"},
                                 "event_map": {"begin": "accept", "end": "complete"}}
        rows = transactions.import_csv(trace, self.adapter, "mapped")
        self.assertEqual(transactions.analyze(rows, 0, 20, 20)["latency_tick"]["mean"], 10)

    @unittest.skipUnless(shutil.which("cmake") and shutil.which("ninja") and shutil.which("g++"), "CMake/Ninja/GCC example tools unavailable")
    def test_real_cpp_source_and_testbench_build(self):
        project = initialize(self.root/"cpp-project", "cpp")
        directory, manifest = external.run(load_json(project/"scenario.json"), project/"adapter.json", self.root/"cpp-runs")
        self.assertEqual(manifest["validity"], "valid", manifest)
        self.assertEqual(len(manifest["processes"]), 3)
        self.assertEqual(load_json(directory/"metrics.json")["latency_tick"]["mean"], 10)
        external.verify(directory)


class Distribution(unittest.TestCase):
    def test_archive_traversal_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, name in enumerate(("../escape", "/absolute", "safe-link")):
                archive = root/f"bad-{index}.tar.gz"
                with tarfile.open(archive, "w:gz") as stream:
                    info = tarfile.TarInfo(name)
                    if name == "safe-link":
                        info.type = tarfile.SYMTYPE
                        info.linkname = "../outside"
                    stream.addfile(info)
                with self.assertRaises(ValueError):
                    extract_source(archive, root/"extracted")

    def test_customer_zip_excludes_local_work_and_runs_without_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = package(root/"pilot.zip")
            repeat = package(root/"pilot-repeat.zip")
            self.assertEqual(result["sha256"], repeat["sha256"])
            with zipfile.ZipFile(result["package"]) as archive:
                names = archive.namelist()
                self.assertIn("vendor/systemc/systemc-2.3.4.tar.gz", names)
                self.assertIn("PACKAGE-MANIFEST.json", names)
                manifest = json.loads(archive.read("PACKAGE-MANIFEST.json"))
                for name, expected in manifest["files_sha256"].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), expected, name)
                self.assertFalse(any(name.split("/")[0] in {"private", "runs", ".git", ".deps", "dist"} or name.startswith("build") for name in names))
                archive.extractall(root/"unpacked space")
            bundle = root/"unpacked space"
            result = subprocess.run([sys.executable, str(bundle/"tlm-lab.py"), "demo", "--output", str(root/"runs")],
                                    cwd=root, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)["validity"], "valid")


if __name__ == "__main__":
    unittest.main()
