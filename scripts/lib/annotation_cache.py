"""Read a check run's annotations through a disk cache keyed by check-run id (ai-config#6032).

A completed check run's annotations never change, and a re-run gets a new
check-run id, so a cached read is safe when the run is `completed` and the
cached list holds exactly `annotations_count` items. Anything else (a run still
in progress, a count mismatch, an unreadable file) falls through to a live read,
and only a complete live read of a completed run is written back.

On a gha head about 110 runs carry annotations, so each uncached read of a head
costs at least 110 calls from the shared REST budget; a cached re-read costs
none, and `main`'s tip is read once instead of once per PR compared with it.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PER_PAGE = 100


def default_cache_dir():
    """`$AI_CONFIG_ANNOTATION_CACHE`, else `~/.cache/ai-config/annotations`."""
    env = os.environ.get("AI_CONFIG_ANNOTATION_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "ai-config" / "annotations"


def cache_path(cache_dir, repo, run_id):
    return Path(cache_dir) / repo.replace("/", "__") / f"{run_id}.json"


def expected_count(run):
    return (run.get("output") or {}).get("annotations_count") or 0


def cached(cache_dir, repo, run):
    """The cached annotations of `run`, or None when no trustworthy copy exists."""
    if cache_dir is None or run.get("status") != "completed":
        return None
    path = cache_path(cache_dir, repo, run["id"])
    try:
        anns = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(anns, list) or len(anns) != expected_count(run):
        return None
    return anns


def store(cache_dir, repo, run, anns):
    """Write a complete read of a completed run; skip anything else."""
    if cache_dir is None or run.get("status") != "completed" or len(anns) != expected_count(run):
        return
    path = cache_path(cache_dir, repo, run["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(anns), encoding="utf-8")
    os.replace(tmp, path)


def read_annotations(api, repo, run, cache_dir=None, per_page=PER_PAGE):
    """Every annotation on `run`: from the cache when trustworthy, else paged live and stored."""
    hit = cached(cache_dir, repo, run)
    if hit is not None:
        return hit
    out, page = [], 1
    while True:
        batch = api(f"repos/{repo}/check-runs/{run['id']}/annotations"
                    f"?per_page={per_page}&page={page}")
        out += batch
        if len(batch) < per_page:
            break
        page += 1
    store(cache_dir, repo, run, out)
    return out


def gh_api(path):
    """GET `path` with `gh api`, paged by the caller (`--paginate` 403s in CCR, gha#1432)."""
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def annotated_runs(api, repo, sha, per_page=PER_PAGE):
    """Every check run on `sha` that carries annotations."""
    runs, page = [], 1
    while True:
        batch = api(f"repos/{repo}/commits/{sha}/check-runs?per_page={per_page}&page={page}")["check_runs"]
        runs += [r for r in batch if expected_count(r)]
        if len(batch) < per_page:
            return runs
        page += 1


def rows(api, repo, sha, cache_dir=None):
    """One (run id, level, path, first 140 characters of the message's first line) per annotation."""
    for run in annotated_runs(api, repo, sha):
        for ann in read_annotations(api, repo, run, cache_dir):
            first = (ann.get("message") or "").split("\n")[0][:140]
            yield (str(run["id"]), ann.get("annotation_level") or "", ann.get("path") or "", first)


def main(argv=None):
    """`annotation_cache.py rows OWNER/REPO SHA`: the rows summarize-pr-annotations.sh prints."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or args[0] != "rows":
        print("usage: annotation_cache.py rows OWNER/REPO SHA", file=sys.stderr)
        return 2
    try:
        for row in rows(gh_api, args[1], args[2], default_cache_dir()):
            print("\t".join(field.replace("\t", " ") for field in row))
    except (RuntimeError, KeyError, ValueError) as exc:
        print(f"ERROR: incomplete read: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
