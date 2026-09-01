#!/usr/bin/env python3
"""Unit tests for upload_skills.sh change-detection, deletion propagation, and caching."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "upload_skills.sh"


class TestUploadSkills(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.td = Path(self.temp_dir.name)
        self.stage = self.td / "stage"
        self.stage.mkdir()
        self.bin_dir = self.td / "bin"
        self.bin_dir.mkdir()
        self.map_file = self.td / "skill_ids.tsv"
        self.state_file = self.td / "skill_state.json"
        self.curl_log = self.td / "curl_calls.jsonl"
        self.mock_responses = self.td / "mock_responses.json"

        # Set up mock curl executable
        mock_curl_script = self.bin_dir / "curl"
        mock_curl_content = f"""#!/usr/bin/env python3
import sys, os, json

log_file = {repr(str(self.curl_log))}
responses_file = {repr(str(self.mock_responses))}

config = {{}}
if os.path.exists(responses_file):
    with open(responses_file, "r") as f:
        config = json.load(f)

args = sys.argv[1:]
# Record call
with open(log_file, "a") as f:
    f.write(json.dumps({{"args": args}}) + "\\n")

# Determine method and url
method = "GET"
url = None
i = 0
while i < len(args):
    arg = args[i]
    if arg == "-X" and i + 1 < len(args):
        method = args[i+1]
        i += 2
        continue
    if arg.startswith("http://") or arg.startswith("https://"):
        url = arg
    i += 1

key = f"{{method}} {{url}}"
response = config.get(key, config.get("DEFAULT", {{"code": 200, "body": "{{\\"data\\":[]}}"}}))

# Write body
body = response.get("body", "")
code = response.get("code", 200)

if "-w" in args:
    # Print body + newline + status code
    sys.stdout.write(body + "\\n" + str(code))
else:
    sys.stdout.write(body)

sys.exit(response.get("exit_code", 0))
"""
        mock_curl_script.write_text(mock_curl_content)
        mock_curl_script.chmod(mock_curl_script.stat().st_mode | stat.S_IEXEC)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_upload(self, env_overrides=None, mock_config=None):
        if mock_config is not None:
            self.mock_responses.write_text(json.dumps(mock_config))
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["ANTHROPIC_API_KEY"] = "sk-ant-test-workspace-key"
        env["STAGE"] = str(self.stage)
        env["MAP"] = str(self.map_file)
        env["STATE"] = str(self.state_file)
        if env_overrides:
            env.update(env_overrides)

        res = subprocess.run(
            ["bash", str(SCRIPT_PATH)],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(self.td),
        )
        return res

    def get_curl_calls(self):
        if not self.curl_log.exists():
            return []
        calls = []
        with open(self.curl_log, "r") as f:
            for line in f:
                if line.strip():
                    calls.append(json.loads(line))
        return calls

    def test_new_skills_creation(self):
        (self.stage / "skill-alpha").mkdir()
        (self.stage / "skill-alpha" / "SKILL.md").write_text("# Alpha Skill\nContent")
        (self.stage / "skill-beta").mkdir()
        (self.stage / "skill-beta" / "SKILL.md").write_text("# Beta Skill\nContent")

        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"data": []}),
            },
            "POST https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"id": "skill_alpha_123", "latest_version_id": "ver_1"}),
            },
        }

        res = self.run_upload(mock_config=mock_config)
        self.assertEqual(res.returncode, 0, f"stderr: {res.stderr}")
        self.assertIn("created: skill-alpha -> skill_alpha_123", res.stdout)
        self.assertIn("created=2 versioned=0 unchanged=0 deleted=0 failed=0", res.stdout)

        map_content = self.map_file.read_text()
        self.assertIn("skill-alpha\tskill_alpha_123\tCREATED", map_content)
        self.assertIn("skill-beta\tskill_alpha_123\tCREATED", map_content)

        self.assertTrue(self.state_file.exists())
        state = json.loads(self.state_file.read_text())
        self.assertIn("skill-alpha", state["skills"])
        self.assertIn("skill-beta", state["skills"])
        self.assertEqual(state["skills"]["skill-alpha"]["id"], "skill_alpha_123")

    def test_unchanged_skill_skipped(self):
        (self.stage / "skill-alpha").mkdir()
        (self.stage / "skill-alpha" / "SKILL.md").write_text("# Alpha Skill\nContent")

        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"data": []}),
            },
            "POST https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"id": "skill_alpha_123", "latest_version_id": "ver_1"}),
            },
        }

        res1 = self.run_upload(mock_config=mock_config)
        self.assertEqual(res1.returncode, 0)
        self.assertIn("created=1", res1.stdout)

        self.curl_log.unlink()

        mock_config["GET https://api.anthropic.com/v1/skills"] = {
            "code": 200,
            "body": json.dumps({"data": [{"id": "skill_alpha_123", "display_name": "skill-alpha"}]}),
        }

        res2 = self.run_upload(mock_config=mock_config)
        self.assertEqual(res2.returncode, 0)
        self.assertIn("unchanged: skill-alpha -> skill_alpha_123 (cached)", res2.stdout)
        self.assertIn("created=0 versioned=0 unchanged=1 deleted=0 failed=0", res2.stdout)

        calls = self.get_curl_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn("https://api.anthropic.com/v1/skills", calls[0]["args"])

    def test_modified_skill_versioned(self):
        (self.stage / "skill-alpha").mkdir()
        skill_file = self.stage / "skill-alpha" / "SKILL.md"
        skill_file.write_text("# Alpha Skill\nInitial")

        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"data": []}),
            },
            "POST https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"id": "skill_alpha_123", "latest_version_id": "ver_1"}),
            },
        }
        self.run_upload(mock_config=mock_config)

        skill_file.write_text("# Alpha Skill\nModified content")

        mock_config["GET https://api.anthropic.com/v1/skills"] = {
            "code": 200,
            "body": json.dumps({"data": [{"id": "skill_alpha_123", "display_name": "skill-alpha"}]}),
        }
        mock_config["POST https://api.anthropic.com/v1/skills/skill_alpha_123/versions"] = {
            "code": 200,
            "body": json.dumps({"id": "ver_2"}),
        }

        res = self.run_upload(mock_config=mock_config)
        self.assertEqual(res.returncode, 0)
        self.assertIn("versioned: skill-alpha -> skill_alpha_123 (version ver_2)", res.stdout)
        self.assertIn("created=0 versioned=1 unchanged=0 deleted=0 failed=0", res.stdout)

        state = json.loads(self.state_file.read_text())
        self.assertEqual(state["skills"]["skill-alpha"]["version_id"], "ver_2")

    def test_force_upload(self):
        (self.stage / "skill-alpha").mkdir()
        (self.stage / "skill-alpha" / "SKILL.md").write_text("# Alpha Skill\nContent")

        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"data": [{"id": "skill_alpha_123", "display_name": "skill-alpha"}]}),
            },
            "POST https://api.anthropic.com/v1/skills/skill_alpha_123/versions": {
                "code": 200,
                "body": json.dumps({"id": "ver_2"}),
            },
        }
        self.state_file.write_text(json.dumps({
            "version": 1,
            "skills": {
                "skill-alpha": {
                    "id": "skill_alpha_123",
                    "hash": "dummy_hash",
                    "version_id": "ver_1",
                }
            }
        }))

        res = self.run_upload(env_overrides={"FORCE": "1"}, mock_config=mock_config)
        self.assertEqual(res.returncode, 0)
        self.assertIn("versioned: skill-alpha -> skill_alpha_123", res.stdout)

    def test_deletion_propagation_prunes_managed_only(self):
        self.state_file.write_text(json.dumps({
            "version": 1,
            "skills": {
                "skill-managed-1": {
                    "id": "sk_m1",
                    "hash": "hash_1",
                    "version_id": "ver_1",
                },
                "skill-managed-2": {
                    "id": "sk_m2",
                    "hash": "hash_2",
                    "version_id": "ver_1",
                }
            }
        }))

        (self.stage / "skill-managed-1").mkdir()
        (self.stage / "skill-managed-1" / "SKILL.md").write_text("# Skill 1")

        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({
                    "data": [
                        {"id": "sk_m1", "display_name": "skill-managed-1"},
                        {"id": "sk_m2", "display_name": "skill-managed-2"},
                        {"id": "sk_builtin", "display_name": "builtin-anthropic-skill"},
                    ]
                }),
            },
            "POST https://api.anthropic.com/v1/skills/sk_m1/versions": {
                "code": 200,
                "body": json.dumps({"id": "ver_m1_2"}),
            },
            "DELETE https://api.anthropic.com/v1/skills/sk_m2": {
                "code": 204,
                "body": "",
            },
        }

        res = self.run_upload(mock_config=mock_config)
        self.assertEqual(res.returncode, 0)
        self.assertIn("deleted: skill-managed-2 -> sk_m2", res.stdout)
        self.assertIn("deleted=1", res.stdout)

        map_content = self.map_file.read_text()
        self.assertIn("skill-managed-2\tsk_m2\tDELETED", map_content)

        state = json.loads(self.state_file.read_text())
        self.assertIn("skill-managed-1", state["skills"])
        self.assertNotIn("skill-managed-2", state["skills"])

        calls = self.get_curl_calls()
        delete_calls = [c for c in calls if "-X" in c["args"] and "DELETE" in c["args"]]
        self.assertEqual(len(delete_calls), 1)
        self.assertIn("https://api.anthropic.com/v1/skills/sk_m2", delete_calls[0]["args"])

    def test_prune_disabled(self):
        self.state_file.write_text(json.dumps({
            "version": 1,
            "skills": {
                "skill-managed-2": {
                    "id": "sk_m2",
                    "hash": "hash_2",
                }
            }
        }))
        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"data": [{"id": "sk_m2", "display_name": "skill-managed-2"}]}),
            },
        }

        res = self.run_upload(env_overrides={"PRUNE": "0"}, mock_config=mock_config)
        self.assertEqual(res.returncode, 0)
        self.assertIn("deleted=0", res.stdout)
        calls = self.get_curl_calls()
        delete_calls = [c for c in calls if "-X" in c["args"] and "DELETE" in c["args"]]
        self.assertEqual(len(delete_calls), 0)

    def test_multi_file_skill_upload(self):
        (self.stage / "quarto-authoring").mkdir()
        (self.stage / "quarto-authoring" / "SKILL.md").write_text("# Quarto")
        (self.stage / "quarto-authoring" / "references").mkdir()
        (self.stage / "quarto-authoring" / "references" / "figures.md").write_text("# Figures")

        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"data": []}),
            },
            "POST https://api.anthropic.com/v1/skills": {
                "code": 200,
                "body": json.dumps({"id": "sk_quarto", "latest_version_id": "ver_1"}),
            },
        }

        res = self.run_upload(mock_config=mock_config)
        self.assertEqual(res.returncode, 0)
        calls = self.get_curl_calls()
        create_call = [c for c in calls if "POST" in c["args"]][0]
        args_str = " ".join(create_call["args"])
        self.assertIn("filename=quarto-authoring/SKILL.md", args_str)
        self.assertIn("filename=quarto-authoring/references/figures.md", args_str)

    def test_auth_error_bails_out(self):
        (self.stage / "skill-alpha").mkdir()
        (self.stage / "skill-alpha" / "SKILL.md").write_text("# Alpha")

        mock_config = {
            "GET https://api.anthropic.com/v1/skills": {
                "code": 401,
                "body": json.dumps({"error": {"message": "Unauthorized"}}),
            },
        }

        res = self.run_upload(mock_config=mock_config)
        self.assertEqual(res.returncode, 1)
        self.assertIn("ERROR: Skills API auth failed", res.stderr)

    def test_missing_staging_dir(self):
        res = self.run_upload(env_overrides={"STAGE": "/nonexistent/stage/dir"})
        self.assertEqual(res.returncode, 1)
        self.assertIn("No staging dir", res.stderr)


if __name__ == "__main__":
    unittest.main()
