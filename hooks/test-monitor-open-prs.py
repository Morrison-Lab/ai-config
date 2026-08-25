#!/usr/bin/env python3
"""Tests for monitor-open-prs.py orphaned temporary-state-file sweeping."""
import importlib.util
import json
import os
import tempfile
import time
import unittest

MODULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor-open-prs.py")


def load_module():
    spec = importlib.util.spec_from_file_location("monitor_open_prs", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SweepOrphanTempFilesTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.directory = tempfile.mkdtemp(prefix="monitor-open-prs-test-")
        self.module.STATE_PATH = os.path.join(self.directory, "all-open-prs.json")

    def tearDown(self):
        for name in os.listdir(self.directory):
            os.unlink(os.path.join(self.directory, name))
        os.rmdir(self.directory)

    def write(self, name, age_seconds=0):
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("{}")
        if age_seconds:
            stamp = time.time() - age_seconds
            os.utime(path, (stamp, stamp))
        return path

    def names(self):
        return sorted(os.listdir(self.directory))

    def test_removes_temp_files_older_than_one_poll_interval(self):
        stale = self.write("all-open-prs.json.4242.tmp", age_seconds=self.module.POLL_SECONDS + 60)
        self.assertEqual(self.module.sweep_orphan_temp_files(), 1)
        self.assertFalse(os.path.exists(stale))

    def test_keeps_temp_files_young_enough_to_have_a_live_writer(self):
        fresh = self.write("all-open-prs.json.4243.tmp", age_seconds=1)
        self.assertEqual(self.module.sweep_orphan_temp_files(), 0)
        self.assertTrue(os.path.exists(fresh))

    def test_never_removes_own_pid_temp_file(self):
        own = self.write(f"all-open-prs.json.{os.getpid()}.tmp",
                         age_seconds=self.module.POLL_SECONDS * 10)
        self.assertEqual(self.module.sweep_orphan_temp_files(), 0)
        self.assertTrue(os.path.exists(own))

    def test_leaves_real_state_and_session_files_alone(self):
        self.write("all-open-prs.json", age_seconds=self.module.POLL_SECONDS * 10)
        self.write("deadbeef.json", age_seconds=self.module.POLL_SECONDS * 10)
        self.assertEqual(self.module.sweep_orphan_temp_files(), 0)
        self.assertEqual(self.names(), ["all-open-prs.json", "deadbeef.json"])

    def test_leaves_temp_files_without_an_integer_pid_alone(self):
        self.write("all-open-prs.json.notapid.tmp", age_seconds=self.module.POLL_SECONDS * 10)
        self.write("unrelated.tmp", age_seconds=self.module.POLL_SECONDS * 10)
        self.assertEqual(self.module.sweep_orphan_temp_files(), 0)
        self.assertEqual(self.names(), ["all-open-prs.json.notapid.tmp", "unrelated.tmp"])

    def test_removes_only_the_stale_subset(self):
        self.write("all-open-prs.json.1.tmp", age_seconds=self.module.POLL_SECONDS * 3)
        self.write("all-open-prs.json.2.tmp", age_seconds=self.module.POLL_SECONDS * 3)
        self.write("all-open-prs.json.3.tmp", age_seconds=2)
        self.assertEqual(self.module.sweep_orphan_temp_files(), 2)
        self.assertEqual(self.names(), ["all-open-prs.json.3.tmp"])

    def test_tolerates_a_missing_state_directory(self):
        for name in os.listdir(self.directory):
            os.unlink(os.path.join(self.directory, name))
        os.rmdir(self.directory)
        self.assertEqual(self.module.sweep_orphan_temp_files(), 0)
        os.makedirs(self.directory, exist_ok=True)

    def test_write_state_leaves_no_temp_file_behind(self):
        self.module.write_state({"kind": "all_open_prs", "pid": os.getpid()})
        self.assertEqual(self.names(), ["all-open-prs.json"])
        with open(self.module.STATE_PATH, encoding="utf-8") as stream:
            self.assertEqual(json.load(stream)["kind"], "all_open_prs")

    def test_poll_once_sweeps_after_a_failed_poll(self):
        def failing_open_prs():
            raise OSError("gh unavailable")

        self.module.open_prs = failing_open_prs
        stale = self.write("all-open-prs.json.9999.tmp", age_seconds=self.module.POLL_SECONDS + 60)
        state = self.module.poll_once({})
        self.assertEqual(state["error"], "gh unavailable")
        self.assertFalse(os.path.exists(stale))
        self.assertEqual(self.names(), ["all-open-prs.json"])

    def test_poll_once_sweeps_after_a_successful_poll(self):
        self.module.open_prs = lambda: [{"number": 1}]
        stale = self.write("all-open-prs.json.9998.tmp", age_seconds=self.module.POLL_SECONDS + 60)
        state = self.module.poll_once({})
        self.assertEqual(state["data"], [{"number": 1}])
        self.assertFalse(os.path.exists(stale))


if __name__ == "__main__":
    unittest.main()
