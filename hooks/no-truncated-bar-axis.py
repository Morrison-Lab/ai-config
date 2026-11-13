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

* matplotlib, seaborn (`barplot`, `countplot`) and pandas (`.plot.bar(`,
  `kind='bar'`): a value-axis limit (`set_ylim(N`, `ylim(N`, `bottom=N`,
  `set(ylim=(N`, a `ylim=(N` argument, or the x forms for horizontal bars)
  on the same axes as the bars; a `twinx()` axes is never paired;
* ggplot2: `geom_col(` / `geom_bar(` with `ylim(N`, `ylim = c(N` or
  `limits = c(N` in `scale_y_continuous`;
* base R: `barplot(` with `ylim = c(N` or `xlim = c(N`;
* plotly: `go.Bar(` / `px.bar(` / `type='bar'` with a value-axis `range=[N`
  (the x axis when `orientation='h'`), skipping `secondary_y=True`;
* altair: `mark_bar(` with `alt.Scale(domain=[N` or `zero=False`;
* python-pptx: a COLUMN or BAR chart type with `minimum_scale = N`.

The text is split at each new figure (`plt.figure(`, `plt.subplots(`,
`go.Figure(`, `ggplot(`, `alt.Chart(`, `add_chart(`), so a limit on one
chart is not paired with bars drawn on another.

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
N = r"(\d*\.?\d+)"
NUM = r"\(?\s*" + N

# A new figure starts a new segment, so a limit on one chart is never paired
# with bars drawn on another.
SEGMENT = re.compile(
    r"(?=\b(?:plt|pyplot)\.(?:figure|subplots)\s*\(|\bgo\.Figure\s*\(|\bmake_subplots\s*\("
    r"|\bggplot\s*\(|\balt\.Chart\s*\(|\.add_chart\s*\()"
)

# matplotlib, seaborn and pandas: limits are paired with the axes the bars are on.
MPL_BAR = re.compile(r"(\w+)\.(bar|barh)\s*\(")
SNS_BAR = re.compile(r"(?:(\w+)\s*=\s*)?(?:sns|seaborn)\.(?:barplot|countplot)\s*\(([^\n]*)")
PANDAS_BAR = re.compile(
    r"(?:(\w+)\s*=\s*)?[\w\]\[\"'.]+\.plot(?:\.(bar|barh)\s*\(([^\n]*)"
    r"|\s*\(([^\n]*\bkind\s*=\s*['\"](bar|barh)['\"][^\n]*))"
)
TWIN = re.compile(r"(\w+)\s*=\s*[\w.]+\.twin[xy]\s*\(")
LIMIT_CALL = {
    "bar": re.compile(r"(\w+)\.(?:set_ylim|ylim)\s*\(\s*(?:bottom\s*=\s*)?" + NUM
                      + r"|(\w+)\.set_ylim\s*\([^)]*\bbottom\s*=\s*" + N
                      + r"|(\w+)\.set\s*\([^\n]*\bylim\s*=\s*[(\[]\s*" + N),
    "barh": re.compile(r"(\w+)\.(?:set_xlim|xlim)\s*\(\s*(?:left\s*=\s*)?" + NUM
                       + r"|(\w+)\.set_xlim\s*\([^)]*\bleft\s*=\s*" + N
                       + r"|(\w+)\.set\s*\([^\n]*\bxlim\s*=\s*[(\[]\s*" + N),
}
KW_LIMIT = {"bar": re.compile(r"\bylim\s*=\s*[(\[]\s*" + N),
            "barh": re.compile(r"\bxlim\s*=\s*[(\[]\s*" + N)}
PYPLOT = {"plt", "pyplot"}


def _cut(value):
    return value is not None and float(value) > 0


def _mpl(seg):
    """`(name, snippet)` for a matplotlib-family bar chart with a cut value axis, or None."""
    axes = {"bar": set(), "barh": set()}
    for m in MPL_BAR.finditer(seg):
        if m.group(1) not in ("sns", "seaborn", "plot"):
            axes[m.group(2)].add(m.group(1))
    for m in SNS_BAR.finditer(seg):
        kind = "barh" if re.search(r"\borient\s*=\s*['\"]h", m.group(2)) else "bar"
        ax = re.search(r"\bax\s*=\s*(\w+)", m.group(2))
        axes[kind] |= {name for name in (m.group(1), ax and ax.group(1)) if name} | PYPLOT
    for m in PANDAS_BAR.finditer(seg):
        kind = m.group(2) or m.group(5)
        args = m.group(3) or m.group(4) or ""
        ax = re.search(r"\bax\s*=\s*(\w+)", args)
        axes[kind] |= {name for name in (m.group(1), ax and ax.group(1)) if name} | PYPLOT
        kw = KW_LIMIT[kind].search(args)
        if kw and _cut(kw.group(1)):
            return "pandas bars", " ".join(kw.group(0).split())
    twins = set(TWIN.findall(seg))
    for kind, receivers in axes.items():
        if not receivers:
            continue
        for m in LIMIT_CALL[kind].finditer(seg):
            groups = m.groups()
            receiver = next(g for g in groups[0::2] if g is not None)
            value = next((g for g in groups[1::2] if g is not None), None)
            if receiver in twins:
                continue
            if receiver in receivers or (receiver in PYPLOT and not twins):
                if _cut(value):
                    label = "matplotlib horizontal bars" if kind == "barh" else "matplotlib bars"
                    return label, " ".join(m.group(0).split())[:80]
    return None


# Other tools: (name, bar-chart pattern, value-axis-limit pattern). A match
# whose number groups are all empty (altair `zero=False`) is a cut axis too.
PLOTLY_BAR = re.compile(r"\bgo\.Bar\s*\(|\bpx\.bar\s*\(|type\s*=\s*['\"]bar['\"]"
                        r"|['\"]type['\"]\s*:\s*['\"]bar['\"]")
PLOTLY_H = re.compile(r"\borientation\s*=\s*['\"]h['\"]|['\"]orientation['\"]\s*:\s*['\"]h['\"]")


def _plotly_limit(axis):
    return re.compile(
        r"(?:update_{a}axes\s*\(|{a}axis\s*=\s*dict\s*\(|['\"]?{a}axis['\"]?\s*[:=]\s*\{{)"
        r"[^)}}]*?\brange['\"]?\s*[=:]\s*\[\s*{n}|{a}axis_range\s*=\s*\[\s*{n}".format(a=axis, n=N),
        re.S)


RULES = [
    ("ggplot2 bars",
     re.compile(r"\bgeom_(?:col|bar)\s*\("),
     re.compile(r"\bylim\s*\(\s*" + N + r"|\bylim\s*=\s*c\(\s*" + N
                + r"|scale_y_continuous\s*\([^)]*?\blimits\s*=\s*c\(\s*" + N, re.S)),
    ("base R barplot",
     re.compile(r"(?<![.\w])barplot\s*\("),
     re.compile(r"\b[xy]lim\s*=\s*c\(\s*" + N)),
    ("altair bars",
     re.compile(r"\bmark_bar\s*\("),
     re.compile(r"alt\.Scale\s*\([^)]*?(?:\bdomain\s*=\s*[\[(]\s*" + N + r"|\bzero\s*=\s*False)")),
    ("python-pptx bar or column chart",
     re.compile(r"XL_CHART_TYPE\.(?:COLUMN|BAR)_"),
     re.compile(r"minimum_scale\s*=\s*" + N)),
]


def _plotly(seg):
    if not PLOTLY_BAR.search(seg):
        return None
    axis = "x" if PLOTLY_H.search(seg) else "y"
    for m in _plotly_limit(axis).finditer(seg):
        call_end = seg.find(")", m.end())
        call = seg[m.start(): call_end if call_end != -1 else len(seg)]
        if re.search(r"\bsecondary_y\s*=\s*True", call):
            continue
        value = next((g for g in m.groups() if g is not None), None)
        if _cut(value):
            return "plotly bars", " ".join(m.group(0).split())[:80]
    return None


def _rules(seg):
    for name, bar, limit in RULES:
        if not bar.search(seg):
            continue
        for m in limit.finditer(seg):
            values = [g for g in m.groups() if g is not None]
            if not values or _cut(values[0]):
                return name, " ".join(m.group(0).split())[:80]
    return None


def truncated(text):
    """The first bar chart whose value axis starts above zero, as `(name, snippet)`, or None."""
    if ALLOW.search(text):
        return None
    for seg in SEGMENT.split(text):
        hit = _mpl(seg) or _plotly(seg) or _rules(seg)
        if hit:
            return hit
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
