"""Implementations of data input/output (codecs).

Concrete codecs live in submodules; this package intentionally has no eager imports,
so heavy optional dependencies (OpenCV, SlideIO, ...) are loaded only on demand.
"""
