"""Every shell script in this directory must at least parse (`bash -n`)."""
import glob
import os
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
@pytest.mark.parametrize("script", sorted(glob.glob(os.path.join(_HERE, "*.sh"))))
def test_script_parses(script):
    result = subprocess.run(["bash", "-n", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
