#!/usr/bin/env python3
"""Chunked Argon read for a PR whose diff `gh pr diff` refuses (HTTP 406, over 300 files).

usage: bigread.py owner/repo PR [focus text]

Lists the PR's files through the paginated files API, packs their patches into
chunks of at most CHUNK_CHARS, runs one agy read per chunk (WORKERS at a time),
and writes the combined result to out-<owner>_<repo>-<PR>.txt in the format
post.sh reads (line 1 `HEAD: <sha>`).  Any chunk that does not return a real
verdict, or any empty patch list, is a hard error: nothing is written for post.sh.
"""
import json
import os
import re
import subprocess
import sys
import concurrent.futures as cf

CHUNK_CHARS = 22000
WORKERS = 5
MODEL = os.environ.get("MODEL", "gemini-4-argon-medium")
HERE = os.path.dirname(os.path.abspath(__file__))
TAIL = (
    " Do not write a plan, do not create artifacts, do not ask questions or request approval:"
    " answer in one pass with the review itself. List every finding, wording and style nits"
    " included, each in at most 3 lines with the quoted passage. Keep the answer under 3000"
    " characters. The last line must be exactly VERDICT: FINDINGS if you list any finding at"
    " all, or exactly VERDICT: CLEAN if there is none (then say only that nothing was found)."
)


def clean_part(out):
    """One part's findings: the text before its first VERDICT line, minus status chatter."""
    keep = []
    for line in out.splitlines():
        if line.startswith("VERDICT:"):
            break
        if line.startswith("**Stopping Point") or line.startswith("**Status"):
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def die(msg):
    sys.stderr.write("FATAL: " + msg + "\n")
    sys.exit(5)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        die("%s failed: %s" % (" ".join(cmd[:4]), p.stderr.strip()[:300]))
    return p.stdout


def list_files(repo, pr):
    raw = run(["gh", "api", "--paginate", "repos/%s/pulls/%s/files" % (repo, pr)])
    dec, i, items = json.JSONDecoder(), 0, []
    while i < len(raw):
        while i < len(raw) and raw[i].isspace():
            i += 1
        if i >= len(raw):
            break
        obj, i = dec.raw_decode(raw, i)
        items += obj
    if not items:
        die("the files API returned no files for %s#%s" % (repo, pr))
    return items


def pack(items):
    pieces = []
    for f in items:
        patch = f.get("patch")
        if not patch:
            die("no patch text for %s (binary or too large); cannot review it" % f["filename"])
        text = "FILE: %s (%s)\n%s\n" % (f["filename"], f["status"], patch)
        while len(text) > CHUNK_CHARS:  # split one huge patch on line boundaries
            cut = text.rfind("\n", 0, CHUNK_CHARS)
            cut = cut if cut > 0 else CHUNK_CHARS
            pieces.append((f["filename"], text[:cut]))
            text = "FILE: %s (continued)\n%s" % (f["filename"], text[cut:])
        pieces.append((f["filename"], text))
    chunks, cur, names = [], "", []
    for name, text in pieces:
        if cur and len(cur) + len(text) > CHUNK_CHARS:
            chunks.append((names, cur))
            cur, names = "", []
        cur += text
        names.append(name)
    if cur:
        chunks.append((names, cur))
    return chunks


def read_chunk(idx, total, names, text, repo, pr, meta, focus):
    prompt = (
        "You are an adversarial reviewer of part %d of %d of GitHub PR %s#%s. Everything you need is "
        "below; do not call tools or edit files. Check for correctness errors, broken Quarto syntax or "
        "crossrefs, lost or duplicated content (an include or exercise dropped or listed twice), "
        "factual errors, ambiguous pronouns and style problems in the files of THIS part only. Quote "
        "the exact passage for each finding.\n\n%s\n\n%s\n\nDIFF (part %d of %d, files %s ... %s):\n%s"
        % (idx + 1, total, repo, pr, focus + TAIL, meta, idx + 1, total, names[0], names[-1], text)
    )
    last = ""
    for _ in range(3):
        try:
            p = subprocess.run(
                ["agy", "--model", MODEL, "--mode", "plan", "--print-timeout", "880s", "-p=" + prompt],
                capture_output=True, text=True, encoding="utf-8", timeout=900)
            out = p.stdout + p.stderr
        except subprocess.TimeoutExpired:
            out = "AGY_ERROR timeout"
        last = out
        lines = [l for l in out.splitlines() if l.strip()]
        ok = (lines and lines[-1].strip() in ("VERDICT: CLEAN", "VERDICT: FINDINGS")
              and not re.search(r"AGY_ERROR|RESOURCE_EXHAUSTED", out)
              and not re.search(r"awaiting (your )?(approval|confirmation)|implementation plan", out, re.I))
        if ok:
            return idx, lines[-1].strip()[9:], out.strip()
    return idx, "ERROR", last[-500:]


def main():
    if len(sys.argv) < 3:
        die("usage: bigread.py owner/repo PR [focus]")
    repo, pr = sys.argv[1], sys.argv[2]
    focus = sys.argv[3] if len(sys.argv) > 3 else ""
    info = json.loads(run(["gh", "pr", "view", pr, "-R", repo, "--json", "headRefOid,title,state,body"]))
    head = info["headRefOid"]
    if info["state"] != "OPEN":
        die("PR is %s" % info["state"])
    items = list_files(repo, pr)
    chunks = pack(items)
    meta = "HEAD: %s\nTITLE: %s\nBODY:\n%s" % (head, info["title"], (info["body"] or "")[:3000])
    sys.stderr.write("%d files, %d chunks at %s\n" % (len(items), len(chunks), head[:8]))
    results = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(read_chunk, i, len(chunks), n, t, repo, pr, meta, focus)
                for i, (n, t) in enumerate(chunks)]
        for f in cf.as_completed(futs):
            results.append(f.result())
    results.sort()
    bad = [r for r in results if r[1] == "ERROR"]
    if bad:
        die("chunks without a real verdict: %s; first failure tail: %s" % ([b[0] + 1 for b in bad], bad[0][2][-300:]))
    now = json.loads(run(["gh", "pr", "view", pr, "-R", repo, "--json", "headRefOid"]))["headRefOid"]
    if now != head:
        sys.stderr.write("WARNING: head moved from %s to %s during the read\n" % (head[:8], now[:8]))
    findings = []
    for idx, verdict, out in results:
        if verdict == "FINDINGS":
            body = clean_part(out)
            findings.append("**Part %d of %d (%s ... %s)**\n\n%s" % (
                idx + 1, len(chunks), chunks[idx][0][0], chunks[idx][0][-1], body))
    verdict = "FINDINGS" if findings else "CLEAN"
    body = ("\n\n".join(findings) if findings else
            "Read in %d parts covering all %d files; nothing found in any part." % (len(chunks), len(items)))
    path = os.path.join(HERE, "out-%s-%s.txt" % (repo.replace("/", "_"), pr))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("HEAD: %s\nSTATE: OPEN\n%s\nVERDICT: %s\n" % (head, body, verdict))
    print("wrote %s verdict=%s parts=%d files=%d head=%s" % (path, verdict, len(chunks), len(items), head))


if __name__ == "__main__":
    main()
