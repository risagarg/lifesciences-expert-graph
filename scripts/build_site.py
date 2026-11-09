#!/usr/bin/env python3
"""Moved to scripts/build.py. Run `python3 scripts/build.py --site` for the local viewer."""
import runpy
import sys
import pathlib

sys.argv = [sys.argv[0], "--site"]
runpy.run_path(str(pathlib.Path(__file__).with_name("build.py")), run_name="__main__")
