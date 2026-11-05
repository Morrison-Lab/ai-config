#!/usr/bin/env python3
"""Tests for check-session-runtime.py (ai-config#879).

Each negative isolates one fail-closed step, so a test that passes vacuously
(the script printing OK on bad input) fails here.
"""
import importlib.util
import json
import os
import tempfile
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "csr", Path(__file__).parent / "check-session-runtime.py")
csr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(csr)

SID = "11111111-2222-3333-4444-555555555555"


def record(model, effort="high", requested=None, sidechain=False):
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "effort": effort,
        "requestedModel": requested if requested is not None else model,
        "message": {"role": "assistant", "model": model, "content": []},
    }


def write(projects, slug, records, sid=SID):
    folder = Path(projects) / slug
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{sid}.jsonl", "w", encoding="utf-8") as handle:
        for item in records:
            handle.write(json.dumps(item) + "\n")


def run(projects, *extra, sid=SID):
    args = ["--projects-dir", str(projects)] + (["--session-id", sid] if sid else []) + list(extra)
    return csr.main(args)


def check(label, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), label, "" if ok else f"(got {got}, want {want})")
    return ok


def main():
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "proj-a", [record("claude-opus-5", "high")])
        results.append(check("matching model and effort: ok", run(tmp), 0))
        results.append(check("expected model accepted from a list",
                             run(tmp, "--expect-model", "claude-sonnet-5,claude-opus-5"), 0))
        results.append(check("wrong model: mismatch (1)",
                             run(tmp, "--expect-model", "claude-sonnet-5"), 1))
        results.append(check("wrong effort: mismatch (1)",
                             run(tmp, "--expect-effort", "low"), 1))
        saved = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        try:
            results.append(check("no session id anywhere: stop (2)", run(tmp, sid=""), 2))
            os.environ["CLAUDE_CODE_SESSION_ID"] = SID
            results.append(check("the id falls back to $CLAUDE_CODE_SESSION_ID", run(tmp, sid=""), 0))
        finally:
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            if saved is not None:
                os.environ["CLAUDE_CODE_SESSION_ID"] = saved
        results.append(check("unknown session id: stop (2)", run(tmp, sid="nope"), 2))

    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "proj-a", [record("claude-opus-5")])
        write(tmp, "proj-b", [record("claude-sonnet-5")])
        results.append(check("same id in two projects: stop (2)", run(tmp), 2))

    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "p", [record("claude-opus-5", "high"), record("claude-sonnet-5", "low")])
        results.append(check("a mid-session switch reports the LATEST model",
                             run(tmp, "--expect-model", "claude-sonnet-5"), 0))
        results.append(check("the earlier model no longer matches",
                             run(tmp, "--expect-model", "claude-opus-5"), 1))

    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "p", [record("claude-opus-5", "high"), record("claude-haiku-5", "low", sidechain=True)])
        results.append(check("sidechain (subagent) records are ignored",
                             run(tmp, "--expect-model", "claude-opus-5"), 0))

    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "p", [record("claude-opus-5", "high", requested="claude-fable-5")])
        results.append(check("a reroute is a stop (2), even when the model matches",
                             run(tmp, "--expect-model", "claude-opus-5"), 2))

    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "p", [record("claude-opus-5", effort=None)])
        results.append(check("missing effort: stop (2), no default", run(tmp), 2))

    with tempfile.TemporaryDirectory() as tmp:
        write(tmp, "p", [{"type": "user", "message": {"role": "user", "content": "hi"}}])
        results.append(check("no assistant model at all: stop (2)", run(tmp), 2))

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "p"
        folder.mkdir()
        (folder / f"{SID}.jsonl").write_text(
            "not json\n" + json.dumps(record("claude-opus-5")) + "\n", encoding="utf-8")
        results.append(check("an unparseable line is skipped, not fatal", run(tmp), 0))

    passed = sum(results)
    print(f"{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
