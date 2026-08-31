"""Windows へキーボード・マウス操作を代行実行するモジュール。

このクラスはジェスチャー判定などの基幹ロジックを持たない「実行専任」。
main.py 等から呼び出されたことをそのまま Windows に対して実行するだけ。

詳細な仕様は SPEC.md、使い方は docs/api/win_action.md を参照。
"""

from __future__ import annotations

import ctypes
import time
from enum import Enum, auto

from mouse_input import MouseButton


class Key(Enum):
    # 修飾キー
    CTRL = auto()
    SHIFT = auto()
    ALT = auto()
    WIN = auto()
    # 文字
    A = auto(); B = auto(); C = auto(); D = auto(); E = auto(); F = auto()
    G = auto(); H = auto(); I = auto(); J = auto(); K = auto(); L = auto()
    M = auto(); N = auto(); O = auto(); P = auto(); Q = auto(); R = auto()
    S = auto(); T = auto(); U = auto(); V = auto(); W = auto(); X = auto()
    Y = auto(); Z = auto()
    # 数字
    N0 = auto(); N1 = auto(); N2 = auto(); N3 = auto(); N4 = auto()
    N5 = auto(); N6 = auto(); N7 = auto(); N8 = auto(); N9 = auto()
    # ファンクションキー
    F1 = auto(); F2 = auto(); F3 = auto(); F4 = auto(); F5 = auto(); F6 = auto()
    F7 = auto(); F8 = auto(); F9 = auto(); F10 = auto(); F11 = auto(); F12 = auto()
    # 制御・ナビゲーション
    ENTER = auto()
    ESC = auto()
    TAB = auto()
    SPACE = auto()
    BACKSPACE = auto()
    DELETE = auto()
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    HOME = auto()
    END = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()


KEY_CODE_MAP: dict[Key, int] = {
    Key.CTRL: 0x11,
    Key.SHIFT: 0x10,
    Key.ALT: 0x12,
    Key.WIN: 0x5B,
    Key.A: 0x41, Key.B: 0x42, Key.C: 0x43, Key.D: 0x44, Key.E: 0x45, Key.F: 0x46,
    Key.G: 0x47, Key.H: 0x48, Key.I: 0x49, Key.J: 0x4A, Key.K: 0x4B, Key.L: 0x4C,
    Key.M: 0x4D, Key.N: 0x4E, Key.O: 0x4F, Key.P: 0x50, Key.Q: 0x51, Key.R: 0x52,
    Key.S: 0x53, Key.T: 0x54, Key.U: 0x55, Key.V: 0x56, Key.W: 0x57, Key.X: 0x58,
    Key.Y: 0x59, Key.Z: 0x5A,
    Key.N0: 0x30, Key.N1: 0x31, Key.N2: 0x32, Key.N3: 0x33, Key.N4: 0x34,
    Key.N5: 0x35, Key.N6: 0x36, Key.N7: 0x37, Key.N8: 0x38, Key.N9: 0x39,
    Key.F1: 0x70, Key.F2: 0x71, Key.F3: 0x72, Key.F4: 0x73, Key.F5: 0x74, Key.F6: 0x75,
    Key.F7: 0x76, Key.F8: 0x77, Key.F9: 0x78, Key.F10: 0x79, Key.F11: 0x7A, Key.F12: 0x7B,
    Key.ENTER: 0x0D,
    Key.ESC: 0x1B,
    Key.TAB: 0x09,
    Key.SPACE: 0x20,
    Key.BACKSPACE: 0x08,
    Key.DELETE: 0x2E,
    Key.UP: 0x26,
    Key.DOWN: 0x28,
    Key.LEFT: 0x25,
    Key.RIGHT: 0x27,
    Key.HOME: 0x24,
    Key.END: 0x23,
    Key.PAGE_UP: 0x21,
    Key.PAGE_DOWN: 0x22,
}


# --- SendInput 用 ctypes 構造体 ---

PUL = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        # mouseData は Win32 API 上は DWORD だが、MOUSEEVENTF_WHEEL/HWHEEL 時は
        # 符号付き値（負=下/左スクロール）として解釈されるため c_long にする。
        # c_ulong にすると Python 側の負値が unsigned のビットパターンに
        # ラップされ、呼び出し側からは巨大な正の数に見えてしまう。
        ("mouseData", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUT_UNION)]


_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1

_KEYEVENTF_KEYUP = 0x0002

_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_ABSOLUTE = 0x8000
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_MIDDLEDOWN = 0x0020
_MOUSEEVENTF_MIDDLEUP = 0x0040
_MOUSEEVENTF_XDOWN = 0x0080
_MOUSEEVENTF_XUP = 0x0100
_MOUSEEVENTF_WHEEL = 0x0800
_MOUSEEVENTF_HWHEEL = 0x1000

_XBUTTON1 = 0x0001
_XBUTTON2 = 0x0002

_WHEEL_DELTA = 120

_SM_CXSCREEN = 0
_SM_CYSCREEN = 1

_MOUSE_DOWN_FLAGS: dict[MouseButton, int] = {
    MouseButton.LEFT: _MOUSEEVENTF_LEFTDOWN,
    MouseButton.RIGHT: _MOUSEEVENTF_RIGHTDOWN,
    MouseButton.MIDDLE: _MOUSEEVENTF_MIDDLEDOWN,
    MouseButton.X1: _MOUSEEVENTF_XDOWN,
    MouseButton.X2: _MOUSEEVENTF_XDOWN,
}
_MOUSE_UP_FLAGS: dict[MouseButton, int] = {
    MouseButton.LEFT: _MOUSEEVENTF_LEFTUP,
    MouseButton.RIGHT: _MOUSEEVENTF_RIGHTUP,
    MouseButton.MIDDLE: _MOUSEEVENTF_MIDDLEUP,
    MouseButton.X1: _MOUSEEVENTF_XUP,
    MouseButton.X2: _MOUSEEVENTF_XUP,
}
_MOUSE_DATA: dict[MouseButton, int] = {
    MouseButton.X1: _XBUTTON1,
    MouseButton.X2: _XBUTTON2,
}


class WinAction:
    """キーボード・マウス操作を Windows に代行実行するクラス。"""

    DEFAULT_HOLD_SECONDS: float = 0.05

    # ------------------------------------------------------------------
    # キーボード操作の基本形（通常はこの2つだけで足りる）
    # ------------------------------------------------------------------

    def press_key(self, key: Key, hold_seconds: float = DEFAULT_HOLD_SECONDS) -> None:
        """1つのキーを押して離す。内部的には press_keys([key], hold_seconds)。"""
        self.press_keys([key], hold_seconds)

    def press_keys(
        self, keys: list[Key], hold_seconds: float = DEFAULT_HOLD_SECONDS
    ) -> None:
        """ショートカット実行用。

        keys[0] から順に押下し、hold_seconds 待ってから逆順
        （keys[-1] → keys[0]）で離す。

        これは厳密な「同時押し」ではない。実際には各キーのdownイベントを
        極短時間の間隔で連続送信し、複数キーが押下状態で重なっている時間を
        作り出すことで OS 側にショートカットとして認識させる仕組みである。
        """
        if not keys:
            raise ValueError("keys must not be empty")
        if hold_seconds < 0:
            raise ValueError("hold_seconds must not be negative")

        for key in keys:
            self.key_down(key)
        self._sleep(hold_seconds)
        for key in reversed(keys):
            self.key_up(key)

    # ------------------------------------------------------------------
    # キーボード操作（特殊用途・原則使用しない）
    # ------------------------------------------------------------------

    def key_down(self, key: Key) -> None:
        """押すだけで離さない。key_up() を自分で呼ばない限り押しっぱなしになる。

        解除忘れのリスクがあるため、長押し状態を作りたい等の明確な理由が
        ない限り使用しないこと。基本は press_key / press_keys を使う。
        """
        self._send_key_event(KEY_CODE_MAP[key], key_up=False)

    def key_up(self, key: Key) -> None:
        """離すだけ。key_down() とペアで、特別な理由がある場合のみ使用する。"""
        self._send_key_event(KEY_CODE_MAP[key], key_up=True)

    # ------------------------------------------------------------------
    # マウス操作
    # ------------------------------------------------------------------

    def mouse_click(
        self, button: MouseButton, hold_seconds: float = DEFAULT_HOLD_SECONDS
    ) -> None:
        """マウスボタンを押して離す。通常はこれを使う。"""
        if hold_seconds < 0:
            raise ValueError("hold_seconds must not be negative")
        self.mouse_down(button)
        self._sleep(hold_seconds)
        self.mouse_up(button)

    def mouse_down(self, button: MouseButton) -> None:
        """押すだけで離さない。key_down() と同様、原則使用しない特殊用途。"""
        self._send_mouse_button_event(button, is_down=True)

    def mouse_up(self, button: MouseButton) -> None:
        """離すだけ。mouse_down() とペアの特殊用途。"""
        self._send_mouse_button_event(button, is_down=False)

    def mouse_move(self, x: int, y: int, relative: bool = False) -> None:
        """マウスカーソルを移動する。

        relative=True の場合は現在位置からの相対移動量 (x, y) として扱う。
        relative=False（デフォルト）の場合は画面上の絶対座標として扱い、
        画面解像度をもとに 0-65535 の範囲へ正規化して送信する。
        """
        if relative:
            self._dispatch_mouse(dx=x, dy=y, flags=_MOUSEEVENTF_MOVE)
            return

        norm_x, norm_y = self._normalize_absolute(x, y)
        self._dispatch_mouse(
            dx=norm_x, dy=norm_y, flags=_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE
        )

    def mouse_scroll(self, amount: int, horizontal: bool = False) -> None:
        """ホイールスクロールを送出する。

        amount は「ノッチ数」（正=上/右、負=下/左）。内部で WHEEL_DELTA(120)
        を掛けて OS に渡す。
        """
        flags = _MOUSEEVENTF_HWHEEL if horizontal else _MOUSEEVENTF_WHEEL
        self._dispatch_mouse(dx=0, dy=0, flags=flags, mouse_data=amount * _WHEEL_DELTA)

    # ------------------------------------------------------------------
    # 正規化ロジック
    # ------------------------------------------------------------------

    def _normalize_absolute(self, x: int, y: int) -> tuple[int, int]:
        width, height = self._get_screen_size()
        norm_x = round(x * 65535 / max(width - 1, 1))
        norm_y = round(y * 65535 / max(height - 1, 1))
        return norm_x, norm_y

    # ------------------------------------------------------------------
    # 内部: SendInput 発行
    # ------------------------------------------------------------------

    def _send_key_event(self, vk: int, key_up: bool) -> None:
        flags = _KEYEVENTF_KEYUP if key_up else 0
        inp = _INPUT(
            type=_INPUT_KEYBOARD,
            union=_INPUT_UNION(ki=_KEYBDINPUT(vk, 0, flags, 0, None)),
        )
        self._dispatch(inp)

    def _send_mouse_button_event(self, button: MouseButton, is_down: bool) -> None:
        flags = (_MOUSE_DOWN_FLAGS if is_down else _MOUSE_UP_FLAGS)[button]
        mouse_data = _MOUSE_DATA.get(button, 0)
        self._dispatch_mouse(dx=0, dy=0, flags=flags, mouse_data=mouse_data)

    def _dispatch_mouse(
        self, dx: int, dy: int, flags: int, mouse_data: int = 0
    ) -> None:
        inp = _INPUT(
            type=_INPUT_MOUSE,
            union=_INPUT_UNION(mi=_MOUSEINPUT(dx, dy, mouse_data, flags, 0, None)),
        )
        self._dispatch(inp)

    # --- OS呼び出しの窓口（テスト時にモンキーパッチ対象） ---

    def _dispatch(self, inp: _INPUT) -> None:
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _get_screen_size(self) -> tuple[int, int]:
        width = ctypes.windll.user32.GetSystemMetrics(_SM_CXSCREEN)
        height = ctypes.windll.user32.GetSystemMetrics(_SM_CYSCREEN)
        return width, height

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
