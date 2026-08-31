"""mouse_input.MouseInput のユニットテスト。

GetCursorPos / GetAsyncKeyState への実アクセスは _read_cursor_pos /
_read_button_down のモンキーパッチで置き換え、状態遷移・履歴管理の
ロジックだけを検証する（実マウス状態に依存させない）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mouse_input import ButtonState, MouseButton, MouseInput  # noqa: E402
from mouse_input import _BUTTON_VK_CODES as MouseInput_VK  # noqa: E402


class _FakeMouseInput(MouseInput):
    """OSアクセスをスクリプト化した値に差し替えたテスト用サブクラス。"""

    def __init__(self, history_length: int = 100) -> None:
        super().__init__(history_length=history_length)
        self._positions: list[tuple[int, int]] = []
        self._button_down_sequences: dict[MouseButton, list[bool]] = {
            button: [] for button in MouseButton
        }
        self._tick = 0

    def queue_position(self, x: int, y: int) -> None:
        self._positions.append((x, y))

    def queue_button(self, button: MouseButton, is_down: bool) -> None:
        self._button_down_sequences[button].append(is_down)

    def _read_cursor_pos(self) -> tuple[int, int]:
        return self._positions[self._tick]

    def _read_button_down(self, vk: int) -> bool:
        # vk だけでは呼び出し中のボタンを判別できないため、
        # update() が MouseButton を列挙する順序に合わせてキューから取り出す。
        for button, sequence in self._button_down_sequences.items():
            if MouseInput_VK[button] == vk:
                return sequence[self._tick]
        raise AssertionError(f"unexpected vk: {vk}")

    def tick(self) -> None:
        self.update()
        self._tick += 1


class MouseInputDeltaTests(unittest.TestCase):
    def test_first_update_has_zero_delta_regardless_of_position(self) -> None:
        mouse = _FakeMouseInput()
        mouse.queue_position(500, 500)
        for button in MouseButton:
            mouse.queue_button(button, False)

        mouse.tick()

        self.assertEqual(mouse.get_delta(), (0, 0))
        self.assertEqual(mouse.get_position(), (500, 500))

    def test_delta_is_difference_from_previous_position(self) -> None:
        mouse = _FakeMouseInput()
        for x, y in [(100, 100), (110, 95), (90, 95)]:
            mouse.queue_position(x, y)
            for button in MouseButton:
                mouse.queue_button(button, False)

        mouse.tick()
        mouse.tick()
        self.assertEqual(mouse.get_delta(), (10, -5))

        mouse.tick()
        self.assertEqual(mouse.get_delta(), (-20, 0))


class MouseInputBeforeAnyUpdateTests(unittest.TestCase):
    def test_position_and_delta_are_none(self) -> None:
        mouse = MouseInput()
        self.assertIsNone(mouse.get_position())
        self.assertIsNone(mouse.get_delta())

    def test_history_is_empty(self) -> None:
        mouse = MouseInput()
        self.assertEqual(mouse.get_history(), [])
        self.assertEqual(mouse.get_button_history(MouseButton.LEFT), [])

    def test_button_state_defaults_to_idle(self) -> None:
        mouse = MouseInput()
        self.assertEqual(mouse.get_button_state(MouseButton.LEFT), ButtonState.IDLE)
        self.assertEqual(
            mouse.get_all_button_states(),
            {button: ButtonState.IDLE for button in MouseButton},
        )


class MouseInputButtonStateTransitionTests(unittest.TestCase):
    def test_full_press_release_cycle(self) -> None:
        # up, up, down, down, up, up -> IDLE, IDLE, PRESSED, HELD, RELEASED, IDLE
        sequence = [False, False, True, True, False, False]
        expected = [
            ButtonState.IDLE,
            ButtonState.IDLE,
            ButtonState.PRESSED,
            ButtonState.HELD,
            ButtonState.RELEASED,
            ButtonState.IDLE,
        ]

        mouse = _FakeMouseInput()
        for is_down in sequence:
            mouse.queue_position(0, 0)
            for button in MouseButton:
                mouse.queue_button(button, is_down if button is MouseButton.LEFT else False)

        actual = []
        for _ in sequence:
            mouse.tick()
            actual.append(mouse.get_button_state(MouseButton.LEFT))

        self.assertEqual(actual, expected)

    def test_buttons_are_tracked_independently(self) -> None:
        mouse = _FakeMouseInput()
        mouse.queue_position(0, 0)
        mouse.queue_button(MouseButton.LEFT, True)
        mouse.queue_button(MouseButton.RIGHT, False)
        mouse.queue_button(MouseButton.MIDDLE, False)
        mouse.queue_button(MouseButton.X1, False)
        mouse.queue_button(MouseButton.X2, False)

        mouse.tick()

        states = mouse.get_all_button_states()
        self.assertEqual(states[MouseButton.LEFT], ButtonState.PRESSED)
        self.assertEqual(states[MouseButton.RIGHT], ButtonState.IDLE)


class MouseInputHistoryTests(unittest.TestCase):
    def test_history_is_bounded_by_history_length(self) -> None:
        mouse = _FakeMouseInput(history_length=3)
        for i in range(5):
            mouse.queue_position(i, i)
            for button in MouseButton:
                mouse.queue_button(button, False)

        for _ in range(5):
            mouse.tick()

        history = mouse.get_history()
        self.assertEqual(len(history), 3)
        # 古い2件（x=0, x=1）は破棄され、直近3件（x=2,3,4）が残る
        self.assertEqual([snap.x for snap in history], [2, 3, 4])

    def test_get_history_with_n_returns_last_n_entries(self) -> None:
        mouse = _FakeMouseInput(history_length=10)
        for i in range(5):
            mouse.queue_position(i, 0)
            for button in MouseButton:
                mouse.queue_button(button, False)
        for _ in range(5):
            mouse.tick()

        last_two = mouse.get_history(n=2)
        self.assertEqual([snap.x for snap in last_two], [3, 4])

    def test_get_button_history_matches_per_tick_states(self) -> None:
        sequence = [False, True, True]
        mouse = _FakeMouseInput()
        for is_down in sequence:
            mouse.queue_position(0, 0)
            for button in MouseButton:
                mouse.queue_button(button, is_down if button is MouseButton.RIGHT else False)

        for _ in sequence:
            mouse.tick()

        history = mouse.get_button_history(MouseButton.RIGHT)
        self.assertEqual(
            history, [ButtonState.IDLE, ButtonState.PRESSED, ButtonState.HELD]
        )


class MouseInputConstructorTests(unittest.TestCase):
    def test_zero_history_length_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            MouseInput(history_length=0)

    def test_negative_history_length_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            MouseInput(history_length=-1)


if __name__ == "__main__":
    unittest.main()
