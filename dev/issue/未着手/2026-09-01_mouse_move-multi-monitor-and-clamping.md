# Issue: `WinAction.mouse_move` の絶対座標指定がマルチモニタ・範囲外座標に未対応

- 作成日: 2026-09-01
- 状態: 未着手
- 発見元: dev/task/解決/2026-09-01_mouse_input-win_action-base-implementation.md の最終整合性チェック

## 内容

`win_action.py` の `WinAction.mouse_move(x, y, relative=False)`（絶対座標モード）は
`_get_screen_size()`（`GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)`）で取得した
**プライマリモニタの解像度のみ**を基準に 0–65535 へ正規化している。

このため:

1. マルチモニタ環境で、プライマリモニタより左/上に配置されたセカンダリモニタの
   負の座標を正しく指定できない。
2. セカンダリモニタ側の解像度が異なる場合、正規化の基準がずれてカーソルが
   意図しない位置に移動する可能性がある。
3. 画面範囲外の `x`/`y`（`width`/`height` を超える値や負の値）を渡した場合の
   クランプ処理が実装されておらず、正規化結果が 0–65535 の範囲を超えることがある。

## 対応案（未決定・要方針決め）

- 仮想デスクトップ全体を基準にする場合: `GetSystemMetrics(SM_XVIRTUALSCREEN=76,
  SM_YVIRTUALSCREEN=77, SM_CXVIRTUALSCREEN=78, SM_CYVIRTUALSCREEN=79)` を使い、
  オフセットを考慮した正規化に変更する。
- 呼び出し側に「今は正規化前提で使う」ことを許容するのか、`mouse_move` 内で
  範囲外座標を `ValueError` にする／クランプするかは方針要検討。

## 影響範囲

現時点で `main.py` は `win_action.py` を一切呼び出していないため、実害はない
（`mouse_move` 自体は他のどこからも呼ばれていない）。将来ジェスチャー判定から
`WinAction` を使い始めるタイミングまでに解消すればよい。
