"""Pluggable backends for xTalent Graph.

Each module in this package implements one of the core protocols defined in
:mod:`xtalent.publish` (``IPFSClient``) or :mod:`xtalent.search`
(``Embedder`` / ``VectorIndex``) against an external system.

Submodules import their third-party dependencies lazily so the core package
stays importable even when optional extras are not installed.
"""
