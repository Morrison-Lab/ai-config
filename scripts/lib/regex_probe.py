"""Time a regex search in a child process that can be killed (ai-config#5503).

Without SIGALRM (Windows, or a non-main thread), a thread joined with a timeout
bounds nothing: `re` holds the GIL for the whole match, so the regex tests hung
the Windows job for its full 60 minutes. So one long-lived child Python (one
process per probe would cost minutes) gets one probe per line; the caller waits
on a queue that a reader thread fills, and kills a child that misses the
deadline. The child times the search alone, as the SIGALRM path does, and the
caller waits GRACE seconds past the timeout, so a slow round trip is not
counted against the pattern.
"""
import atexit
import json
import queue
import subprocess
import sys
import threading
import time

_WORKER = r"""
import json, os, re, sys, time
# Answers go out on a private copy of stdout. Anything else the child prints,
# such as re.DEBUG's parse tree, goes to stderr and cannot break the protocol.
proto = os.fdopen(os.dup(1), "w", encoding="utf-8")
os.dup2(2, 1)
sys.stdout = sys.stderr
proto.write("ready\n")
proto.flush()
for line in sys.stdin:
    req = json.loads(line)
    try:
        compiled = re.compile(req["p"], req["f"])
        t0 = time.perf_counter()
        compiled.search(req["s"])
        out = {"d": time.perf_counter() - t0}
    except Exception as exc:
        out = {"e": str(exc)}
    proto.write(json.dumps(out) + "\n")
    proto.flush()
"""

STARTUP_TIMEOUT = 60.0  # starting the child is not part of any probe's time
GRACE = 1.0  # how long past a probe's timeout the caller waits for an answer


class ProbeWorker:
    """A killable child that runs `re.compile(p, f).search(s)` on request."""

    def __init__(self):
        self._proc = None
        self._lines = None
        # One child serves one request at a time, so concurrent callers queue here.
        self._lock = threading.Lock()

    def _start(self):
        self._proc = subprocess.Popen(
            [sys.executable, "-I", "-u", "-c", _WORKER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            encoding="utf-8")
        self._lines = queue.Queue()
        threading.Thread(target=self._read, args=(self._proc.stdout, self._lines),
                         daemon=True).start()
        try:
            first = self._lines.get(timeout=STARTUP_TIMEOUT)
        except queue.Empty:
            first = None
        if first != "ready\n":
            self.close()
            raise RuntimeError(f"regex probe worker did not start (got {first!r})")

    @staticmethod
    def _read(stream, lines):
        for line in stream:
            lines.put(line)
        lines.put(None)

    def close(self):
        if self._proc is None:
            return
        proc, self._proc = self._proc, None
        proc.kill()
        proc.wait()
        for stream in (proc.stdin, proc.stdout):
            try:
                stream.close()
            except OSError:
                pass  # a pipe to a killed child may already be broken

    def _send(self, request):
        """Write one request, starting the child first if it is not running."""
        if self._proc is None:
            self._start()
        self._proc.stdin.write(request + "\n")
        self._proc.stdin.flush()

    def search(self, pattern_str, flags, probe, timeout):
        """Return (passed, duration, error_or_timeout_msg), like test_dynamic_probe.

        A child that dies while answering raises RuntimeError: that is a fault
        in the worker, not a finding about the pattern.
        """
        with self._lock:
            return self._search(pattern_str, flags, probe, timeout)

    def _search(self, pattern_str, flags, probe, timeout):
        request = json.dumps({"p": pattern_str, "f": flags, "s": probe})
        try:
            self._send(request)
        except OSError:
            # The child died since the last probe: start a new one, once.
            self.close()
            self._send(request)
        t0 = time.perf_counter()
        try:
            line = self._lines.get(timeout=timeout + GRACE)
        except queue.Empty:
            # The search is still running: kill the child; the next call starts another.
            dur = time.perf_counter() - t0
            self.close()
            return False, dur, f"Execution timed out (> {timeout:.2f}s)"
        if line is None:
            code = self._proc.wait()
            self.close()
            raise RuntimeError(
                f"regex probe worker exited with code {code} during a probe of {pattern_str!r}")
        try:
            out = json.loads(line)
        except ValueError:
            # The stream is out of step with the requests: never reuse it.
            self.close()
            raise RuntimeError(
                f"regex probe worker sent {line!r} for a probe of {pattern_str!r}") from None
        if "e" in out:
            return True, 0.0, out["e"]
        if out["d"] > timeout:
            return False, out["d"], f"Execution timed out (> {timeout:.2f}s)"
        return True, out["d"], None


_shared = ProbeWorker()
atexit.register(_shared.close)


def search_in_child(pattern_str, flags, probe, timeout):
    """Run one probe in the shared child; see ProbeWorker.search."""
    return _shared.search(pattern_str, flags, probe, timeout)
