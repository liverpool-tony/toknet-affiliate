#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""x_search_trends.json の契約バリデータ

契約（Hermes skill / CLAUDE.md）:
  {"items": [{"source": str, "title": str, "url": str,
              "keywords": [str, ...], "score": number}, ...],
   "collected_at": str}

- `results` / `trends` 等の別キーは無効（items のみ）
- keywords（非空 list[str]）と score（数値）は必須。欠けると
  multi_trend_collector 側で x_search ソース全体がエラーになる
- U+FFFD（置換文字）はサブエージェント並行書き込みによる
  UTF-8 破損の兆候として検出する（run-log 2026-06-30 の実事故）

Usage:
    python3 scripts/validate_x_search_trends.py            # 既定パスを検証
    python3 scripts/validate_x_search_trends.py PATH       # 任意パスを検証

Exit code: 0 = 有効（またはファイル無し=任意ソースなので許容）/ 1 = 契約違反
"""

import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / 'data' / 'x_search_trends.json'

REQUIRED_ITEM_KEYS = {'keywords', 'score'}
RECOMMENDED_ITEM_KEYS = {'source', 'title', 'url'}
KNOWN_BAD_TOP_KEYS = {'results', 'trends'}  # 過去に誤って使われた形式


def validate_file(path=DEFAULT_PATH):
    """(ok: bool, errors: list[str], warnings: list[str]) を返す"""
    path = Path(path)
    errors = []
    warnings = []

    if not path.exists():
        warnings.append(f"{path} が存在しない（x_search は任意ソースなので許容）")
        return True, errors, warnings

    try:
        raw = path.read_text(encoding='utf-8')
    except UnicodeDecodeError as e:
        errors.append(f"UTF-8 として読めない: {e}")
        return False, errors, warnings

    if '�' in raw:
        errors.append("置換文字 U+FFFD を含む（UTF-8 破損の兆候。書き込み後の読み戻し検証を）")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        errors.append(f"JSON パース失敗: {e}")
        return False, errors, warnings

    if not isinstance(data, dict):
        errors.append(f"トップレベルが object でない: {type(data).__name__}")
        return False, errors, warnings

    bad_keys = KNOWN_BAD_TOP_KEYS & set(data.keys())
    if bad_keys:
        errors.append(f"無効なキー {sorted(bad_keys)} を使用（有効なのは 'items' のみ）")

    if 'items' not in data:
        errors.append("'items' キーが無い")
        return False, errors, warnings

    items = data['items']
    if not isinstance(items, list):
        errors.append(f"'items' が list でない: {type(items).__name__}")
        return False, errors, warnings

    if not items:
        warnings.append("'items' が空（今回の X トレンドは 0 件扱い）")

    for i, item in enumerate(items):
        label = f"items[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{label} が object でない")
            continue
        missing = REQUIRED_ITEM_KEYS - set(item.keys())
        if missing:
            errors.append(f"{label} に必須キー {sorted(missing)} が無い")
        kws = item.get('keywords')
        if kws is not None:
            if not isinstance(kws, list) or not kws:
                errors.append(f"{label}.keywords が非空 list でない")
            elif not all(isinstance(k, str) and k.strip() for k in kws):
                errors.append(f"{label}.keywords に文字列でない/空の要素がある")
        score = item.get('score')
        if score is not None and not isinstance(score, (int, float)):
            errors.append(f"{label}.score が数値でない: {score!r}")
        missing_rec = RECOMMENDED_ITEM_KEYS - set(item.keys())
        if missing_rec:
            warnings.append(f"{label} に推奨キー {sorted(missing_rec)} が無い")

    if 'collected_at' not in data:
        warnings.append("'collected_at' が無い（鮮度判定不能）")

    return not errors, errors, warnings


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    ok, errors, warnings = validate_file(path)

    for w in warnings:
        print(f"  ⚠️ {w}")
    for e in errors:
        print(f"  ❌ {e}")

    if ok:
        print(f"✅ {path}: 有効")
        sys.exit(0)
    else:
        print(f"❌ {path}: 契約違反（{len(errors)} 件）— 'items' 形式で書き直してください")
        sys.exit(1)


if __name__ == '__main__':
    main()
