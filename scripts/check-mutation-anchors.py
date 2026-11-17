#!/usr/bin/env python3
"""Report every mutation anchor in hooks/test-*.py that no longer resolves.

A harness stops at its FIRST bad anchor, after its slow cases, so a refactor
surfaces them one red push at a time (ai-config#5735, #5738).  This reads
them all statically.  The `for ... in MUTATIONS[.items()]` loop names the
fields: an anchor is bound to old/find/anchor, or sits in an `edits` list of
(find, replace), or (TARGET, find, replace) for scripts/lib/<TARGET>.py.
Edits in a clause apply in order.  An anchor must occur once (once or more if
the loop tests it only with `not in`).  What this cannot follow is SKIPPED.
Usage: check-mutation-anchors.py [ROOT].  Exit 0 clean, 1 a bad anchor, 2 the
negative control failed or nothing was examined.
"""
import ast
import glob
import io
import os
import sys
import tempfile
from contextlib import suppress

FIND = {"old", "find", "anchor"}
LABEL = {"clause", "name", "mid", "label"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Skip(Exception):
    """A harness, or one clause of it, this reader cannot follow."""


def _loop_kind(node):
    if getattr(node, "id", None) == "MUTATIONS":
        return "list"
    func = getattr(node, "func", None)
    if getattr(func, "attr", None) == "items" and getattr(func.value, "id", None) == "MUTATIONS":
        return "items"
    return None


def _string(node, consts):
    """Evaluate a string built from literals, `+`, `chr(<int>)` and known names."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _string(node.left, consts) + _string(node.right, consts)
    if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "chr"
            and len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, int)
            and 0 <= node.args[0].value <= sys.maxunicode):
        return chr(node.args[0].value)
    raise Skip("anchor is not a string built from literals")


def _constants(tree):
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            with suppress(Skip):  # not a string; an anchor naming it is skipped
                out[node.targets[0].id] = _string(node.value, out)
    return out


def _bind(pattern, node, out):
    if isinstance(pattern, ast.Name):
        out[pattern.id] = node
        return
    if (not isinstance(pattern, (ast.Tuple, ast.List)) or not isinstance(node, (ast.Tuple, ast.List))
            or len(node.elts) != len(pattern.elts)):
        raise Skip("entry shape does not match the loop target")
    for sub_pattern, sub_node in zip(pattern.elts, node.elts):
        _bind(sub_pattern, sub_node, out)


def _edits(bound, consts):
    """[(target, find, replace)]; target None is the hook, replace None unknown."""
    def maybe(node):
        with suppress(Skip):
            return _string(node, consts)
        return None
    find = [n for n in bound if n in FIND]
    if find:  # one anchor per clause, so its replacement never matters
        return [(None, _string(bound[find[0]], consts), None)]
    edits = bound["edits"]
    if not isinstance(edits, (ast.List, ast.Tuple)):
        raise Skip("edits is not a literal list")
    out = []
    for edit in edits.elts:
        parts = getattr(edit, "elts", [])
        if len(parts) not in (2, 3):
            raise Skip("an edit is not a 2- or 3-tuple")
        target = _string(parts[0], consts) if len(parts) == 3 else None
        out.append((target, _string(parts[-2], consts), maybe(parts[-1])))
    return out


def check_file(test_path, root):
    """(clauses, anchors, bad, skipped, exact); raise Skip for the whole file."""
    with open(test_path, encoding="utf-8") as handle:
        try:
            tree = ast.parse(handle.read())
        except SyntaxError as exc:
            raise Skip(f"does not parse: {exc.msg}") from None
    tables = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
              and getattr(n.targets[0], "id", None) == "MUTATIONS"]
    loops = [n for n in ast.walk(tree)
             if isinstance(n, ast.For) and _loop_kind(n.iter)]
    if len(tables) != 1 or not loops:
        raise Skip(f"{len(tables)} MUTATIONS assignment(s), {len(loops)} loop(s); need 1 and 1+")
    table, loop = tables[0], loops[0]
    if _loop_kind(loop.iter) == "items" and isinstance(table, ast.Dict):
        entries = [ast.Tuple(elts=[k, v]) for k, v in zip(table.keys, table.values)]
    elif _loop_kind(loop.iter) == "list" and isinstance(table, (ast.List, ast.Tuple)):
        entries = table.elts
    else:
        raise Skip("MUTATIONS literal does not match how the loop reads it")
    names = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
    if not names & (FIND | {"edits"}):
        raise Skip("loop binds no anchor field (" + ", ".join(sorted(names)) + ")")
    stem = os.path.basename(test_path)[len("test-"):-len(".py")]
    hook = os.path.join(os.path.dirname(test_path), stem + ".py")
    if not os.path.isfile(hook):
        raise Skip(f"no subject hooks/{stem}.py")
    consts = _constants(tree)
    calls_count = any(getattr(getattr(n, "func", None), "attr", None) == "count"
                      for n in ast.walk(loop))
    not_in = any(isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.NotIn)
                 and getattr(n.left, "id", None) in FIND for n in ast.walk(loop))
    exact = calls_count or not not_in
    sources, bad, skipped, anchors = {}, [], [], 0
    for index, entry in enumerate(entries):
        bound, label = {}, f"#{index}"
        try:
            _bind(loop.target, entry, bound)
            label = next((node.value for name, node in bound.items()
                          if name in LABEL and isinstance(node, ast.Constant)
                          and isinstance(node.value, str)), label)
            current = {}
            for target, find, replace in _edits(bound, consts):
                path = hook
                if target is not None:
                    path = os.path.join(root, "scripts", "lib", target + ".py")
                    if not os.path.isfile(path):
                        raise Skip(f"edit target {target!r} is not scripts/lib/{target}.py")
                if path not in sources:
                    with open(path, encoding="utf-8") as handle:
                        sources[path] = handle.read()
                body = current.get(path, sources[path])
                anchors += 1
                count = body.count(find)
                if count == 0 or (exact and count != 1):
                    bad.append((label, os.path.relpath(path, root), count, find))
                elif replace is not None:
                    # A later anchor in this clause sees the mutated text.
                    current[path] = body.replace(find, replace, 1)
        except Skip as exc:
            skipped.append((label, str(exc)))
    return len(entries), anchors, bad, skipped, exact


def run(paths, root, out):
    """Check `paths` and write the report to `out`; return (examined, bad)."""
    examined = clauses = anchors = bad_total = 0
    skipped_files = []
    for path in paths:
        rel = os.path.relpath(path, root)
        try:
            n_clauses, n_anchors, bad, skipped, exact = check_file(path, root)
        except Skip as exc:
            skipped_files.append(f"SKIP {rel}: {exc}\n")
            continue
        examined, clauses, anchors = examined + 1, clauses + n_clauses, anchors + n_anchors
        bad_total += len(bad)
        need = "exactly 1" if exact else "1 or more"
        for label, target, count, find in bad:
            out.write(f"BAD  {rel}: clause {label}: {target} has {count}, need {need}: {find.strip()[:80]!r}\n")
        for label, reason in skipped:
            out.write(f"SKIP {rel}: clause {label}: {reason}\n")
    out.write("".join(skipped_files) + f"examined {examined} harness(es), {clauses} clause(s), "
              f"{anchors} anchor(s); skipped {len(skipped_files)} file(s); {bad_total} bad anchor(s)\n")
    return examined, bad_total


def _harnesses(root):
    for path in sorted(glob.glob(os.path.join(root, "hooks", "test-*.py"))):
        with open(path, encoding="utf-8") as handle:
            if "MUTATIONS" in handle.read():
                yield path


def negative_control():
    """A harness with one good and one missing anchor must yield exactly 1 bad."""
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "hooks"))
        files = {"probe.py": "if alpha:\n", "test-probe.py": (
            "MUTATIONS = {'good': ('s', [('if alpha:', '')], set()),\n"
            "             'gone': ('s', [('if beta:', '')], set())}\n"
            "for clause, (statement, edits, flips) in MUTATIONS.items():\n    pass\n")}
        for name, text in files.items():
            with open(os.path.join(tmp, "hooks", name), "w", encoding="utf-8") as handle:
                handle.write(text)
        return run(list(_harnesses(tmp)), tmp, io.StringIO()) == (1, 1)


def main(argv):
    root = os.path.abspath(argv[0] if argv else ROOT)
    if not negative_control():
        print("negative control FAILED: a known-missing anchor was not reported", file=sys.stderr)
        return 2
    examined, bad = run(list(_harnesses(root)), root, sys.stdout)
    if not examined:
        print("no mutation harness examined; nothing was checked", file=sys.stderr)
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
