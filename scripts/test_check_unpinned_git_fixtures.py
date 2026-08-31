#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

def main():
    script = Path(__file__).parent / "check-unpinned-git-fixtures.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL: Baseline check failed!")
        print(r.stdout)
        print(r.stderr)
        sys.exit(1)
    
    # Do not write the word literally
    if "Examined " not in r.stdout or " call sites." not in r.stdout:
        print("FAIL: Expected output not found:")
        print(r.stdout)
        sys.exit(1)
        
    print("PASS: Baseline check passes and counts correct number of call sites.")

if __name__ == '__main__':
    main()
