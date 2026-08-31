"""Windows のマウス状態（位置・移動量・ボタン）をポーリングで取得するモジュール。

詳細な仕様は SPEC.md、使い方は docs/api/mouse_input.md を参照。
"""

from __future__ import annotations

import ctypes
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto


class MouseButton(Enum):
    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()
    X1 = auto()
    X2 = auto()


class ButtonState(Enum):
    PRESSED = auto()   # 今tick押された（立ち上がりエッジ）
    HELD = auto()       # 押され続けている
    RELEASED = auto()   # 今tick離された（立ち下がりエッジ）
    IDLE = auto()        # 離され続けている


# GetAsyncKeyState に渡す仮想キーコード（マウスボタン用）
_BUTTON_VK_CODES: dict[MouseButton, int] = {
    MouseButton.LEFT: 0x01,    # VK_LBUTTON
    MouseButton.RIGHT: 0x02,   # VK_RBUTTON
    MouseButton.MIDDLE: 0x04,  # VK_MBUTTON
    MouseButton.X1: 0x05,      # VK_XBUTTON1
    MouseButton.X2: 0x06,      # VK_XBUTTON2
}


@dataclass(frozen=True)
class MouseSnapshot:
    """1回の update() 呼び出し時点でのマウス状態のスナップショット。"""

    timestamp: float
    x: int
    y: int
    dx: int
    dy: int
    buttons: dict[MouseButton, ButtonState]


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MouseInput:
    """マウスの位置・移動量・ボタン状態をポーリングで追跡するクラス。

    呼び出し側（main.py 等）が任意の間隔で update() を呼び続けることで、
    内部状態と履歴が更新される。自前のタイマー・スレッドは持たない。
    """

    def __init__(self, history_length: int = 100) -> None:
        if history_length <= 0:
            raise ValueError("history_length must be a positive integer")
        self._history_length = history_length
        self._history: deque[MouseSnapshot] = deque(maxlen=history_length)
        self._last_position: tuple[int, int] | None = None
        self._last_button_down: dict[MouseButton, bool] = {
            button: False for button in MouseButton
        }

    def update(self) -> None:
        """現在のマウス状態を読み取り、内部状態・履歴を1tick分更新する。"""
        x, y = self._read_cursor_pos()
        if self._last_position is None:
            dx, dy = 0, 0
        else:
            dx, dy = x - self._last_position[0], y - self._last_position[1]
        self._last_position = (x, y)

        buttons: dict[MouseButton, ButtonState] = {}
        for button in MouseButton:
            is_down = self._read_button_down(_BUTTON_VK_CODES[button])
            was_down = self._last_button_down[button]
            buttons[button] = self._resolve_state(was_down, is_down)
            self._last_button_down[button] = is_down

        self._history.append(
            MouseSnapshot(
                timestamp=self._now(),
                x=x,
                y=y,
                dx=dx,
                dy=dy,
                buttons=buttons,
            )
        )

    # --- 現在値 ---

    def get_position(self) -> tuple[int, int] | None:
        if not self._history:
            return None
        last = self._history[-1]
        return last.x, last.y

    def get_delta(self) -> tuple[int, int] | None:
        if not self._history:
            return None
        last = self._history[-1]
        return last.dx, last.dy

    def get_button_state(self, button: MouseButton) -> ButtonState:
        if not self._history:
            return ButtonState.IDLE
        return self._history[-1].buttons[button]

    def get_all_button_states(self) -> dict[MouseButton, ButtonState]:
        if not self._history:
            return {button: ButtonState.IDLE for button in MouseButton}
        return dict(self._history[-1].buttons)

    # --- 履歴（古い→新しい順） ---

    def get_history(self, n: int | None = None) -> list[MouseSnapshot]:
        history = list(self._history)
        if n is None:
            return history
        if n <= 0:
            return []
        return history[-n:]

    def get_button_history(
        self, button: MouseButton, n: int | None = None
    ) -> list[ButtonState]:
        return [snapshot.buttons[button] for snapshot in self.get_history(n)]

    # --- 状態遷移ロジック ---

    @staticmethod
    def _resolve_state(was_down: bool, is_down: bool) -> ButtonState:
        if is_down:
            return ButtonState.PRESSED if not was_down else ButtonState.HELD
        return ButtonState.RELEASED if was_down else ButtonState.IDLE

    # --- OS呼び出しの窓口（テスト時にモンキーパッチ対象） ---

    def _read_cursor_pos(self) -> tuple[int, int]:
        point = _POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def _read_button_down(self, vk: int) -> bool:
        state = ctypes.windll.user32.GetAsyncKeyState(vk)
        return bool(state & 0x8000)

    def _now(self) -> float:
        return time.perf_counter()
