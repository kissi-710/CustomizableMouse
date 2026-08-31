"""win_action.WinAction のユニットテスト。

実際に SendInput を呼ぶと本物のキー/クリックが送出されてしまうため、
_dispatch / _sleep / _get_screen_size をモンキーパッチして
「何が・どの順番で・どんな内容で呼ばれたか」だけを検証する。
実OSへは一切イベントを送らない。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mouse_input import MouseButton  # noqa: E402
from win_action import (  # noqa: E402
    KEY_CODE_MAP,
    Key,
    WinAction,
    _INPUT_KEYBOARD,
    _KEYEVENTF_KEYUP,
    _MOUSEEVENTF_ABSOLUTE,
    _MOUSEEVENTF_HWHEEL,
    _MOUSEEVENTF_LEFTDOWN,
    _MOUSEEVENTF_LEFTUP,
    _MOUSEEVENTF_MOVE,
    _MOUSEEVENTF_WHEEL,
    _MOUSEEVENTF_XDOWN,
    _WHEEL_DELTA,
    _XBUTTON1,
    _XBUTTON2,
)


class _RecordingWinAction(WinAction):
    """_dispatch を差し替えて発行された INPUT の内容を記録するテスト用サブクラス。"""

    def __init__(self, screen_size: tuple[int, int] = (1920, 1080)) -> None:
        self.dispatched: list[dict] = []
        self.sleeps: list[float] = []
        self._screen_size = screen_size

    def _dispatch(self, inp) -> None:  # type: ignore[override]
        if inp.type == _INPUT_KEYBOARD:
            self.dispatched.append(
                {"kind": "key", "vk": inp.union.ki.wVk, "flags": inp.union.ki.dwFlags}
            )
        else:
            self.dispatched.append(
                {
                    "kind": "mouse",
                    "dx": inp.union.mi.dx,
                    "dy": inp.union.mi.dy,
                    "mouseData": inp.union.mi.mouseData,
                    "flags": inp.union.mi.dwFlags,
                }
            )

    def _sleep(self, seconds: float) -> None:  # type: ignore[override]
        self.sleeps.append(seconds)

    def _get_screen_size(self) -> tuple[int, int]:  # type: ignore[override]
        return self._screen_size


class KeyCodeMapCompletenessTests(unittest.TestCase):
    def test_every_key_enum_member_has_a_vk_code(self) -> None:
        missing = [key for key in Key if key not in KEY_CODE_MAP]
        self.assertEqual(missing, [], f"KEY_CODE_MAP is missing entries for: {missing}")

    def test_no_duplicate_vk_codes(self) -> None:
        vk_codes = list(KEY_CODE_MAP.values())
        self.assertEqual(
            len(vk_codes), len(set(vk_codes)), "KEY_CODE_MAP contains duplicate VK codes"
        )


class KeyDownUpTests(unittest.TestCase):
    def test_key_down_sends_vk_without_keyup_flag(self) -> None:
        action = _RecordingWinAction()
        action.key_down(Key.A)
        self.assertEqual(
            action.dispatched, [{"kind": "key", "vk": KEY_CODE_MAP[Key.A], "flags": 0}]
        )

    def test_key_up_sends_vk_with_keyup_flag(self) -> None:
        action = _RecordingWinAction()
        action.key_up(Key.A)
        self.assertEqual(
            action.dispatched,
            [{"kind": "key", "vk": KEY_CODE_MAP[Key.A], "flags": _KEYEVENTF_KEYUP}],
        )


class PressKeyDelegatesToPressKeysTests(unittest.TestCase):
    def test_press_key_calls_press_keys_with_single_element_list(self) -> None:
        action = _RecordingWinAction()
        calls: list[tuple[list[Key], float]] = []
        action.press_keys = lambda keys, hold_seconds=WinAction.DEFAULT_HOLD_SECONDS: calls.append(
            (keys, hold_seconds)
        )

        action.press_key(Key.ENTER)

        self.assertEqual(calls, [([Key.ENTER], WinAction.DEFAULT_HOLD_SECONDS)])

    def test_press_key_forwards_custom_hold_seconds(self) -> None:
        action = _RecordingWinAction()
        calls: list[tuple[list[Key], float]] = []
        action.press_keys = lambda keys, hold_seconds=WinAction.DEFAULT_HOLD_SECONDS: calls.append(
            (keys, hold_seconds)
        )

        action.press_key(Key.ENTER, hold_seconds=0.3)

        self.assertEqual(calls, [([Key.ENTER], 0.3)])


class PressKeysOrderingTests(unittest.TestCase):
    def test_presses_in_order_and_releases_in_reverse_order(self) -> None:
        action = _RecordingWinAction()
        action.press_keys([Key.CTRL, Key.SHIFT, Key.ESC])

        vk_sequence = [event["vk"] for event in action.dispatched]
        flag_sequence = [event["flags"] for event in action.dispatched]

        expected_vks = [
            KEY_CODE_MAP[Key.CTRL],
            KEY_CODE_MAP[Key.SHIFT],
            KEY_CODE_MAP[Key.ESC],
            KEY_CODE_MAP[Key.ESC],
            KEY_CODE_MAP[Key.SHIFT],
            KEY_CODE_MAP[Key.CTRL],
        ]
        self.assertEqual(vk_sequence, expected_vks)
        self.assertEqual(flag_sequence, [0, 0, 0, _KEYEVENTF_KEYUP, _KEYEVENTF_KEYUP, _KEYEVENTF_KEYUP])

    def test_empty_key_list_raises_value_error(self) -> None:
        action = _RecordingWinAction()
        with self.assertRaises(ValueError):
            action.press_keys([])

    def test_negative_hold_seconds_raises_value_error(self) -> None:
        action = _RecordingWinAction()
        with self.assertRaises(ValueError):
            action.press_keys([Key.A], hold_seconds=-0.1)

    def test_default_hold_seconds_used_when_omitted(self) -> None:
        action = _RecordingWinAction()
        action.press_keys([Key.A])
        self.assertEqual(action.sleeps, [WinAction.DEFAULT_HOLD_SECONDS])

    def test_custom_hold_seconds_is_forwarded_to_sleep(self) -> None:
        action = _RecordingWinAction()
        action.press_keys([Key.A], hold_seconds=1.5)
        self.assertEqual(action.sleeps, [1.5])


class MouseButtonEventTests(unittest.TestCase):
    def test_mouse_down_left_uses_leftdown_flag(self) -> None:
        action = _RecordingWinAction()
        action.mouse_down(MouseButton.LEFT)
        self.assertEqual(
            action.dispatched,
            [{"kind": "mouse", "dx": 0, "dy": 0, "mouseData": 0, "flags": _MOUSEEVENTF_LEFTDOWN}],
        )

    def test_mouse_up_left_uses_leftup_flag(self) -> None:
        action = _RecordingWinAction()
        action.mouse_up(MouseButton.LEFT)
        self.assertEqual(
            action.dispatched,
            [{"kind": "mouse", "dx": 0, "dy": 0, "mouseData": 0, "flags": _MOUSEEVENTF_LEFTUP}],
        )

    def test_mouse_down_x1_sets_mouse_data_to_xbutton1(self) -> None:
        action = _RecordingWinAction()
        action.mouse_down(MouseButton.X1)
        event = action.dispatched[0]
        self.assertEqual(event["flags"], _MOUSEEVENTF_XDOWN)
        self.assertEqual(event["mouseData"], _XBUTTON1)

    def test_mouse_down_x2_sets_mouse_data_to_xbutton2(self) -> None:
        action = _RecordingWinAction()
        action.mouse_down(MouseButton.X2)
        event = action.dispatched[0]
        self.assertEqual(event["mouseData"], _XBUTTON2)

    def test_mouse_click_is_down_then_up_with_hold(self) -> None:
        from win_action import _MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP

        action = _RecordingWinAction()
        action.mouse_click(MouseButton.RIGHT, hold_seconds=0.2)

        flag_sequence = [event["flags"] for event in action.dispatched]
        self.assertEqual(flag_sequence, [_MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP])
        self.assertEqual(action.sleeps, [0.2])


class MouseMoveTests(unittest.TestCase):
    def test_relative_move_passes_dx_dy_through_unchanged(self) -> None:
        action = _RecordingWinAction()
        action.mouse_move(15, -7, relative=True)
        event = action.dispatched[0]
        self.assertEqual((event["dx"], event["dy"]), (15, -7))
        self.assertEqual(event["flags"], _MOUSEEVENTF_MOVE)

    def test_absolute_move_top_left_normalizes_to_zero(self) -> None:
        action = _RecordingWinAction(screen_size=(1920, 1080))
        action.mouse_move(0, 0, relative=False)
        event = action.dispatched[0]
        self.assertEqual((event["dx"], event["dy"]), (0, 0))
        self.assertEqual(event["flags"], _MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE)

    def test_absolute_move_bottom_right_normalizes_to_max(self) -> None:
        width, height = 1920, 1080
        action = _RecordingWinAction(screen_size=(width, height))
        action.mouse_move(width - 1, height - 1, relative=False)
        event = action.dispatched[0]
        self.assertEqual((event["dx"], event["dy"]), (65535, 65535))


class MouseScrollTests(unittest.TestCase):
    def test_vertical_scroll_multiplies_by_wheel_delta(self) -> None:
        action = _RecordingWinAction()
        action.mouse_scroll(2)
        event = action.dispatched[0]
        self.assertEqual(event["mouseData"], 2 * _WHEEL_DELTA)
        self.assertEqual(event["flags"], _MOUSEEVENTF_WHEEL)

    def test_horizontal_scroll_uses_hwheel_flag(self) -> None:
        action = _RecordingWinAction()
        action.mouse_scroll(-1, horizontal=True)
        event = action.dispatched[0]
        self.assertEqual(event["mouseData"], -1 * _WHEEL_DELTA)
        self.assertEqual(event["flags"], _MOUSEEVENTF_HWHEEL)


if __name__ == "__main__":
    unittest.main()
