#!/usr/bin/env python3
"""Scan a rendered Quarto/HTML page for failures the SOURCE cannot show.

A .qmd diff can be perfectly correct while the published page is broken: a
macro that never expanded, a citation key with no bib entry, a crossref that
resolved to nothing, a list that lost its blank line and rendered as a
paragraph. None of those is visible in the diff, and none makes CI red.

Relationship to `check-rendered-references.py`, which came first: that
script is the mature implementation for unresolved crossrefs and missing
citation keys in LOCAL artifacts, with fence stripping and footnote
handling, and the `check-rendered-refs` skill drives it. The two checks
here that overlap it are deliberately kept so that a single command covers
a URL, but for a local `_site/` tree prefer that script. The three checks
that are genuinely new are the broken list, the KaTeX error, and the
unexpanded macro in prose.

Usage:  check-rendered-page.py <url-or-file> [<url-or-file> ...]
Exit 0 when every target is clean, 1 when any check fires, 2 on a fetch error.
"""
import re, sys, html, subprocess
from html.parser import HTMLParser

def fetch(t):
    """Fetch a URL with curl, or read a local file.

    curl rather than urllib: this machine's Python has no CA bundle wired up,
    so urlopen dies with CERTIFICATE_VERIFY_FAILED on every https target,
    while curl uses the system trust store and works.
    """
    if t.startswith(("http://", "https://")):
        r = subprocess.run(["curl", "-sSL", "--max-time", "60", "-w", "%{http_code}",
                            "-o", "/dev/stdout", t],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:160] or f"curl exit {r.returncode}")
        body, code = r.stdout[:-3], r.stdout[-3:]
        if code != "200":
            raise RuntimeError(f"HTTP {code}")
        return body
    return open(t, encoding="utf-8", errors="replace").read()

SKIP_TAGS = {"script", "style", "code", "pre", "math", "annotation", "semantics"}
# Quarto puts the raw citation key in a hover popup and in the reference
# list; both are real DOM text, so a bare `@key` scan reports every correct
# citation on the page. These subtrees are excluded wholesale.
# NOTE "citation" is deliberately NOT here, and the reason is narrower than
# it first looks. Pandoc's unresolved-key markup does sit inside
# `class="citation"`, but the detector for it reads the RAW html, so a class
# exclusion cannot silence that one. What a `citation` exclusion WOULD
# silence is the `?@key` text scan, since Quarto puts a literal `?@fig-x`
# inside a citation span -- excluding the class makes that case invisible.
# The bibliography (`csl-entry`) is excluded instead, which is what actually
# caused the bare-`@key` noise. A `tippy` entry was here too and was removed:
# Quarto's hover popups are injected client-side, so that markup never
# appears in HTML fetched by curl or read from `_site/`, and the entry could
# not match anything.
SKIP_CLASS = frozenset({
    "katex", "katex-mathml", "katex-html", "math", "sourcecode",
    "cell-output", "csl-entry", "footnotes", "quarto-title-meta",
})


class _Visible(HTMLParser):
    """Collect rendered prose, skipping whole subtrees that are not prose.

    A regex cannot do this: KaTeX nests spans several deep, so a non-greedy
    `<span class=katex>.*?</span>` stops at the first inner close and the
    rest of the math leaks into the text. Twenty false positives on a clean
    page came from exactly that, which is why this is a parser.
    """

    def __init__(self, per_paragraph=False):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.depth = 0          # >0 while inside a skipped subtree
        self.stack = []
        self.per_paragraph = per_paragraph
        self.paragraphs = []
        self._para = None       # buffer while inside a <p>

    def handle_starttag(self, tag, attrs):
        if self.per_paragraph and tag == "p" and self._para is None:
            self._para = []
        cls = " ".join(v or "" for k, v in attrs if k == "class").lower()
        # Exact TOKEN membership, not substring containment. `"footnotes" in
        # cls` also matches `gt_footnotes`, a real class gt emits on live
        # pages and nothing to do with document footnotes -- so a genuine
        # defect inside a gt table footer became invisible to every check.
        skip = tag in SKIP_TAGS or bool(SKIP_CLASS & set(cls.split()))
        self.stack.append(skip)
        if skip:
            self.depth += 1

    def handle_endtag(self, tag):
        if self.stack:
            if self.stack.pop():
                self.depth = max(0, self.depth - 1)
        if self.per_paragraph and tag == "p" and self._para is not None:
            self.paragraphs.append("".join(self._para))
            self._para = None

    def handle_data(self, data):
        if self.depth:
            return
        self.out.append(data)
        if self._para is not None:
            self._para.append(data)


def _paragraphs(s):
    """Visible text of each `<p>`, with skipped subtrees removed."""
    p = _Visible(per_paragraph=True)
    try:
        p.feed(s)
    except Exception:
        return [re.sub(r"<[^>]+>", " ", m)
                for m in re.findall(r"<p>.*?</p>", s, re.S)]
    return p.paragraphs


def _visible_text(s):
    """Rendered prose only: no script, style, code, math, or citation chrome."""
    p = _Visible()
    try:
        p.feed(s)
    except Exception:
        return html.unescape(re.sub(r"<[^>]+>", " ", s))
    return " ".join(p.out)


# Each check is (label, finder). A finder returns a list of offending strings.
# A bullet or numbered marker that pandoc left inside a paragraph. Two
# positions matter, and the second is the commoner mistake:
#
#   <p>- item</p>                      a list with nothing before it
#   <p>Lead-in sentence. - item</p>    a list after a lead-in, no blank line
#
# The second is what pandoc actually emits for the usual error, since a list
# normally introduces something and the lead-in sits in the same source
# block. Anchoring only at `<p>` start missed it entirely.
#
# Mid-paragraph markers are accepted only after sentence-ending punctuation,
# which keeps ordinary prose out: "the range a - b is inclusive" has a word
# character before the dash, so it never matches.
#
# Mid-paragraph detection is BULLETS ONLY, deliberately. A numbered marker
# after a period is ordinary English -- "See Fig. 1. It shows the trend",
# "values are 1. 2. and 3." -- and both of those matched when numbered
# markers were allowed there. A numbered list that loses its blank line
# after a lead-in sentence therefore goes undetected; that is the price of
# keeping the false-positive rate at zero, which for a checker other
# sessions will trust is the side to err on. Numbered markers are still
# caught at the start of a paragraph.
RX_LIST_IN_P = re.compile(
    r'<p>\s*((?:[-*+]|\d+\.)[ \t]+\S[^<]{0,90})'
    r'|(?<=[.:!?])\s+([-*+][ \t]+\S[^<]{0,90})')


def _list_failed(s):
    r"""Markdown list markers that survived into a rendered paragraph.

    Reads each paragraph's VISIBLE text, with math excluded like every other
    check. Scanning the raw `<p>` markup instead produced a false positive on
    a real 4.3 MB page: a display equation ending `... + \hat\beta_p x_p`
    puts a `+` right after the ellipsis's final `.`, which the mid-paragraph
    branch read as a bullet marker. `_list_failed` was the one check not
    routed through the parser, and that was the whole of the bug.
    """
    out = []
    for para in _paragraphs(s):
        for a, b in RX_LIST_IN_P.findall("<p>" + para + "</p>"):
            out.append(html.unescape(a or b).strip()[:90])
    return out


class _StripCode(HTMLParser):
    """Re-emit raw MARKUP with `<code>` and `<pre>` subtrees removed.

    `_katex_error` is the one check that cannot route through
    `_visible_text`, for two independent reasons. Its signal is a `class=`
    attribute, which the visible-text parser discards by design; and
    `SKIP_CLASS` carries `katex` and `math`, which are the very wrappers a
    KaTeX error span sits inside, so reusing it would silence every genuine
    hit rather than only the noise.

    What the check does still need is the `<code>`/`<pre>` exclusion its four
    siblings get, so a page QUOTING `class="katex-error"` or the words
    `Undefined control sequence` inside a code block is not reported as
    having a KaTeX error -- a page documenting this checker is exactly such a
    page. This parser supplies that exclusion and nothing else.

    A regex strip was rejected for the reason `_Visible`'s own docstring
    gives: a non-greedy `<pre>.*?</pre>` stops at the first inner close, so
    it mis-handles the nesting pandoc actually emits (`<pre><code>`).
    """

    DROP = {"code", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.DROP:
            self.depth += 1
        elif not self.depth:
            self.out.append(self.get_starttag_text() or "")

    def handle_startendtag(self, tag, attrs):
        if not self.depth and tag not in self.DROP:
            self.out.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag):
        if tag in self.DROP:
            self.depth = max(0, self.depth - 1)
        elif not self.depth:
            self.out.append("</" + tag + ">")

    def handle_data(self, d):
        if not self.depth:
            self.out.append(d)

    def handle_entityref(self, name):
        if not self.depth:
            self.out.append("&" + name + ";")

    def handle_charref(self, name):
        if not self.depth:
            self.out.append("&#" + name + ";")


def _markup_without_code(s):
    p = _StripCode()
    p.feed(s)
    p.close()
    return "".join(p.out)


def _katex_error(s):
    """KaTeX / LaTeX errors, read from MARKUP with code blocks removed.

    See `_StripCode` for why this check reads markup rather than visible
    text, and why it cannot reuse `SKIP_CLASS`.
    """
    m = _markup_without_code(s)
    out = re.findall(r'class="[^"]*katex-error[^"]*"[^>]*>([^<]{0,80})', m)
    out += re.findall(r'(Undefined control sequence[^<]{0,60})', m)
    return [html.unescape(x) for x in out]

# Pandoc's unresolved-citation rendering, structurally: a doc-biblioref link
# whose visible text is the key with a trailing `?`. Matched on the markup
# rather than on prose, because the same `word?` shape in ordinary English is
# indistinguishable once tags are stripped -- an earlier text-level version
# reported eleven hits on a page with no citation problem at all.
# Quarto's crossref key prefixes. One source of truth: `_bad_crossref` matches
# them, and `_bad_citation` subtracts them so a single unresolved crossref is
# not also reported as an unresolved CITATION. Two copies of this list would
# drift, and the drift is silent -- a prefix present in one and missing from
# the other resurfaces the double-report for exactly that type.
XREF_PREFIXES = ("fig", "tbl", "sec", "eq", "thm", "def", "exm", "exr",
                 "lem", "cor", "prp", "rem", "sol", "cnj")
_XREF_ALT = "|".join(XREF_PREFIXES)
RX_UNRESOLVED_XREF = re.compile(r'\?@(?:' + _XREF_ALT + r')-[\w-]+')
# Matches the PREFIX only, so it also subtracts a key whose tail carries a
# character `RX_UNRESOLVED_XREF` stops at (`?@fig-a.b`). Anchoring on the full
# key would let that shape slip back into the citation list.
RX_XREF_KEY_HEAD = re.compile(r'\?@(?:' + _XREF_ALT + r')-')

# A LaTeX control sequence that failed to expand, EXCLUDING a backslash that
# sits in a path-like context. `\[a-zA-Z]{2,}` alone matches every segment of
# `C:\Users\Documents\myfile`, so any page whose prose mentions a Windows path
# scored itself not-clean -- the false-positive rate this checker's own
# docstring calls disqualifying.
#
# The lookbehind is what draws the line: a real macro follows whitespace, `$`,
# `{` or start-of-text, while a path segment follows a drive letter, a colon or
# the previous segment's name. It costs one gap, deliberately: the second macro
# of `$\hat\beta$` is preceded by a letter and so is not reported. The FIRST
# one still is, so the page is still flagged -- a count is lost, never a verdict.
RX_RAW_MACRO = re.compile(r'(?<![A-Za-z0-9:._/\\-])\\[a-zA-Z]{2,}')

RX_UNRESOLVED_CITE = re.compile(
    r'role="doc-biblioref"[^>]*>\s*(?:<strong>)?\s*([\w:.-]+\?)\s*(?:</strong>)?\s*</a>',
    re.I)


def _bad_citation(s):
    """Unresolved citation keys, as Quarto actually renders them.

    Two detectors, because Quarto has two shapes:

    * a literal `?@key` surviving in prose, scanned over visible text;
    * pandoc's unresolved-citation markup, matched STRUCTURALLY on the raw
      HTML -- an `<a role="doc-biblioref">` whose visible text is `key?`.

    The second is structural rather than textual because an earlier version
    scanned stripped text for `word?` and matched ordinary English instead --
    `plausible?`, `measurement?` -- eleven times on a page with no citation
    problem at all. A checker with that failure rate gets ignored.

    Note the asymmetry in what `SKIP_CLASS` can affect: the structural
    detector reads the raw HTML, so no class exclusion can silence it, while
    the `?@` scan reads visible text and therefore can be silenced. That is
    why `citation` must stay OUT of `SKIP_CLASS` -- see the note there.
    """
    out = [m for m in re.findall(r'\?@[\w:.-]+', _visible_text(s))
           if not RX_XREF_KEY_HEAD.match(m)]
    out += sorted(set(RX_UNRESOLVED_CITE.findall(s)))
    return out

def _bad_crossref(s):
    """Unresolved crossrefs, read from VISIBLE text.

    Routed through the parser like its siblings. Scanning raw HTML instead
    reports a literal `?@fig-x` written inside a `<code>` span as a finding
    -- which is how this corpus's own fragment documents the failure, so a
    page explaining Quarto crossrefs would score itself not-clean.
    """
    return [html.unescape(m) for m in RX_UNRESOLVED_XREF.findall(_visible_text(s))]

def _raw_macro(s):
    """A backslash macro surviving into rendered PROSE.

    Math is excluded wholesale by `_visible_text`. Without that, every page
    using KaTeX reports its own math source as an unexpanded macro -- twenty
    hits on a clean page, which is worse than no check.
    """
    return RX_RAW_MACRO.findall(_visible_text(s))[:20]

CHECKS = [
    ("list rendered as a paragraph (missing blank line before it)", _list_failed),
    ("KaTeX / LaTeX error in the rendered math", _katex_error),
    ("unresolved citation key", _bad_citation),
    ("unresolved crossref", _bad_crossref),
    ("unexpanded macro in rendered text", _raw_macro),
]

def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    worst = 0
    for t in argv[1:]:
        try:
            s = fetch(t)
        except Exception as e:
            print(f"FETCH-FAIL  {t}: {e}"); worst = max(worst, 2); continue
        hits = []
        for label, fn in CHECKS:
            found = fn(s)
            if found:
                hits.append((label, found))
        if hits:
            worst = max(worst, 1)
            print(f"NOT CLEAN   {t}")
            for label, found in hits:
                print(f"  - {label}: {len(found)}")
                for f in found[:4]:
                    print(f"      {f!r}")
        else:
            print(f"clean       {t}   ({len(s):,} bytes, {len(re.findall('<li', s))} list items)")
    return worst

if __name__ == "__main__":
    sys.exit(main(sys.argv))
