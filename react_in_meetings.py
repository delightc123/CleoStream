#!/usr/bin/env python3
"""
react_in_meetings.py — Backward-compatibility forwarder for CleoStream Fallback.
Project has been renamed to CleoStream. Please use cleostream_fallback.py directly.
"""
import runpy
import sys
import warnings

warnings.warn(
    "react_in_meetings.py is deprecated and will be removed in a future release. "
    "Please run 'cleostream_fallback.py' instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    runpy.run_module("cleostream_fallback", run_name="__main__")
