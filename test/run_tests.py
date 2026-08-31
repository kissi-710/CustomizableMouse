"""main.py から起動時チェックとして呼び出されるテストランナー。

`python test/run_tests.py` として単体実行することもできる。
終了コード 0 = 全件パス、0以外 = 失敗（1件以上のテストが失敗 or エラー）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


def run_all_tests() -> bool:
    this_dir = Path(__file__).resolve().parent
    project_root = this_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(this_dir), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
