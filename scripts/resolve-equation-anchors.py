#!/usr/bin/env python3
"""Resolve the position-numbered equation anchors a Quarto/altdoc page emits.

Some of the lab's rendered documentation attaches a permalink to every
display equation with an inline script of this shape:

    document.querySelectorAll(".math.display").forEach(function (mathEl) {
      const labeledContainer = mathEl.closest("[id^='eq-']");
      const target = labeledContainer || mathEl.parentElement;
      let id = labeledContainer ? labeledContainer.id : target.id;
      if (!id) { counter++; id = "eq-anchor-" + counter; target.id = id; }
      ...
    });

Two consequences make a URL carrying `#eq-anchor-N` hard to act on.

The ids do not exist in the served HTML -- they are assigned at
DOMContentLoaded -- so fetching the page and searching for the anchor finds
nothing, and no link checker or archiver can resolve one.

And the counter advances only for equations that carry no `eq-*` label, so
the number is a position among the UNLABELED equations. Adding one such
equation anywhere earlier silently renumbers every later anchor: the link
still resolves, to a different equation.

This module replays that assignment against the served HTML so a cited
anchor can be mapped back to the equation it currently names.

The replay must MUTATE the parsed tree the way the script does, rather than
tracking which elements have been assigned in a side table. Two display
equations can share a parent, and the second one then finds the id the first
one wrote and consumes no number. A side table keyed on element identity
also risks being wrong for a subtler reason: lxml creates element proxies on
demand, so `id(element)` is recycled once a proxy is garbage collected, and
a dictionary keyed on it silently merges unrelated elements.

Usage:

    python3 scripts/resolve-equation-anchors.py <url-or-path> [--anchor N]
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request

USER_AGENT = "ai-config resolve-equation-anchors"


def _classes(element) -> list[str]:
    return (element.get("class") or "").split()


def _labeled_ancestor(element):
    """The nearest ancestor-or-self carrying an `eq-*` id, as `closest()`."""
    node = element
    while node is not None:
        node_id = node.get("id")
        if node_id and node_id.startswith("eq-"):
            return node
        node = node.getparent()
    return None


def resolve_anchors(html: str) -> list[dict]:
    """Return one record per display equation, in document order.

    Each record carries the `anchor` a reader would cite, whether it was
    `generated` by the counter or came from an author-written label, and the
    equation's `latex`.
    """
    from lxml import html as lxml_html

    root = lxml_html.fromstring(html)
    equations = [
        element
        for element in root.iter()
        if "math" in _classes(element) and "display" in _classes(element)
    ]

    resolved: list[dict] = []
    counter = 0
    for equation in equations:
        labeled = _labeled_ancestor(equation)
        target = labeled if labeled is not None else equation.getparent()
        if target is None:
            continue
        anchor = labeled.get("id") if labeled is not None else target.get("id")
        generated = not anchor
        if generated:
            counter += 1
            anchor = f"eq-anchor-{counter}"
            # Mutate, as the page's own script does: a sibling equation
            # sharing this parent must now find the id rather than consume
            # another number.
            target.set("id", anchor)
        latex = re.sub(r"\s+", " ", "".join(equation.itertext())).strip()
        resolved.append(
            {"anchor": anchor, "generated": generated, "latex": latex}
        )
    return resolved


def fetch(location: str) -> str:
    if re.match(r"^https?://", location):
        request = urllib.request.Request(
            location, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8", errors="replace")
    with open(location, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("location", help="URL or local path to rendered HTML")
    parser.add_argument(
        "--anchor",
        help="report only this anchor, e.g. eq-anchor-3 (or just 3)",
    )
    args = parser.parse_args(argv)

    resolved = resolve_anchors(fetch(args.location))
    if not resolved:
        # An empty result is a failure, not a clean pass: a page with no
        # display equations and a page this parser could not read are
        # indistinguishable from the caller's side.
        print("no display equations found", file=sys.stderr)
        return 2

    generated = sum(1 for record in resolved if record["generated"])
    wanted = args.anchor
    if wanted and wanted.isdigit():
        wanted = f"eq-anchor-{wanted}"

    for record in resolved:
        if wanted and record["anchor"] != wanted:
            continue
        kind = "auto" if record["generated"] else "labeled"
        print(f"{record['anchor']}\t{kind}\t{record['latex'][:160]}")

    print(
        f"\n{len(resolved)} display equation(s); {generated} auto-numbered, "
        f"{len(resolved) - generated} labeled.",
        file=sys.stderr,
    )
    if wanted and not any(r["anchor"] == wanted for r in resolved):
        print(f"{wanted} does not exist on this page", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
