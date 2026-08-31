# SPEC.md — CustomizableMouse

マウスジェスチャー機能のための土台となる、Windows API (ctypes) ラッパー2モジュールの仕様。

## 1. 概要

マウスポインタの移動・ボタン状態を監視してジェスチャーを判定する機能を作るにあたり、
`ctypes` による Win32 API の生呼び出しを直接書くのは煩雑なため、以下の2クラスで隠蔽する。

| ファイル | 役割 |
|---|---|
| `mouse_input.py` | マウスの状態（位置・移動量・ボタン）を **取得** するクラス |
| `win_action.py`  | キーボード・マウス操作を Windows へ **代行実行** するクラス |

ジェスチャー判定ロジックそのもの（4方向判定など）はこの2ファイルの責務外。
`main.py` 側が `mouse_input` から生データを取得し、判定した結果を `win_action` に渡して実行する。

```
main.py
 ├─ mouse_input.MouseInput   … 状態を読む（ポーリング）
 └─ win_action.WinAction     … アクションを実行する（権限委譲）
```

## 2. 前提・制約

- 標準ライブラリのみ使用可（`ctypes` / `enum` / `dataclasses` / `collections` / `time` のみ）。
  `pywin32` / `pynput` 等のサードパーティは不可。
- Windows専用（`ctypes.windll` を使用）。
- `mouse_input.py` はフックではなく **ポーリング方式**。
  `main.py` が任意の間隔（想定 0.02秒）で `update()` を呼び続け、内部状態を更新する。
  クラス自身はタイマーやスレッドを持たない（呼び出しタイミングは呼び出し側の責任）。

## 3. `mouse_input.py`

### 3.1 Enum定義

```python
class MouseButton(Enum):
    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()
    X1 = auto()   # サイドボタン1
    X2 = auto()   # サイドボタン2

class ButtonState(Enum):
    PRESSED  = auto()  # 今tick押された（立ち上がりエッジ）
    HELD     = auto()  # 押され続けている
    RELEASED = auto()  # 今tick離された（立ち下がりエッジ）
    IDLE     = auto()  # 離され続けている
```

状態遷移は前回tickとの比較で決定する:

| 前回 | 今回 | 結果 |
|---|---|---|
| 離 | 離 | IDLE |
| 離 | 押 | PRESSED |
| 押 | 押 | HELD |
| 押 | 離 | RELEASED |

初回 `update()` 呼び出し時は「前回」が存在しないため、離とみなす（押されていれば `PRESSED` になる）。

### 3.2 データ構造（同期リングバッファ）

移動履歴とボタン履歴は同じtickで1レコードにまとめ、`collections.deque(maxlen=history_length)` で保持する。
インデックス／タイムスタンプが常に同期しているため、「ボタン押下中の移動軌跡」のような相関を後から取り出しやすい。

```python
@dataclass(frozen=True)
class MouseSnapshot:
    timestamp: float                          # time.perf_counter()
    x: int
    y: int
    dx: int                                    # 前回update()からの移動量（生ベクトル）
    dy: int
    buttons: dict[MouseButton, ButtonState]
```

方向判定（4方向化など）は行わない。`dx, dy` の生データを渡すところまでが本クラスの責務。

### 3.3 クラス `MouseInput`

```python
class MouseInput:
    def __init__(self, history_length: int = 100): ...
    # history_length は1以上の整数が必須。0以下は ValueError
    # （0だと履歴が一切残らず検知不能になる事故を防ぐため）。

    def update(self) -> None:
        """GetCursorPos / GetAsyncKeyState を叩き、内部状態・履歴を1tick分更新する。"""

    # --- 現在値 ---
    def get_position(self) -> tuple[int, int]: ...
    def get_delta(self) -> tuple[int, int]: ...
    def get_button_state(self, button: MouseButton) -> ButtonState: ...
    def get_all_button_states(self) -> dict[MouseButton, ButtonState]: ...

    # --- 履歴（古い→新しい順） ---
    def get_history(self, n: int | None = None) -> list[MouseSnapshot]: ...
    def get_button_history(self, button: MouseButton, n: int | None = None) -> list[ButtonState]: ...
```

`n` を指定すると直近 `n` 件のみ返す（例: 0.2秒分 = `n=10` @0.02秒間隔）。省略時は保持している全履歴。

`get_all_button_states()` は最新tickにおける **5ボタン全ての状態をまとめて** 返す
（内容は最新 `MouseSnapshot.buttons` と同じ）。個別ボタンを1つずつ `get_button_state()` で
問い合わせる代わりに、「今どのボタンが何状態か」を一度に把握したい場合に使う。

### 3.4 内部実装方針

- 位置取得: `ctypes.windll.user32.GetCursorPos(byref(POINT))`
- ボタン状態取得: `ctypes.windll.user32.GetAsyncKeyState(vk)`
  - `GetAsyncKeyState` はマウスボタンのVK定数（`VK_LBUTTON=0x01` 等）も受け付けるため、
    キーボードと同じAPIで5ボタンすべて拾える。
- `update()` を一度も呼んでいない（履歴が0件の）時点での各ゲッターの戻り値は以下の通り:
  - `get_position()` / `get_delta()` → `None`
  - `get_history()` / `get_button_history()` → 空リスト
  - `get_button_state()` / `get_all_button_states()` → `ButtonState.IDLE`
    （「まだ押されていない」とみなせる安全なデフォルト値のため）

## 4. `win_action.py`

### 4.1 目的

キーボード操作・マウス操作を Windows に対して代行実行する **実行専任** クラス。
ジェスチャー判定などの基幹ロジックは持たず、呼び出されたら実行するだけ（権限委譲）。

### 4.2 Key Enum + VKコード辞書

```python
class Key(Enum):
    # 修飾キー
    CTRL = auto(); SHIFT = auto(); ALT = auto(); WIN = auto()
    # 文字/数字（A-Z, 0-9）
    A = auto(); B = auto(); ...; Z = auto()
    N0 = auto(); N1 = auto(); ...; N9 = auto()
    # ファンクション
    F1 = auto(); ...; F12 = auto()
    # 制御・ナビゲーション
    ENTER = auto(); ESC = auto(); TAB = auto(); SPACE = auto()
    BACKSPACE = auto(); DELETE = auto()
    UP = auto(); DOWN = auto(); LEFT = auto(); RIGHT = auto()
    HOME = auto(); END = auto(); PAGE_UP = auto(); PAGE_DOWN = auto()

KEY_CODE_MAP: dict[Key, int] = {
    Key.CTRL: 0x11,   # VK_CONTROL
    Key.SHIFT: 0x10,  # VK_SHIFT
    Key.A: 0x41,
    # ...
}
```

初期実装では利用予定のキーのみ定義し、必要になったら `Key` に追加する。

マウスボタンは `mouse_input.MouseButton` をそのまま import して使う（重複定義しない）。

### 4.3 クラス `WinAction`

```python
class WinAction:
    DEFAULT_HOLD_SECONDS: float = 0.05   # 押してから離すまでのデフォルト保持時間

    # --- キーボード操作の基本形（通常はこの2つだけで足りる） ---
    def press_key(self, key: Key, hold_seconds: float = DEFAULT_HOLD_SECONDS) -> None:
        """内部実装は press_keys([key], hold_seconds) を呼ぶだけ。"""

    def press_keys(self, keys: list[Key], hold_seconds: float = DEFAULT_HOLD_SECONDS) -> None:
        """
        ショートカット実行用。keys[0] から順に押下し、hold_seconds 待ってから
        逆順（keys[-1] → keys[0]）で離す。
        例: press_keys([Key.CTRL, Key.SHIFT, Key.ESC])

        注意:
        - これは厳密な「同時押し」ではない。実際には各キーのdownイベントを
          極短時間の間隔で連続送信し、複数キーが押下状態で重なっている時間を
          作り出すことでOS側にショートカットとして認識させる仕組みである。
        - hold_seconds は「最後のキーを押してから離し始めるまで」の保持時間。
          省略時は DEFAULT_HOLD_SECONDS を使う。
        """

    # --- 特殊用途（原則使用しない） ---
    def key_down(self, key: Key) -> None:
        """
        押すだけで離さない。呼び出し側が明示的に key_up() を呼ぶまで
        押しっぱなしになる。解除忘れ（キーが押されたまま残るバグ）の
        リスクがあるため、長押し状態を作りたい等の明確な理由がない限り
        使用しないこと。基本は press_key / press_keys を使う。
        """

    def key_up(self, key: Key) -> None:
        """離すだけ。key_down() とペアで、特別な理由がある場合のみ使用する。"""

    # --- マウス操作（キーボードと同じ考え方） ---
    def mouse_move(self, x: int, y: int, relative: bool = False) -> None: ...

    def mouse_click(self, button: MouseButton, hold_seconds: float = DEFAULT_HOLD_SECONDS) -> None:
        """内部実装は mouse_down → hold_seconds待機 → mouse_up。通常はこれを使う。"""

    def mouse_down(self, button: MouseButton) -> None:
        """押すだけで離さない。key_down() と同様、原則使用しない特殊用途。"""

    def mouse_up(self, button: MouseButton) -> None:
        """離すだけ。mouse_down() とペアの特殊用途。"""

    def mouse_scroll(self, amount: int, horizontal: bool = False) -> None: ...
```

- 通常の呼び出し側は `press_key` / `press_keys` / `mouse_click` だけを使う。
- `key_down` / `key_up` / `mouse_down` / `mouse_up` は「離し忘れ」の危険があるため、
  長押し状態を意図的に作りたい場合など特別な理由がある時だけ使う特殊用途とする。

### 4.4 内部実装方針

- `ctypes.windll.user32.SendInput` を使用。
- `INPUT` / `KEYBDINPUT` / `MOUSEINPUT` / `ctypes.Union` を本ファイル内に定義する
  （`mouse_input.py` とは別ファイルなので構造体定義は共有せず、それぞれで完結させる）。
- `mouse_move(..., relative=False)`（絶対座標指定）は `MOUSEEVENTF_ABSOLUTE` 用に
  `GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)` で画面解像度を取得し 0–65535 に正規化する。
- キー押下は `KEYEVENTF_KEYUP` フラグの有無で down/up を表現する。

## 5. `main.py`（動作確認用エントリポイント）

現時点の `main.py` はジェスチャー判定を行わず、`mouse_input.py` の動作確認用として
以下の役割のみを持つ（`win_action.py` はまだ呼び出さない）。

1. ループに入る前に `test/run_tests.py` を実行し、テストが1件でも失敗していたら
   エラーメッセージを出して起動を中止する（`sys.exit(1)`）。
2. `MouseInput.update()` を `POLL_INTERVAL_SECONDS`（0.02秒）間隔で呼び続けるループ。
3. 毎ループ `get_delta()` を見て、`(0, 0)` でなければ移動量を print する。
4. 毎ループ `get_all_button_states()` を見て、`PRESSED` / `RELEASED` のボタンだけ
   print する（`IDLE`/`HELD` は出力しない — ターミナルが埋もれるため）。

```python
mouse = MouseInput(history_length=100)

while True:
    mouse.update()

    delta = mouse.get_delta()
    if delta is not None and delta != (0, 0):
        dx, dy = delta
        print(f"[MOVE] dx={dx:+d} dy={dy:+d}")

    for button, state in mouse.get_all_button_states().items():
        if state in (ButtonState.PRESSED, ButtonState.RELEASED):
            print(f"[BUTTON] {button.name}: {state.name}")

    time.sleep(0.02)
```

将来ジェスチャー判定ロジックを追加する際は、上記ループの中で `get_delta()` /
`get_history()` を使って方向を判定し、確定したら `WinAction` の
`press_key` / `press_keys` / `mouse_click` を呼び出す形になる想定。

## 6. 設計メモ

### `Key` Enum + `dict[Key, int]` 分離について

シンボル名（`Key` のメンバー）と実値（VKコード int）を分離する設計は妥当。
呼び出し側コードは常に `Key.CTRL` のようなシンボルで書き、`KEY_CODE_MAP` だけを
差し替えれば値の出所を変更できる。

- 将来 `config.json` に値を外出しする場合: `KEY_CODE_MAP` を JSON からロードした
  `dict[str, int]` を経由して構築し直す形になる（`Key` メンバー自体は Python の列挙なので
  「どのキー名が存在するか」は結局コードで定義する必要がある — JSON側で自由にキー名を
  追加することはできない点は留意）。
- 完全にデータ駆動にしたい場合は `Key` を `Enum` ではなく文字列（キー名の集合をJSON側で管理）に
  する設計もあり得るが、その場合 IDE補完や typo検出が失われるトレードオフがある。
  現状の要件（将来的な移行先が未確定）では **Enum + dict のままで良い**、変更が必要になった時点で
  `KEY_CODE_MAP` の構築元だけ差し替えるのが最小コストと判断する。

## 7. スコープ外（本SPECでは扱わない）

- ジェスチャー方向の判定アルゴリズム（4方向化など）
- ジェスチャー〜アクションのマッピング設定（config.json等）
- `main.py` のポーリングループ本体
