#!/usr/bin/env python3
"""Split a Quarto chapter into a spine plus included subfiles, rme-style.

Usage: python3 scripts/split-qmd.py DIR/CHAPTER.qmd
Writes DIR/_subfiles/CHAPTER/_*.qmd and rewrites CHAPTER.qmd as a spine
whose include lines point there. The leading underscore keeps Quarto from
rendering the subfiles on their own. d-morrison/rme keeps one _subfiles/
tree at the project root instead; move the directory and adjust the include
prefix if a project wants that layout.

The spine keeps the front matter, headings, slide breaks, HTML comments and
blank lines. Every non-empty top-level fenced div becomes one subfile,
named after its id, or <section>-<class> when it has only a class
(::: {.note} or the bare ::: note), or <section>-div when it has neither.
An empty placeholder such as ::: {#refs} stays in the spine. Every other
run of top-level content becomes a _sec-<heading>.qmd.
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


def line_at(body, j, path, opened):
    # a scan that runs off the end means the block opened at line `opened` never closed
    if j >= len(body):
        sys.exit(f"{path}:{opened}: unclosed div, code fence or HTML comment")
    return body[j]


def split_blank_edges(chunk):
    """Return (leading blank lines, content, trailing blank lines)."""
    start = 0
    while start < len(chunk) and not chunk[start].strip():
        start += 1
    stop = len(chunk)
    while stop > start and not chunk[stop - 1].strip():
        stop -= 1
    return chunk[:start], chunk[start:stop], chunk[stop:]


def add_subfile(out, name, chunk):
    """Record chunk as a subfile named after name and include it from the spine."""
    _, chunk, _ = split_blank_edges(chunk)
    if not chunk:
        return
    n = out["used"].get(name, 0) + 1
    out["used"][name] = n
    fname = f"_{name}.qmd" if n == 1 else f"_{name}-{n}.qmd"
    assert fname not in out["files"], fname
    out["files"][fname] = "\n".join(chunk) + "\n"
    out["spine"].append(f"{{{{< include {out['rel']}/{fname} >}}}}")


def flush_prose(out, pending, section):
    """Move a run of top-level prose into a subfile, keeping its edge blanks in the spine."""
    lead, prose, trail = split_blank_edges(pending)
    out["spine"].extend(lead)
    if prose:
        add_subfile(out, f"sec-{section}", prose)
    out["spine"].extend(trail)


def div_end(body, i, path, opened):
    """Return the index of the line closing the div that opens at body[i]."""
    depth, j, fence = 0, i, None
    while True:
        l = line_at(body, j, path, opened)
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
                return j
        j += 1


def split(path):
    path = Path(path)
    lines = path.read_text().split("\n")
    # front matter
    assert lines[0] == "---", "expected front matter"
    end = lines.index("---", 1)
    body = lines[end + 1 :]

    subdir = path.parent / "_subfiles" / path.stem
    out = {"spine": lines[: end + 1], "files": {}, "used": {}, "rel": f"_subfiles/{path.stem}"}
    spine = out["spine"]
    section = "intro"
    pending = []  # a run of top-level prose

    i = 0
    while i < len(body):
        line = body[i]
        opened = i + end + 2
        if line.strip() == "" and not pending:
            spine.append(line)
            i += 1
            continue
        hm = HEADING.match(line)
        if hm or line.strip() in ("{{< slidebreak >}}",) or INCLUDE.match(line):
            flush_prose(out, pending, section)
            pending = []
            spine.append(line)
            if hm:
                section = slug(hm.group(2))
            i += 1
            continue
        if line.startswith("<!--"):
            flush_prose(out, pending, section)
            pending = []
            j = i
            while "-->" not in line_at(body, j, path, opened):
                j += 1
            spine.extend(body[i : j + 1])
            i = j + 1
            continue
        dm = DIV_OPEN.match(line)
        if dm:
            flush_prose(out, pending, section)
            pending = []
            j = div_end(body, i, path, opened)
            if j - i < 2:  # an empty placeholder such as ::: {#refs}
                spine.extend(body[i : j + 1])
            else:
                attrs = dm.group(2) if dm.group(2) is not None else "." + dm.group(4)
                add_subfile(out, div_name(attrs, section), body[i : j + 1])
            i = j + 1
            continue
        fm = FENCE.match(line)
        if fm:
            fence = fm.group(1)
            j = i + 1
            while not (line_at(body, j, path, opened).startswith(fence) and body[j].strip() == fence[0] * len(body[j].strip())):
                j += 1
            pending.extend(body[i : j + 1])
            i = j + 1
            continue
        pending.append(line)
        i += 1
    flush_prose(out, pending, section)

    files = out["files"]
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
