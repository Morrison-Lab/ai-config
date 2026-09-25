#!/usr/bin/env python3
"""Split a Quarto chapter into a spine plus included subfiles, rme-style.

Usage: python3 scripts/split-qmd.py DIR/CHAPTER.qmd
Writes DIR/_subfiles/CHAPTER/_*.qmd and rewrites CHAPTER.qmd as a spine
whose include lines point there. The leading underscore keeps Quarto from
rendering the subfiles on their own. d-morrison/rme keeps one _subfiles/
tree at the project root instead; move the directory and adjust the include
prefix if a project wants that layout.

The spine keeps the front matter, headings, slide breaks, HTML comments and
blank lines. Every non-empty top-level fenced div becomes one subfile
named after its id; an empty placeholder such as ::: {#refs} stays in the
spine. Every other run of top-level content becomes a _sec-<heading>.qmd.
An unclosed div, code fence or HTML comment stops the split with its line
number before anything is written.
Re-running on an already-split spine is a no-op (it only holds spine items
and include lines).
"""
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(#{1,6}) +(.*?)\s*(\{.*\})?\s*$")
DIV_OPEN = re.compile(r"^(:{3,})\s*\{([^}]*)\}\s*$|^(:{3,})\s*([\w-]+)\s*$")
DIV_CLOSE = re.compile(r"^:{3,}\s*$")
FENCE = re.compile(r"^(`{3,}|~{3,})")
INCLUDE = re.compile(r"^\{\{< include .* >\}\}$")


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"


def div_name(attrs, section):
    m = re.search(r"(?:^|\s)#([\w-]+)", attrs)
    if m:
        return m.group(1)
    m = re.search(r"(?:^|\s)\.([\w-]+)", attrs)
    return f"{section}-{m.group(1) if m else 'div'}"


def split(path):
    path = Path(path)
    lines = path.read_text().split("\n")
    # front matter
    assert lines[0] == "---", "expected front matter"
    end = lines.index("---", 1)
    spine = lines[: end + 1]
    body = lines[end + 1 :]

    subdir = path.parent / "_subfiles" / path.stem
    rel = f"_subfiles/{path.stem}"
    files = {}
    used = {}
    section = "intro"

    def emit(name, chunk):
        # strip leading/trailing blank lines
        while chunk and not chunk[0].strip():
            chunk = chunk[1:]
        while chunk and not chunk[-1].strip():
            chunk = chunk[:-1]
        if not chunk:
            return
        n = used.get(name, 0) + 1
        used[name] = n
        fname = f"_{name}.qmd" if n == 1 else f"_{name}-{n}.qmd"
        assert fname not in files, fname
        files[fname] = "\n".join(chunk) + "\n"
        spine.append(f"{{{{< include {rel}/{fname} >}}}}")

    i = 0

    def at(j):
        # a scan that runs off the end means the block opened at line i never closed
        if j >= len(body):
            sys.exit(f"{path}:{i + end + 2}: unclosed div, code fence or HTML comment")
        return body[j]
    pending = []  # a run of top-level prose

    def flush():
        nonlocal pending
        # keep leading/trailing blank lines in the spine, prose in a subfile
        lead = []
        while pending and not pending[0].strip():
            lead.append(pending.pop(0))
        trail = []
        while pending and not pending[-1].strip():
            trail.insert(0, pending.pop())
        spine.extend(lead)
        if pending:
            emit(f"sec-{section}", pending)
        spine.extend(trail)
        pending = []

    while i < len(body):
        line = body[i]
        if line.strip() == "" and not pending:
            spine.append(line)
            i += 1
            continue
        hm = HEADING.match(line)
        if hm or line.strip() in ("{{< slidebreak >}}",) or INCLUDE.match(line):
            flush()
            spine.append(line)
            if hm:
                section = slug(hm.group(2))
            i += 1
            continue
        if line.startswith("<!--"):
            flush()
            j = i
            while "-->" not in at(j):
                j += 1
            spine.extend(body[i : j + 1])
            i = j + 1
            continue
        dm = DIV_OPEN.match(line)
        if dm:
            flush()
            depth, j, fence = 0, i, None
            while True:
                l = at(j)
                if fence:
                    if l.startswith(fence) and l.strip() == fence[0] * len(l.strip()) and len(l.strip()) >= len(fence):
                        fence = None
                elif FENCE.match(l):
                    fence = FENCE.match(l).group(1)
                elif DIV_OPEN.match(l):
                    depth += 1
                elif DIV_CLOSE.match(l):
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j - i < 2:  # an empty placeholder such as ::: {#refs}
                spine.extend(body[i : j + 1])
            else:
                attrs = dm.group(2) if dm.group(2) is not None else "." + dm.group(4)
                emit(div_name(attrs, section), body[i : j + 1])
            i = j + 1
            continue
        fm = FENCE.match(line)
        if fm:
            fence = fm.group(1)
            j = i + 1
            while not (at(j).startswith(fence) and at(j).strip() == fence[0] * len(at(j).strip())):
                j += 1
            pending.extend(body[i : j + 1])
            i = j + 1
            continue
        pending.append(line)
        i += 1
    flush()

    subdir.mkdir(parents=True, exist_ok=True)
    for fname, text in files.items():
        target = subdir / fname
        if target.exists() and target.read_text() != text:
            sys.exit(f"refusing to overwrite {target}: it exists with other content")
    for fname, text in files.items():
        (subdir / fname).write_text(text)
    path.write_text("\n".join(spine))
    return files


if __name__ == "__main__":
    out = split(sys.argv[1])
    print(f"wrote {len(out)} subfiles")
