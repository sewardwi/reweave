"""Reweave analysis engine.

Pure Python. Never imports from ``apps/`` — it must run standalone as the ``reweave-audit`` CLI
and inside the benchmark harness.
"""

from reweave_engine.baseline import TokenOverlapDetector
from reweave_engine.detector import LoadedUnit, PairDetector

__version__ = "0.0.0"

__all__ = ["LoadedUnit", "PairDetector", "TokenOverlapDetector", "__version__"]
