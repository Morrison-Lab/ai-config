#!/usr/bin/env python3
"""Tests for hooks/no-truncated-bar-axis.py (ai-config#5614).

Run: python3 hooks/test-no-truncated-bar-axis.py [hooks/no-truncated-bar-axis.py]

The fixtures below are chart code as text, not charts, so this file exempts
itself from the hook it tests: axis-zero: allow test fixtures.
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "no-truncated-bar-axis.py")

MPL_BAR = "ax.bar(groups, coverage)\n"
# (description, code, denied)
CODE = [
    ("matplotlib bar, set_ylim(70, 80)", MPL_BAR + "ax.set_ylim(70, 80)\n", True),
    ("matplotlib bar, plt.ylim((88, 92))", "plt.bar(x, y)\nplt.ylim((88, 92))\n", True),
    ("matplotlib bar, set_ylim(bottom=50)", MPL_BAR + "ax.set_ylim(bottom=50)\n", True),
    ("matplotlib bar, set_ylim(top=95, bottom=60)", MPL_BAR + "ax.set_ylim(top=95, bottom=60)\n", True),
    ("matplotlib bar, set_ylim(0, 100)", MPL_BAR + "ax.set_ylim(0, 100)\n", False),
    ("matplotlib bar, computed limit", MPL_BAR + "ax.set_ylim(lo, hi)\n", False),
    ("matplotlib bar, no limit", MPL_BAR, False),
    ("matplotlib barh, set_xlim(40, 60)", "ax.barh(g, v)\nax.set_xlim(40, 60)\n", True),
    ("matplotlib barh, set_ylim on category axis", "ax.barh(g, v)\nax.set_ylim(0.5, 3.5)\n", False),
    ("matplotlib line plot, set_ylim(70, 80)", "ax.plot(x, y)\nax.set_ylim(70, 80)\n", False),
    ("ggplot geom_col + coord_cartesian(ylim = c(80, 95))",
     "ggplot(d, aes(g, v)) + geom_col() + coord_cartesian(ylim = c(80, 95))\n", True),
    ("ggplot geom_bar + scale_y_continuous(limits = c(50, NA))",
     "ggplot(d) + geom_bar(aes(g)) + scale_y_continuous(labels = scales::percent, limits = c(50, NA))\n",
     True),
    ("ggplot geom_col + ylim(0, 1)", "ggplot(d, aes(g, v)) + geom_col() + ylim(0, 1)\n", False),
    ("plotly go.Bar + update_yaxes(range=[85, 95])",
     "fig = go.Figure(go.Bar(x=g, y=v))\nfig.update_yaxes(range=[85, 95])\n", True),
    ("plotly px.bar + yaxis_range=[0, 100]",
     "fig = px.bar(d, x='g', y='v')\nfig.update_layout(yaxis_range=[0, 100])\n", False),
    ("python-pptx column chart, minimum_scale = 70",
     "chart = shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, cx, cy, data).chart\n"
     "chart.value_axis.minimum_scale = 70\n", True),
    ("python-pptx line chart, minimum_scale = 70",
     "chart = shapes.add_chart(XL_CHART_TYPE.LINE, x, y, cx, cy, data).chart\n"
     "chart.value_axis.minimum_scale = 70\n", False),
    ("allow comment", MPL_BAR + "ax.set_ylim(70, 80)  # axis-zero: allow index has no zero\n", False),
    ("matplotlib bar, set_ylim(.5, 1)", MPL_BAR + "ax.set_ylim(.5, 1)\n", True),
    ("bars on ax1, limit on a twinx line axes",
     "ax1.bar(g, v)\nax2 = ax1.twinx()\nax2.plot(g, r)\nax2.set_ylim(70, 80)\n", False),
    ("bars on ax1, limit on a separate line axes",
     "fig, (ax1, ax2) = plt.subplots(1, 2)\nax1.bar(g, v)\nax2.plot(x, y)\nax2.set_ylim(70, 80)\n", False),
    ("bars and a line chart in separate figures",
     "plt.figure()\nplt.bar(g, v)\nplt.figure()\nplt.plot(x, y)\nplt.ylim(70, 80)\n", False),
    ("matplotlib bar, ax.set(ylim=(70, 80))", MPL_BAR + "ax.set(ylim=(70, 80))\n", True),
    ("seaborn barplot, plt.ylim(70, 80)", "sns.barplot(data=d, x='g', y='v')\nplt.ylim(70, 80)\n", True),
    ("seaborn barplot on ax, ax.set_ylim(70, 80)",
     "sns.barplot(data=d, x='g', y='v', ax=ax)\nax.set_ylim(70, 80)\n", True),
    ("pandas kind='bar', ylim=(70, 80)", "df.plot(kind='bar', ylim=(70, 80))\n", True),
    ("pandas .plot.bar(), then ax.set_ylim(70, 80)",
     "ax = df.plot.bar(x='g', y='v')\nax.set_ylim(70, 80)\n", True),
    ("pandas kind='line', ylim=(70, 80)", "df.plot(kind='line', ylim=(70, 80))\n", False),
    ("base R barplot(ylim = c(70, 80))", "barplot(v, names.arg = g, ylim = c(70, 80))\n", True),
    ("base R barplot(ylim = c(0, 100))", "barplot(v, ylim = c(0, 100))\n", False),
    ("base R vertical bars, category xlim", "barplot(v, xlim = c(1, 5))\n", False),
    ("base R horizontal bars, xlim = c(70, 80)", "barplot(v, horiz = TRUE, xlim = c(70, 80))\n", True),
    ("base R horizontal bars, category ylim", "barplot(v, horiz = TRUE, ylim = c(1, 5))\n", False),
    ("pyplot bars and ylim after plt.subplots", "fig, ax = plt.subplots()\nplt.bar(g, v)\nplt.ylim(70, 80)\n", True),
    ("plotly horizontal bars, update_xaxes(range=[85, 95])",
     "fig = go.Figure(go.Bar(x=v, y=g, orientation='h'))\nfig.update_xaxes(range=[85, 95])\n", True),
    ("plotly bars, secondary y-axis range",
     "fig = make_subplots(specs=[[{'secondary_y': True}]])\nfig.add_trace(go.Bar(x=g, y=v))\n"
     "fig.update_yaxes(range=[85, 95], secondary_y=True)\n", False),
    ("altair mark_bar, scale zero=False",
     "alt.Chart(d).mark_bar().encode(x='g', y=alt.Y('v', scale=alt.Scale(zero=False)))\n", True),
    ("altair mark_bar, domain=[70, 80]",
     "alt.Chart(d).mark_bar().encode(x='g', y=alt.Y('v', scale=alt.Scale(domain=[70, 80])))\n", True),
    ("altair mark_line, zero=False",
     "alt.Chart(d).mark_line().encode(x='t', y=alt.Y('v', scale=alt.Scale(zero=False)))\n", False),
]


def run(tool, tool_input):
    p = subprocess.run([sys.executable, HOOK], capture_output=True, text=True,
                       input=json.dumps({"tool_name": tool, "tool_input": tool_input}))
    return p.returncode, '"permissionDecision": "deny"' in p.stdout


def main():
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for desc, code, want in CODE:
            path = os.path.join(tmp, "fig.py")
            results.append((f"Write: {desc}", run("Write", {"file_path": path, "content": code}), want))
        results.append(("Bash heredoc script",
                        run("Bash", {"command": "python3 - <<'EOF'\n" + MPL_BAR + "ax.set_ylim(70, 80)\nEOF"}),
                        True))
        results.append(("Write to a .md file is out of scope",
                        run("Write", {"file_path": os.path.join(tmp, "notes.md"),
                                      "content": MPL_BAR + "ax.set_ylim(70, 80)\n"}), False))
        # Edit is judged on the whole file after the edit: the bar call is
        # already in the file and the edit only adds the limit.
        path = os.path.join(tmp, "plot.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(MPL_BAR + "ax.set_ylim(0, 100)\n")
        results.append(("Edit adding a cut limit to an existing bar chart",
                        run("Edit", {"file_path": path, "old_string": "ax.set_ylim(0, 100)",
                                     "new_string": "ax.set_ylim(70, 80)"}), True))
        results.append(("Edit fixing the limit to zero",
                        run("Edit", {"file_path": path, "old_string": "ax.set_ylim(0, 100)",
                                     "new_string": "ax.set_ylim(0, 90)"}), False))
    p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
    results.append(("fails open on garbage stdin", (p.returncode, bool(p.stdout)), False))
    fails = 0
    for desc, (rc, denied), want in results:
        ok = rc == 0 and denied == want
        fails += 0 if ok else 1
        print(f"  {'ok' if ok else 'FAIL':<6} {'deny' if denied else 'allow':<6} {desc}")
    print(f"\n{len(results) - fails}/{len(results)} correct")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
