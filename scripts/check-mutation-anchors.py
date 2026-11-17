#!/usr/bin/env python3
"""Report stale mutation anchors in hooks/test-*.py tables named old/find/anchor/edits.

Most harnesses `sys.exit` at their first bad anchor, after the slow cases
(ai-config#5735, #5738); this reads those it recognises statically.  A table is any
literal (MUTATIONS, MUTANTS, ...) a `for` loop reads into old/find/anchor or an
`edits` list of (find, replace) or (LIBNAME, find, replace) for scripts/lib.
An anchor must occur once (once or more if the loop only tests `not in`).
A SKIP fails the run unless ALLOWED_SKIPS names its file.  Usage: [ROOT].
Exit 0 clean, 1 bad anchor, 2 unallowed skip, nothing examined, or control failed.
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
# Harnesses that mutate source outside a table; their anchors go unchecked here.
ALLOWED_SKIPS = {
    "hooks/test-flag-uncited-rebuttal.py": "one inline anchor, not a table",
    "hooks/test-warn-status-read-after-pipe.py": "anchors passed to load_mutant() calls",
}


class Skip(Exception):
    """A harness, or one clause of it, this reader cannot follow."""


def _passes_find(node, method=None):
    """True when `node` calls something (or `.method`) with an old/find/anchor name argument."""
    return any(isinstance(n, ast.Call) and (method is None or getattr(n.func, "attr", None) == method)
               and any(getattr(a, "id", None) in FIND for a in (n.args[:1] if method else n.args))
               for n in ast.walk(node))


def _table_loop(tree):
    """(entries, loop) for the first loop over a literal mutation table, else None."""
    assigned = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            assigned.setdefault(node.targets[0].id, []).append(node.value)
    for loop in (n for n in ast.walk(tree) if isinstance(n, ast.For)):
        table, items = loop.iter, getattr(getattr(loop.iter, "func", None), "attr", None) == "items"
        table = table.func.value if items else table
        values = assigned.get(getattr(table, "id", None), [])
        names = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
        if len(values) != 1 or not (names & FIND or "edits" in names) or not _passes_find(loop):
            continue
        if items and isinstance(values[0], ast.Dict):
            return [ast.Tuple(elts=[k, v]) for k, v in zip(values[0].keys, values[0].values)], loop
        if not items and isinstance(values[0], (ast.List, ast.Tuple)):
            return values[0].elts, loop
        raise Skip(f"table {table.id} is not a literal the loop can read")
    if _passes_find(tree, "replace"):
        raise Skip("mutation code outside a table this reads")
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
    if len(getattr(node, "elts", ())) != len(getattr(pattern, "elts", [None])):
        raise Skip("entry shape does not match the loop target")
    for sub_pattern, sub_node in zip(pattern.elts, node.elts):
        _bind(sub_pattern, sub_node, out)


def _edits(bound, consts):
    """[(target, find, replace)]; target None is the hook, replace None unknown."""
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
        literal = isinstance(parts[-1], ast.Constant) and isinstance(parts[-1].value, str)
        out.append((target, _string(parts[-2], consts), parts[-1].value if literal else None))
    return out


def check_file(test_path, root):
    """(clauses, anchors, bad, skipped, exact); raise Skip for the whole file."""
    with open(test_path, encoding="utf-8") as handle:
        try:
            tree = ast.parse(handle.read())
        except SyntaxError as exc:
            raise Skip(f"does not parse: {exc.msg}") from None
    found = _table_loop(tree)
    if found is None:
        return None  # not a mutation harness
    entries, loop = found
    stem = os.path.basename(test_path)[len("test-"):-len(".py")]
    hook = os.path.join(os.path.dirname(test_path), stem + ".py")
    if not os.path.isfile(hook):
        raise Skip(f"no subject hooks/{stem}.py")
    consts = _constants(tree)
    exact = _passes_find(loop, "count") or not any(
        isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.NotIn)
        and getattr(n.left, "id", None) in FIND for n in ast.walk(loop))
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
                path = hook if target is None else os.path.join(root, "scripts", "lib", target + ".py")
                if path not in sources:
                    sources[path] = ""  # a missing target file holds no anchor
                    with suppress(FileNotFoundError), open(path, encoding="utf-8") as handle:
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
    """Check `paths`, write the report to `out`; return (examined, bad, unallowed skips)."""
    examined = clauses = anchors = bad_total = 0
    skips = []  # (rel, where, reason)
    for path in paths:
        rel = os.path.relpath(path, root)
        try:
            result = check_file(path, root)
        except Skip as exc:
            skips.append((rel, "", str(exc)))
            continue
        if result is None:
            continue
        n_clauses, n_anchors, bad, skipped, exact = result
        examined, clauses, anchors = examined + 1, clauses + n_clauses, anchors + n_anchors
        bad_total += len(bad)
        need = "exactly 1" if exact else "1 or more"
        for label, target, count, find in bad:
            out.write(f"BAD  {rel}: clause {label}: {target} has {count}, need {need}: {find.strip()[:80]!r}\n")
        skips += [(rel, f" clause {label}:", reason) for label, reason in skipped]
    unallowed = 0
    for rel, where, reason in skips:
        allowed = rel.replace(os.sep, "/") in ALLOWED_SKIPS
        unallowed += not allowed
        out.write(f"SKIP {rel}:{where} {reason}{' (allowed)' if allowed else ''}\n")
    out.write(f"examined {examined} harness(es), {clauses} clause(s), {anchors} anchor(s); "
              f"{len(skips)} skip(s), {unallowed} not allowed; {bad_total} bad anchor(s)\n")
    return examined, bad_total, unallowed


def _harnesses(root):
    return sorted(glob.glob(os.path.join(root, "hooks", "test-*.py")))


def negative_control():
    """A harness with one good and one missing anchor must yield exactly 1 bad."""
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "hooks"))
        files = {"probe.py": "if alpha:\n", "test-probe.py": (
            "MUTATIONS = {'good': ('s', [('if alpha:', '')], set()),\n"
            "             'gone': ('s', [('if beta:', '')], set())}\n"
            "for clause, (statement, edits, flips) in MUTATIONS.items():\n"
            "    for find, replace in edits:\n        SOURCE.count(find)\n")}
        for name, text in files.items():
            with open(os.path.join(tmp, "hooks", name), "w", encoding="utf-8") as handle:
                handle.write(text)
        return run(_harnesses(tmp), tmp, io.StringIO()) == (1, 1, 0)


def main(argv):
    root = os.path.abspath(argv[0] if argv else ROOT)
    if not negative_control():
        print("negative control FAILED: a known-missing anchor was not reported", file=sys.stderr)
        return 2
    examined, bad, unallowed = run(_harnesses(root), root, sys.stdout)
    if not examined or unallowed:
        print("nothing examined" if not examined else f"{unallowed} skip(s) not in ALLOWED_SKIPS", file=sys.stderr)
    return 2 if not examined or unallowed else 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
