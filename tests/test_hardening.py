"""Failure injection and public input contracts; no simulator installation needed."""
import contextlib
import copy
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tlm_lab.cli import generated, main
from tlm_lab.config import MAX_TICK, load, validate
from tlm_lab.events import compare_events, normalize, read_jsonl, validate_lifecycles, write_jsonl
from tlm_lab.runner import ROOT, check_responses, digest, git, process, run, stop_process_tree, verify_run
from tlm_lab.storage import dump, load_json, parse_json


def scenario():
    return load(ROOT/"configs"/"wdt_scenario.example.json")


class TemporaryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(list(map(str, args)))


class Storage(TemporaryTest):
    def test_json_rejects_duplicate_keys_and_nonfinite_numbers(self):
        for text in ('{"a":1,"a":2}', '{"nested":{"a":1,"a":2}}', '[NaN]', '[Infinity]', '[-Infinity]', '[1e400]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_json(text)

    def test_atomic_output_preserves_existing_bytes(self):
        path = self.directory/"result.json"
        dump(path, {"first": True})
        original = path.read_bytes()
        with self.assertRaises(FileExistsError):
            dump(path, {"second": True})
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_write_failures_leave_no_final_or_temporary_artifact(self):
        path = self.directory/"result.json"
        with self.assertRaises(ValueError):
            dump(path, {"invalid": float("nan")})
        with patch("tlm_lab.storage.os.link", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                dump(path, {"valid": True})
        def broken_stream():
            yield {"first": True}
            raise ValueError("partial stream")
        with self.assertRaisesRegex(ValueError, "partial stream"):
            write_jsonl(self.directory/"events.jsonl", broken_stream())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_publication_race_never_overwrites_winner(self):
        path = self.directory/"result.json"
        link = os.link
        def competing_writer(source, target):
            Path(target).write_text("winner", encoding="utf-8")
            link(source, target)
        with patch("tlm_lab.storage.os.link", side_effect=competing_writer):
            with self.assertRaises(FileExistsError):
                dump(path, {"loser": True})
        self.assertEqual(path.read_text(), "winner")
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_manifest_rejects_empty_hashes_and_nonlocal_paths(self):
        for index, hashes in enumerate(({}, {"../outside": "x"}, {"..\\outside": "x"}, {"file:stream": "x"})):
            directory = self.directory/str(index)
            directory.mkdir()
            dump(directory/"manifest.json", {"schema_version": "1", "artifacts_sha256": hashes})
            with self.subTest(hashes=hashes), self.assertRaises(ValueError):
                verify_run(directory)

    def test_valid_manifest_requires_hashes_for_consumed_evidence(self):
        dump(self.directory/"unrelated.json", {})
        dump(self.directory/"manifest.json", {"schema_version": "1", "validity": "valid",
                                             "trace": {"mode": "full"},
                                             "artifacts_sha256": {"unrelated.json": digest(self.directory/"unrelated.json")}})
        with self.assertRaisesRegex(ValueError, "Missing required evidence hashes"):
            verify_run(self.directory)


class FailureLifecycle(TemporaryTest):
    def test_missing_executable_retains_failed_attempt(self):
        directory, manifest = run(scenario(), self.directory/"missing.exe", self.directory)
        self.assertEqual(manifest["validity"], "invalid_run")
        self.assertEqual(manifest["termination"], "preparation_failure")
        self.assertEqual(manifest["stage"], "preparing")
        self.assertTrue((directory/"report.html").exists())
        self.assertEqual(verify_run(directory), manifest)

    def test_checkpoint_precedes_copy_failure(self):
        def cannot_copy(source, target):
            self.assertTrue((target.parent/"started.json").exists())
            raise OSError("copy failed")
        with patch("tlm_lab.runner.shutil.copy2", side_effect=cannot_copy):
            directory, manifest = run(scenario(), self.directory/"simulator.exe", self.directory)
        self.assertEqual(manifest["error"], "copy failed")
        verify_run(directory)

    def test_unlaunchable_executable_is_not_success(self):
        executable = self.directory/"broken.exe"
        executable.write_bytes(b"Not an executable")
        # Inject the loader error: executing a corrupt PE can open a modal Windows
        # error dialog under CTest's inherited error mode and hang the test host.
        with patch("tlm_lab.runner.provenance", return_value={}), \
                patch("tlm_lab.runner.subprocess.Popen", side_effect=OSError("Invalid executable format")):
            directory, manifest = run(scenario(), executable, self.directory)
        self.assertEqual(manifest["termination"], "launch_failure")
        self.assertIsNone(manifest["processes"][0]["exit_code"])
        self.assertIn("error", manifest["processes"][0])
        verify_run(directory)

    def test_launch_failure_has_process_record(self):
        records = []
        result = process([self.directory/"missing.exe"], self.directory, "missing", 1, records)
        self.assertEqual(records, [result])
        self.assertIsNone(result["exit_code"])
        self.assertIn("error", result)
        self.assertEqual(result["timeout_seconds"], 1)

    def test_interrupted_run_finalizes_before_propagating(self):
        executable = self.directory/"stub.exe"
        executable.write_bytes(b"unused")
        with patch("tlm_lab.runner.provenance", return_value={}), patch("tlm_lab.runner.process", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                run(scenario(), executable, self.directory)
        directory = next(self.directory.glob("wdt_expiry-*"))
        manifest = verify_run(directory)
        self.assertEqual(manifest["termination"], "interrupted")
        self.assertEqual(manifest["validity"], "invalid_run")

    def test_interrupted_process_is_reaped(self):
        original_wait = subprocess.Popen.wait
        for cleanup_error in (False, True):
            children, records = [], []
            def interrupt_once(child, *args, **kwargs):
                if not children:
                    children.append(child)
                    raise KeyboardInterrupt
                return original_wait(child, *args, **kwargs)
            def cleanup(child):
                stop_process_tree(child)
                if cleanup_error:
                    raise OSError("tree cleanup diagnostic")
            with self.subTest(cleanup_error=cleanup_error), patch.object(subprocess.Popen, "wait", interrupt_once), \
                    patch("tlm_lab.runner.stop_process_tree", side_effect=cleanup):
                with self.assertRaises(KeyboardInterrupt):
                    process([sys.executable, "-c", "import time; time.sleep(30)"],
                            self.directory, f"interrupt-{cleanup_error}", 5, records)
            self.assertIsNotNone(children[0].poll())
            self.assertTrue(records[0]["cancelled"])
            self.assertEqual("cleanup_error" in records[0], cleanup_error)

    def test_git_is_optional_for_source_exports(self):
        with patch("tlm_lab.runner.subprocess.run", side_effect=FileNotFoundError("no git")):
            self.assertIsNone(git("rev-parse", "HEAD"))
        with patch("tlm_lab.runner.ROOT", self.directory), patch("tlm_lab.runner.subprocess.run") as command:
            self.assertIsNone(git("rev-parse", "HEAD"))
            command.assert_not_called()

    def test_failed_profile_has_no_runtime_claim(self):
        source = self.directory/"scenario.json"
        dump(source, scenario())
        result = self.cli("profile", source, "--executable", self.directory/"missing.exe", "--output", self.directory)
        self.assertEqual(result, 1)
        profile = load_json(next(self.directory.glob("profile-*/profile.json")))
        self.assertFalse(profile["semantic_equivalence"])
        self.assertIsNone(profile["wall_ratio_on_over_off"])

    def test_failed_build_retains_command_record(self):
        def missing_tool(*args, **kwargs):
            raise FileNotFoundError("cmake unavailable")
        with patch("tlm_lab.runner.subprocess.Popen", side_effect=missing_tool):
            result = self.cli("build", "--systemc-prefix", self.directory, "--build-dir", self.directory)
        self.assertEqual(result, 2)
        records = load_json(next(self.directory.glob("configure-*/build.json")))
        self.assertEqual(len(records), 1)
        self.assertIn("error", records[0])

    def test_interrupted_build_retains_record_and_returns_130(self):
        def interrupted(command, directory, stem, timeout, records):
            records.append({"command": list(map(str, command)), "cancelled": True})
            raise KeyboardInterrupt
        with patch("tlm_lab.cli.process", side_effect=interrupted):
            result = self.cli("build", "--systemc-prefix", self.directory, "--build-dir", self.directory)
        self.assertEqual(result, 130)
        records = load_json(next(self.directory.glob("configure-*/build.json")))
        self.assertTrue(records[0]["cancelled"])

    def test_trace_off_requires_complete_native_metadata(self):
        executable = self.directory/"stub.exe"
        executable.write_bytes(b"unused")
        c = scenario()
        c["trace"]["mode"] = "off"
        c.pop("expectations")
        for invalid in ({"event_count": True}, {"resolution_ns": True}, {"event_digest": None}):
            def simulator(command, directory, stem, timeout, records):
                metadata = {"systemc_version": "2.3.4", "resolution_ns": 1,
                            "event_count": 10, "event_digest": "123", "finished": True, **invalid}
                dump(directory/"native.json", metadata)
                result = {"exit_code": 0, "timed_out": False, "wall_seconds": 1}
                records.append(result)
                return result
            with self.subTest(invalid=invalid), patch("tlm_lab.runner.provenance", return_value={}), \
                    patch("tlm_lab.runner.process", side_effect=simulator):
                directory, manifest = run(c, executable, self.directory)
            self.assertEqual(manifest["termination"], "evidence_failure")
            verify_run(directory)

    def test_replay_rejects_response_change_despite_matching_digest(self):
        original, replay = self.directory/"original", self.directory/"reproduced"
        original.mkdir()
        replay.mkdir()
        dump(original/"scenario.json", scenario())
        (original/"responses.csv").write_text("original")
        (replay/"responses.csv").write_text("different")
        manifest = {"validity": "valid", "requested_rtl": False,
                    "native": {"event_digest": "123", "event_count": 10},
                    "correlation": "uncorrelated", "termination": "normal_drain"}
        dump(original/"manifest.json", manifest)
        def rerun(c, executable, output, *args):
            output.mkdir(parents=True)
            return replay, copy.deepcopy(manifest)
        with patch("tlm_lab.cli.verify_run", return_value=manifest), patch("tlm_lab.cli.run", side_effect=rerun):
            self.assertEqual(self.cli("replay", original, "--output", self.directory), 1)
        result = load_json(next(self.directory.glob("replay-*/replay.json")))
        self.assertFalse(result["semantic_digest_matches"])


class InputContracts(TemporaryTest):
    def test_numeric_string_seed_matches_integer_and_late_clock_works(self):
        self.assertEqual(generated("41", "5"), generated(41, 5))
        c = scenario()
        c["clock"]["first_rising_tick"] = 10000
        c["reset"][1]["tick"] = 10001
        result = generated(41, 5, c)
        self.assertGreater(int(result["measurement"]["end_tick"]), 10001)
        validate(result)

    def test_invalid_enum_containers_and_completion_overflow(self):
        mutations = [lambda c: c["trace"].update(mode=[]),
                     lambda c: c["workload"][0].update(op={}),
                     lambda c: c["expectations"][0].update(event=[])]
        for change in mutations:
            c = scenario()
            change(c)
            with self.assertRaises(ValueError):
                validate(c)
        c = scenario()
        c["workload"] = c["workload"][:1]
        c["parameters"]["bus_latency_tick"] = MAX_TICK-11
        with self.assertRaisesRegex(ValueError, "Completion timestamp overflow"):
            validate(c)

    def test_nonfinite_regression_tolerances_rejected_before_io(self):
        for flag in ("--absolute", "--relative"):
            for value in ("nan", "inf", "-inf"):
                with self.subTest(flag=flag, value=value):
                    result = self.cli("regress", "absent", "absent", f"{flag}={value}", "--output", self.directory/"result.json")
                    self.assertEqual(result, 2)
        self.assertFalse((self.directory/"result.json").exists())

    def test_duplicate_sweep_keys_rejected_before_launch(self):
        source = self.directory/"scenario.json"
        dump(source, scenario())
        matrix = self.directory/"matrix.json"
        matrix.write_text('{"parameters":{},"parameters":{}}')
        with patch("tlm_lab.cli.run") as launch:
            self.assertEqual(self.cli("sweep", source, "--matrix", matrix), 2)
        launch.assert_not_called()

    def test_canonical_events_reject_lossy_or_malformed_fields(self):
        event = normalize([{"tick": 10, "delta": 1, "sequence": 1, "event": "reset",
                            "transaction_id": 0, "address": 0, "value": 0}], scenario(), "fixture")[0]
        mutations = [lambda e: e.update(observed_tick=10.5), lambda e: e.update(sequence=True),
                     lambda e: e.update(value=str(2**32)), lambda e: e.update(delta="01"),
                     lambda e: e.update(attributes=[]), lambda e: e.pop("epoch"),
                     lambda e: e.update(transaction_id="unexpected"), lambda e: e.update(event=[])]
        for index, change in enumerate(mutations):
            malformed = copy.deepcopy(event)
            change(malformed)
            path = self.directory/f"bad{index}.jsonl"
            write_jsonl(path, [malformed])
            with self.subTest(index=index), self.assertRaises(ValueError):
                read_jsonl(path)
        valid = self.directory/"valid.jsonl"
        write_jsonl(valid, [event])
        self.assertEqual(read_jsonl(valid), [event])
        invalid = self.directory/"not-object.jsonl"
        write_jsonl(invalid, [None])
        self.assertEqual(self.cli("compare", invalid, valid, "--output", self.directory/"comparison.json"), 2)

    def test_same_tick_mismatch_order_is_deterministic(self):
        rows = [{"event": name, "scope": "wdt", "value": "1", "attributes": {}, "observed_tick": "10"}
                for name in ("reset_request", "irq", "expiry")]
        result = compare_events(rows, [])
        self.assertEqual([row["key"][1] for row in result["differences"]], ["expiry", "irq", "reset_request"])

    def test_response_time_validation_does_not_depend_on_trace(self):
        c = scenario()
        c["workload"] = c["workload"][:1]
        path = self.directory/"responses.csv"
        path.write_text("transaction_id,tick,status,value\n1,30,1,3\n")
        check_responses(path, c)
        for row in ("1,31,1,3", "1,30,1,4294967296", "1,30,1,3,extra", "1,30,1"):
            path.write_text("transaction_id,tick,status,value\n" + row + "\n")
            with self.subTest(row=row), self.assertRaises(ValueError):
                check_responses(path, c)

    def test_lifecycle_rejects_wrong_operation_or_clock_cycle(self):
        c = scenario()
        c["workload"] = c["workload"][:1]
        rows = [{"tick": tick, "delta": 1, "sequence": index, "event": name,
                 "transaction_id": 1, "address": 4, "value": 0}
                for index, (tick, name) in enumerate(((11, "submit"), (26, "peq_ready"), (30, "commit_write")), 1)]
        events = normalize(rows, c, "fixture")
        validate_lifecycles(events, c)
        for change in (lambda e: e.update(event="commit_read"), lambda e: e.update(cycle="99")):
            malformed = copy.deepcopy(events)
            change(malformed[-1])
            with self.assertRaises(ValueError):
                validate_lifecycles(malformed, c)


if __name__ == "__main__":
    unittest.main()
