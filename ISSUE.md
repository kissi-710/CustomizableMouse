# ISSUE.md

`SPEC.md` / 実装(`mouse_input.py`, `win_action.py`, `main.py`) / テスト / `docs/` の
最終整合性チェックで見つかった問題の記録。

## 未解決

### 1. `WinAction.mouse_move` の絶対座標指定がマルチモニタ・範囲外座標に未対応

- 詳細: [dev/issue/未着手/2026-09-01_mouse_move-multi-monitor-and-clamping.md](dev/issue/未着手/2026-09-01_mouse_move-multi-monitor-and-clamping.md)
- 概要: 絶対座標の正規化にプライマリモニタの解像度 (`GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)`)
  のみを使っており、セカンダリモニタの負座標や画面範囲外の値に対応していない。
- 影響: 現時点で `mouse_move` はどこからも呼ばれていない（`main.py` は `win_action.py` を
  未使用）ため実害なし。`WinAction` を実際に使い始める前に方針を決めて対応する。

## チェックして問題なしと判断した点

- SPEC.md の各クラス・関数シグネチャと実装（`mouse_input.py`/`win_action.py`）の一致。
- SPEC.md 3.4節「update() 未呼び出し時の戻り値」と実装のデフォルト値（`None`/空リスト/`IDLE`）の一致。
- `docs/api/*.md` 内で使用しているタグが `docs/TAG.md` の正本と過不足なく一致している
  （未定義タグ・未使用タグともになし）。
- `press_key` が内部で `press_keys([key], hold_seconds)` を呼ぶ実装になっていること
  （`test/test_win_action.py::PressKeyDelegatesToPressKeysTests` で検証）。
- `Key` enum の全メンバーが `KEY_CODE_MAP` に過不足なく対応していること、VKコードの重複がないこと
  （`test/test_win_action.py::KeyCodeMapCompletenessTests` で検証）。
- `main.py` は SPEC.md 5章の記述どおり、ループ前に `test/run_tests.py` を実行して
  失敗時は起動を中止し、`win_action.py` を一切呼び出さない構成になっている。
- テスト全件（33件）がパスしている（`python test/run_tests.py`）。

## 修正済み（実装中に発見・その場で修正したもの）

- `win_action.py` の `MOUSEINPUT.mouseData` フィールドを `ctypes.c_ulong`（符号なし）で
  定義していたため、`mouse_scroll` に負の値（下/左スクロール）を渡すと巨大な正の値に
  ラップされる不具合があった。`ctypes.c_long`（符号付き）に修正し、テストで再発防止済み
  （`test/test_win_action.py::MouseScrollTests::test_horizontal_scroll_uses_hwheel_flag`）。
- SPEC.md 5章がまだ `win_action.py` を使う古いサンプルコードのままで、
  「実装対象外」という記述も実際に `main.py` を実装した現状と矛盾していたため、
  実装済みの `main.py` の内容に合わせて更新した。
