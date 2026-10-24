#!/usr/bin/env python3
"""
react_in_meetings_v2.py — Backward-compatibility forwarder for CleoStream.
Project has been renamed to CleoStream. Please use cleostream.py directly.
"""
import runpy
import sys
import warnings

warnings.warn(
    "react_in_meetings_v2.py is deprecated and will be removed in a future release. "
    "Please run 'cleostream.py' instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    runpy.run_module("cleostream", run_name="__main__")
