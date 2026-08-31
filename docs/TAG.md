# TAG.md — タグの正本

`docs/` 配下のリファレンスで使用するタグの一覧。新しいタグを追加する場合は必ずここに登録してから使うこと。
リファレンス側の記述形式は `<タグ名>`。

| タグ名 | 説明 | 主な対象 |
|---|---|---|
| `<mouse-input>` | マウスの状態（位置・移動量・ボタン）を **取得** する側の機能全般 | `mouse_input.py` |
| `<win-action>` | キーボード・マウス操作を Windows へ **代行実行** する側の機能全般 | `win_action.py` |
| `<polling>` | `update()` を呼び続けるポーリング方式に関わる機能 | `MouseInput.update` |
| `<history>` | リングバッファで保持する履歴の参照に関わる機能 | `get_history` / `get_button_history` |
| `<button-state>` | マウスボタンの4状態（PRESSED/HELD/RELEASED/IDLE）モデルに関わる機能 | `ButtonState` / `get_button_state` 等 |
| `<keyboard>` | キーボードキーの送出に関わる機能 | `Key` / `press_key` / `press_keys` / `key_down` / `key_up` |
| `<mouse-action>` | マウス操作（クリック・移動・スクロール）の送出に関わる機能 | `mouse_click` / `mouse_move` / `mouse_scroll` 等 |
| `<shortcut>` | 複数キーの組み合わせ（ショートカット）実行に関わる機能 | `press_keys` |
| `<special-use>` | 通常は使わない特殊用途API（解除忘れ等のリスクがあるため注意が必要） | `key_down` / `key_up` / `mouse_down` / `mouse_up` |
| `<constructor>` | クラスの初期化・パラメータに関わる機能 | `MouseInput.__init__` |
| `<enum>` / `<key-code>` | 仮想キーコードやボタン種別などの列挙・マッピング定義 | `Key` / `MouseButton` / `KEY_CODE_MAP` |
