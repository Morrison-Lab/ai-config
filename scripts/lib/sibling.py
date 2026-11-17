"""Load a hook's hyphenated sibling module by path, shared by the hooks.

A hook file name such as `no-push-without-self-review.py` is not a Python
identifier, so a hook that reuses another hook's code loads it with
`importlib` by path. Most such hooks still carry their own copy of that
loader, and the copies disagree: some return None when the sibling is
missing and some raise (ai-config#2018, which moves them here).

`load_sibling` is the one copy. A fail-open hook takes None when the
sibling cannot load, and then degrades or goes silent as it chooses; the
loader names the cause on stderr either way. A fail-closed hook, which
must handle the error itself, passes `required=True` to get the error.
"""
import importlib.util
import os
import re
import sys


def load_sibling(hook_file, name, key=None, *, required=False):
    """Import the module `name` that sits beside `hook_file`.

    `hook_file` is the calling hook's `__file__`; symlinks are resolved, so
    a hook linked into another directory still finds its real siblings.
    `key` is the module name the import uses, derived from `name` when not
    given. Returns the module, or None if it cannot be loaded, after saying
    why on stderr. With `required=True`, the error is raised instead.
    """
    path = os.path.join(os.path.dirname(os.path.realpath(hook_file)), name)
    if key is None:
        key = "_sibling_" + re.sub(r"\W", "_", os.path.splitext(name)[0])
    try:
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as exc:
        if required:
            raise
        print(f"{os.path.basename(hook_file)}: cannot load sibling {name} ({exc}); "
              "running without it", file=sys.stderr)
        return None
