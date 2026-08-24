#!/usr/bin/env python3
"""Executable entrypoint for the Persistent Orchestrator CLI."""

import sys
import os

# Ensure package is importable when executed directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.cli import main

if __name__ == "__main__":
    main()
