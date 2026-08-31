# API リファレンス — `mouse_input.py`

`<mouse-input>` `<polling>`

マウスの位置・移動量・ボタン状態をポーリングで取得するモジュール。
仕様の全体像は [SPEC.md](../../SPEC.md) を参照。

---

## Enum: `MouseButton`

`<mouse-input>` `<enum>`

対象とするマウスボタンの種別。

```python
class MouseButton(Enum):
    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()
    X1 = auto()   # サイドボタン1
    X2 = auto()   # サイドボタン2
```

- **どういうときに使うか**: `get_button_state()` などボタンを指定する全ての関数の引数として使う。

---

## Enum: `ButtonState`

`<mouse-input>` `<button-state>` `<enum>`

ある1tickにおけるボタンの状態。

```python
class ButtonState(Enum):
    PRESSED  = auto()  # 今tick押された（立ち上がりエッジ）
    HELD     = auto()  # 押され続けている
    RELEASED = auto()  # 今tick離された（立ち下がりエッジ）
    IDLE     = auto()  # 離され続けている
```

- **どういうときに使うか**: 「クリックされた瞬間だけ」を検知したいなら `PRESSED`、
  「離された瞬間だけ」なら `RELEASED` を見る。ドラッグ中かどうかを判定したいなら
  `HELD` を含めて判定する。

---

## dataclass: `MouseSnapshot`

`<mouse-input>` `<history>`

1回の `update()` 時点の状態をまとめたレコード。`get_history()` の要素型。

```python
@dataclass(frozen=True)
class MouseSnapshot:
    timestamp: float                          # time.perf_counter()
    x: int
    y: int
    dx: int                                    # 前回update()からの移動量
    dy: int
    buttons: dict[MouseButton, ButtonState]
```

- **引数/フィールド**:
  - `timestamp`: `time.perf_counter()` によるモノトニックな時刻。実時間の壁時計ではなく
    「経過時間の比較」用（tick間の間隔を測るのに使う）。
  - `x`, `y`: スクリーン座標での絶対位置。
  - `dx`, `dy`: 直前の `update()` からの移動量（生ベクトル）。方向の分類（4方向化など）は
    このモジュールでは行わない — 呼び出し側の責務。
  - `buttons`: そのtick時点での5ボタン全ての `ButtonState`。
- **どういうときに使うか**: `get_history()` で過去の軌跡をまとめて解析したい時。

---

## クラス: `MouseInput`

`<mouse-input>` `<polling>`

### `__init__(self, history_length: int = 100)`

`<constructor>`

- **引数**:
  - `history_length` (`int`, デフォルト `100`): 保持する履歴の最大件数。
    `update()` を 0.02秒間隔で呼ぶ想定なら `100` で直近1秒分。
    **1以上の整数が必須。0以下を渡すと `ValueError`**
    （0だと履歴が一切残らず検知不能になる事故を防ぐため）。
- **使用例**:
  ```python
  from mouse_input import MouseInput

  mouse = MouseInput(history_length=100)
  ```

### `update(self) -> None`

`<mouse-input>` `<polling>`

- **概要**: `GetCursorPos` / `GetAsyncKeyState` を1回ずつ読み取り、内部状態と履歴を1tick分更新する。
  このクラス自身はタイマーやスレッドを持たないため、呼び出し側が任意の間隔で呼び続ける必要がある。
- **引数**: なし
- **戻り値**: なし
- **どういうときに使うか**: メインループの毎ループで必ず呼ぶ。呼ばない限り状態は一切更新されない。
- **使用例**:
  ```python
  import time

  mouse = MouseInput()
  while True:
      mouse.update()
      # ここで get_delta() 等を使って状態を読む
      time.sleep(0.02)
  ```

### `get_position(self) -> tuple[int, int] | None`

`<mouse-input>`

- **概要**: 最新tickでのマウスの絶対座標 `(x, y)` を返す。
- **戻り値**: `update()` を一度も呼んでいなければ `None`。
- **どういうときに使うか**: ジェスチャーの起点座標を記録したい時など。
- **使用例**:
  ```python
  mouse.update()
  pos = mouse.get_position()
  if pos is not None:
      x, y = pos
  ```

### `get_delta(self) -> tuple[int, int] | None`

`<mouse-input>`

- **概要**: 最新tickでの移動量 `(dx, dy)` を返す（前回 `update()` からの差分・生ベクトル）。
- **戻り値**: `update()` を一度も呼んでいなければ `None`。初回 `update()` 直後は `(0, 0)`
  （前回位置が存在しないため）。
- **どういうときに使うか**: ジェスチャー判定（方向の分類など）の入力として、毎tickこれを使う。
- **使用例**:
  ```python
  mouse.update()
  delta = mouse.get_delta()
  if delta is not None and delta != (0, 0):
      dx, dy = delta
      print(f"dx={dx}, dy={dy}")
  ```

### `get_button_state(self, button: MouseButton) -> ButtonState`

`<mouse-input>` `<button-state>`

- **概要**: 指定した1ボタンの最新tickでの状態を返す。
- **引数**: `button` — 状態を知りたい `MouseButton`。
- **戻り値**: `ButtonState`。`update()` を一度も呼んでいなければ `ButtonState.IDLE`
  （「まだ押されていない」とみなせる安全なデフォルト値）。
- **どういうときに使うか**: 特定の1ボタンだけ監視したい場合。
- **使用例**:
  ```python
  from mouse_input import MouseButton, ButtonState

  mouse.update()
  if mouse.get_button_state(MouseButton.LEFT) is ButtonState.PRESSED:
      print("左クリックされた瞬間")
  ```

### `get_all_button_states(self) -> dict[MouseButton, ButtonState]`

`<mouse-input>` `<button-state>`

- **概要**: 最新tickにおける **5ボタン全ての状態をまとめて** 返す。
- **引数**: なし
- **戻り値**: `dict[MouseButton, ButtonState]`。`update()` を一度も呼んでいなければ
  全ボタン `ButtonState.IDLE` の辞書。
- **どういうときに使うか**: 個別に `get_button_state()` を5回呼ぶ代わりに、
  「今どのボタンが何状態か」を一度に把握したい時（例: 毎tickのログ出力）。
- **使用例**:
  ```python
  mouse.update()
  for button, state in mouse.get_all_button_states().items():
      if state in (ButtonState.PRESSED, ButtonState.RELEASED):
          print(f"{button.name}: {state.name}")
  ```

### `get_history(self, n: int | None = None) -> list[MouseSnapshot]`

`<mouse-input>` `<history>`

- **概要**: 保持している履歴を古い→新しい順のリストで返す。
- **引数**: `n` — 直近何件を返すか。`None`（デフォルト）なら保持している全件。
  `0` 以下を指定した場合は空リスト。
- **戻り値**: `list[MouseSnapshot]`。
- **どういうときに使うか**: 直近0.2秒分（`n=10` @0.02秒間隔）の軌跡をまとめて解析したい時。
- **使用例**:
  ```python
  recent = mouse.get_history(n=10)   # 直近10tick分（≒0.2秒）
  for snap in recent:
      print(snap.x, snap.y, snap.dx, snap.dy)
  ```

### `get_button_history(self, button: MouseButton, n: int | None = None) -> list[ButtonState]`

`<mouse-input>` `<history>` `<button-state>`

- **概要**: 指定した1ボタンの状態履歴を古い→新しい順のリストで返す
  （`get_history(n)` の各要素から該当ボタンの状態だけを抜き出したもの）。
- **引数**:
  - `button` — 対象の `MouseButton`。
  - `n` — 直近何件を返すか。`None`（デフォルト）なら全件。
- **戻り値**: `list[ButtonState]`。
- **どういうときに使うか**: 「ボタンを押している間の移動量」のように、
  ボタン状態と移動量を突き合わせて相関を見たい時（`get_history()` と同じインデックスで対応する）。
- **使用例**:
  ```python
  history = mouse.get_history(n=10)
  button_history = mouse.get_button_history(MouseButton.LEFT, n=10)
  for snap, state in zip(history, button_history):
      if state is ButtonState.HELD:
          print("ドラッグ中の移動:", snap.dx, snap.dy)
  ```
