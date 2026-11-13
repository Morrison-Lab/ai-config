#!/usr/bin/env python3
"""PreToolUse: deny a bar chart whose value axis does not start at zero.

ai-config#5614. On 2026-11-12 a session built matplotlib bar charts for a
.pptx talk with the y-axis starting well above zero, so a gap of about one
percentage point in vaccination coverage looked large. It noticed, and added
a speaker-note caution instead of fixing the axis.
`shared/writing/visuals-everywhere.md` already asked for zero "when it
matters", and the session read that guide as being about Quarto and R chunks.
A bar's length is the value it shows, so a bar chart's value axis must
start at zero in every tool and every output format; that case is decidable
from the code, so it is a deny rather than a reminder.

Fires on a Write, Edit or MultiEdit of a code file (.py, .R, .qmd, .Rmd,
.ipynb, .js, .ts and the like), judged on the file as it will be after the
edit, and on a Bash command (a heredoc script), when the text both draws a
bar chart and sets that chart's value axis to start above zero:

* matplotlib: `.bar(` with `set_ylim(N` / `ylim(N` / `bottom=N`, or `.barh(`
  with the x forms;
* ggplot2: `geom_col(` / `geom_bar(` with `ylim(N`, `ylim = c(N` or
  `limits = c(N` in `scale_y_continuous`;
* plotly: `go.Bar(` / `px.bar(` / `type='bar'` with a y-axis `range=[N`;
* python-pptx: a COLUMN or BAR chart type with `minimum_scale = N`.

N is a literal number above zero. A computed limit is not judged: the check
cannot evaluate it, and whether zero matters on a dot or line plot is a
judgment the prose rule covers.

`axis-zero: allow <reason>` anywhere in the text (a code comment) exempts
it, for the rare bar chart of a quantity with no meaningful zero.

Fails OPEN on any parse trouble.
"""
import json
import os
import re
import sys

CODE_EXT = {".py", ".r", ".qmd", ".rmd", ".ipynb", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".jl"}
ALLOW = re.compile(r"axis-zero:\s*allow\b", re.I)
NUM = r"\(?\s*(\d+(?:\.\d+)?)"

# (name, bar-chart pattern, value-axis-limit pattern)
RULES = [
    ("matplotlib vertical bars",
     re.compile(r"\.bar\s*\("),
     re.compile(r"(?:set_ylim|\bylim)\s*\(\s*(?:bottom\s*=\s*)?" + NUM + r"|set_ylim\s*\([^)]*\bbottom\s*=\s*(\d+(?:\.\d+)?)")),
    ("matplotlib horizontal bars",
     re.compile(r"\.barh\s*\("),
     re.compile(r"(?:set_xlim|\bxlim)\s*\(\s*(?:left\s*=\s*)?" + NUM + r"|set_xlim\s*\([^)]*\bleft\s*=\s*(\d+(?:\.\d+)?)")),
    ("ggplot2 bars",
     re.compile(r"\bgeom_(?:col|bar)\s*\("),
     re.compile(r"\bylim\s*\(\s*(\d+(?:\.\d+)?)|\bylim\s*=\s*c\(\s*(\d+(?:\.\d+)?)"
                r"|scale_y_continuous\s*\([^)]*?\blimits\s*=\s*c\(\s*(\d+(?:\.\d+)?)", re.S)),
    ("plotly bars",
     re.compile(r"\bgo\.Bar\s*\(|\bpx\.bar\s*\(|type\s*=\s*['\"]bar['\"]|['\"]type['\"]\s*:\s*['\"]bar['\"]"),
     re.compile(r"(?:update_yaxes|yaxis\s*=\s*dict|['\"]?yaxis['\"]?\s*[:=]\s*\{)[^)}]*?\brange['\"]?\s*[=:]\s*\[\s*(\d+(?:\.\d+)?)"
                r"|yaxis_range\s*=\s*\[\s*(\d+(?:\.\d+)?)", re.S)),
    ("python-pptx bar or column chart",
     re.compile(r"XL_CHART_TYPE\.(?:COLUMN|BAR)_"),
     re.compile(r"minimum_scale\s*=\s*(\d+(?:\.\d+)?)")),
]


def truncated(text):
    """The first rule whose bar chart has a value axis starting above zero, or None."""
    if ALLOW.search(text):
        return None
    for name, bar, limit in RULES:
        if not bar.search(text):
            continue
        for m in limit.finditer(text):
            value = next((g for g in m.groups() if g is not None), None)
            if value is not None and float(value) > 0:
                return name, " ".join(m.group(0).split())[:80]
    return None


def text_after_edit(tool, inp):
    """The text to judge for this tool call, or None when it is out of scope."""
    if tool == "Bash":
        return inp.get("command") if isinstance(inp.get("command"), str) else None
    path = inp.get("file_path") or inp.get("notebook_path") or ""
    if not isinstance(path, str) or os.path.splitext(path)[1].lower() not in CODE_EXT:
        return None
    if tool == "Write":
        return inp.get("content")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        text = ""
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    for edit in edits or []:
        if not isinstance(edit, dict):
            continue
        old, new = edit.get("old_string") or "", edit.get("new_string") or ""
        if old and old in text:
            text = (text.replace(old, new) if edit.get("replace_all")
                    else text.replace(old, new, 1))
        else:
            text += "\n" + new
    return text


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = payload.get("tool_name") or ""
    inp = payload.get("tool_input")
    if tool not in ("Bash", "Write", "Edit", "MultiEdit") or not isinstance(inp, dict):
        return 0
    try:
        text = text_after_edit(tool, inp)
        hit = truncated(text) if isinstance(text, str) else None
    except Exception as exc:
        print(f"no-truncated-bar-axis: {type(exc).__name__}: {exc}; not gating", file=sys.stderr)
        return 0
    if not hit:
        return 0
    name, snippet = hit
    reason = (
        f"[hook: no-truncated-bar-axis] This draws {name} with the value axis starting above "
        f"zero (`{snippet}`). A bar's length is its value, so a cut axis makes a small "
        "difference look large. Start the value axis at zero, in every tool and output format "
        "(slides, Word, matplotlib, plotly, Shiny), per shared/writing/visuals-everywhere.md. "
        "To show a small difference, plot the difference itself or use dots with intervals; "
        "never leave the cut axis and add a caution in a caption or speaker note. If the "
        "quantity has no meaningful zero, add a comment `axis-zero: allow <reason>`."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
