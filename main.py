"""マウスジェスチャー機能のエントリポイント（現時点では動作確認用）。

起動時に test/run_tests.py でテスト全件パスを確認し、失敗していれば起動を止める。
その後 MouseInput.update() を叩き続けるループで、移動量とボタンの
押下/離す 瞬間だけをターミナルに出力する。win_action.py はここでは使わない。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from mouse_input import ButtonState, MouseInput

POLL_INTERVAL_SECONDS = 0.02
HISTORY_LENGTH = 100

_PRINTABLE_BUTTON_STATES = (ButtonState.PRESSED, ButtonState.RELEASED)


def _ensure_tests_pass() -> None:
    project_root = Path(__file__).resolve().parent
    runner_script = project_root / "test" / "run_tests.py"
    result = subprocess.run([sys.executable, str(runner_script)])
    if result.returncode != 0:
        print(
            "[FATAL] スタートアップテストに失敗しました。"
            " mouse_input.py / win_action.py の修正が必要です。起動を中止します。",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    _ensure_tests_pass()

    mouse = MouseInput(history_length=HISTORY_LENGTH)

    print("マウスジェスチャー監視を開始します（Ctrl+C で終了）。")
    try:
        while True:
            mouse.update()

            delta = mouse.get_delta()
            if delta is not None and delta != (0, 0):
                dx, dy = delta
                print(f"[MOVE] dx={dx:+d} dy={dy:+d}")

            for button, state in mouse.get_all_button_states().items():
                if state in _PRINTABLE_BUTTON_STATES:
                    print(f"[BUTTON] {button.name}: {state.name}")

            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("終了します。")


if __name__ == "__main__":
    main()
