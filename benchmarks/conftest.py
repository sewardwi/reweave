"""Make the benchmark modules importable from tests without packaging them.

The harness is scripts, not a library — it is run as ``python benchmarks/run_bench.py``. This
keeps the test imports working without inventing a distribution for it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
