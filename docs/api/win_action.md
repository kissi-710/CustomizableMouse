# API リファレンス — `win_action.py`

`<win-action>`

キーボード・マウス操作を Windows へ代行実行するモジュール。
ジェスチャー判定などの基幹ロジックは持たず、呼び出されたことをそのまま実行するだけ（権限委譲）。
仕様の全体像は [SPEC.md](../../SPEC.md) を参照。

---

## Enum: `Key`

`<win-action>` `<keyboard>` `<enum>`

送出可能なキーのシンボル一覧（修飾キー・文字・数字・ファンクション・制御/ナビゲーションキー）。

```python
class Key(Enum):
    CTRL = auto(); SHIFT = auto(); ALT = auto(); WIN = auto()
    A = auto(); ...; Z = auto()
    N0 = auto(); ...; N9 = auto()
    F1 = auto(); ...; F12 = auto()
    ENTER = auto(); ESC = auto(); TAB = auto(); SPACE = auto()
    BACKSPACE = auto(); DELETE = auto()
    UP = auto(); DOWN = auto(); LEFT = auto(); RIGHT = auto()
    HOME = auto(); END = auto(); PAGE_UP = auto(); PAGE_DOWN = auto()
```

- **どういうときに使うか**: `press_key` / `press_keys` / `key_down` / `key_up` の引数として使う。
- **拡張したい場合**: 必要なキーが無ければ `Key` にメンバーを追加し、`KEY_CODE_MAP` にも
  対応する仮想キーコード(VK)を追加する。2つがずれると `KeyCodeMapCompletenessTests` の
  テスト（`test/test_win_action.py`）が失敗して検知できる。

## `KEY_CODE_MAP: dict[Key, int]`

`<win-action>` `<keyboard>` `<key-code>`

`Key` のシンボルと実際の仮想キーコード(VK)を結び付ける辞書。

- **どういうときに使うか**: 通常は直接使わない（`WinAction` の内部で参照される）。
  将来 `config.json` 等へキーコードの出所を外出しする場合は、この辞書の構築元だけを
  差し替える（詳細は SPEC.md 6章の設計メモを参照）。

---

## クラス: `WinAction`

`<win-action>`

キーボード・マウス操作を実行する唯一の入口。基本的には
**`press_key` / `press_keys` / `mouse_click` の3つだけで用が足りる**ように設計されている。

### `DEFAULT_HOLD_SECONDS: float = 0.05`

`press_key` / `press_keys` / `mouse_click` で `hold_seconds` を省略した時に使われるデフォルト値（秒）。

---

### `press_key(self, key: Key, hold_seconds: float = DEFAULT_HOLD_SECONDS) -> None`

`<win-action>` `<keyboard>`

- **概要**: 1つのキーを押して離す。内部実装は `press_keys([key], hold_seconds)` を呼ぶだけ
  （挙動は完全に `press_keys` に委譲されている）。
- **引数**:
  - `key` — 押す `Key`。
  - `hold_seconds` — 押してから離すまでの待ち時間（秒）。省略時は `DEFAULT_HOLD_SECONDS`。
- **どういうときに使うか**: 単発のキー入力を送りたい時。基本はこれを使う。
- **使用例**:
  ```python
  from win_action import WinAction, Key

  action = WinAction()
  action.press_key(Key.ENTER)
  ```

### `press_keys(self, keys: list[Key], hold_seconds: float = DEFAULT_HOLD_SECONDS) -> None`

`<win-action>` `<keyboard>` `<shortcut>`

- **概要**: ショートカット実行用。`keys[0]` から順に押下し、`hold_seconds` 待ってから
  逆順（`keys[-1]` → `keys[0]`）で離す。
- **引数**:
  - `keys` — 押す `Key` のリスト。**空リストは `ValueError`**。
  - `hold_seconds` — 最後のキーを押してから離し始めるまでの待ち時間（秒）。
    省略時は `DEFAULT_HOLD_SECONDS`。**負の値は `ValueError`**。
- **戻り値**: なし
- **重要な注意点**:
  - これは厳密な「同時押し」ではない。実際には各キーの down イベントを極短時間の間隔で
    連続送信し、複数キーが押下状態で重なっている時間を作り出すことで OS 側に
    ショートカットとして認識させる仕組みである。
  - 押し忘れ・離し忘れを防ぐため、通常のショートカット実行にはこの関数（または `press_key`）
    を使い、`key_down` / `key_up` は特別な理由がない限り使わないこと。
- **どういうときに使うか**: `Ctrl+C` のような複数キーの組み合わせを実行したい時。
- **使用例**:
  ```python
  # Ctrl+Shift+Esc（タスクマネージャーを開くショートカット）
  action.press_keys([Key.CTRL, Key.SHIFT, Key.ESC])

  # 保持時間を長めにしたい場合
  action.press_keys([Key.CTRL, Key.C], hold_seconds=0.1)
  ```

---

### `key_down(self, key: Key) -> None`

`<win-action>` `<keyboard>` `<special-use>`

- **概要**: 押すだけで離さない。
- **引数**: `key` — 押す `Key`。
- **注意**: 呼び出し側が責任を持って `key_up()` を呼ばない限り、キーが押しっぱなしの
  ままアプリケーションが終了するなどして「解除忘れ」が起きるリスクがある。
  **長押し状態を意図的に作りたい等の明確な理由がない限り使用しないこと。**
  通常は `press_key` / `press_keys` を使う。
- **使用例**:
  ```python
  # 例: Shiftを押している間だけ別の操作をしたい、等の特殊なケースのみ
  action.key_down(Key.SHIFT)
  try:
      ...  # Shiftを押しっぱなしにしたい処理
  finally:
      action.key_up(Key.SHIFT)  # 必ず対で呼ぶこと
  ```

### `key_up(self, key: Key) -> None`

`<win-action>` `<keyboard>` `<special-use>`

- **概要**: 離すだけ。`key_down()` とペアで、特別な理由がある場合のみ使用する。
- **引数**: `key` — 離す `Key`。

---

### `mouse_click(self, button: MouseButton, hold_seconds: float = DEFAULT_HOLD_SECONDS) -> None`

`<win-action>` `<mouse-action>`

- **概要**: マウスボタンを押して離す（`mouse_down` → 待機 → `mouse_up`）。通常はこれを使う。
- **引数**:
  - `button` — `mouse_input.MouseButton`（`LEFT`/`RIGHT`/`MIDDLE`/`X1`/`X2`）。
  - `hold_seconds` — 押してから離すまでの待ち時間（秒）。省略時は `DEFAULT_HOLD_SECONDS`。
    **負の値は `ValueError`**。
- **使用例**:
  ```python
  from mouse_input import MouseButton

  action.mouse_click(MouseButton.LEFT)
  ```

### `mouse_down(self, button: MouseButton) -> None` / `mouse_up(self, button: MouseButton) -> None`

`<win-action>` `<mouse-action>` `<special-use>`

- **概要**: `key_down`/`key_up` と同様、押すだけ・離すだけの特殊用途。原則使用しない。
- **使用例**:
  ```python
  # 例: ドラッグ操作のように、押しっぱなしのまま別の処理を挟みたい場合のみ
  action.mouse_down(MouseButton.LEFT)
  action.mouse_move(500, 500)
  action.mouse_up(MouseButton.LEFT)
  ```

### `mouse_move(self, x: int, y: int, relative: bool = False) -> None`

`<win-action>` `<mouse-action>`

- **概要**: マウスカーソルを移動する。
- **引数**:
  - `x`, `y` —
    - `relative=True` の場合: 現在位置からの相対移動量。
    - `relative=False`（デフォルト）の場合: 画面上の絶対座標。内部で画面解像度をもとに
      0–65535 の範囲へ正規化して送信する。
  - `relative` — 相対移動か絶対移動かを選択する。
- **使用例**:
  ```python
  action.mouse_move(10, -5, relative=True)   # 現在位置から右へ10px, 上へ5px
  action.mouse_move(960, 540)                # 画面上の絶対座標へ
  ```
- **既知の制限**: 絶対座標モードは現状プライマリモニタの解像度
  (`GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)`) のみを基準に正規化しており、
  マルチモニタ環境のセカンダリモニタや、プライマリより左/上に配置された
  モニタの負の座標には対応していない。また画面範囲外の `x`/`y` を渡した場合の
  クランプ処理も未実装。詳細は [ISSUE.md](../../ISSUE.md) を参照。

### `mouse_scroll(self, amount: int, horizontal: bool = False) -> None`

`<win-action>` `<mouse-action>`

- **概要**: ホイールスクロールを送出する。
- **引数**:
  - `amount` — スクロールの「ノッチ数」。正=上/右方向、負=下/左方向。内部で
    `WHEEL_DELTA(120)` を掛けて OS に渡す。
  - `horizontal` — `True` で水平スクロール（`Shift+ホイール`相当）、`False`（デフォルト）で垂直スクロール。
- **使用例**:
  ```python
  action.mouse_scroll(1)               # 上へ1ノッチ
  action.mouse_scroll(-2)              # 下へ2ノッチ
  action.mouse_scroll(1, horizontal=True)  # 右へ1ノッチ
  ```
