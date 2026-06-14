#!/usr/bin/env python3
"""
AI記事自動生成スクリプト
Amazon商品データ + テンプレート → WordPress投稿用Markdown記事

使い方:
  python3 generate_article.py --category laptop-pc --type single_review --product "MacBook Air M3"
  python3 generate_article.py --category camera --type comparison --products "Sony α7IV,Canon EOS R6 Mark II"
  python3 generate_article.py --category audio-headphones --type best_of --count 5
"""

import json
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
CATEGORIES_FILE = PROJECT_ROOT / "content" / "categories.json"
TEMPLATES_DIR = PROJECT_ROOT / "content" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "content" / "articles"


def load_categories():
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_template(template_name):
    template_file = TEMPLATES_DIR / f"{template_name}.md"
    if template_file.exists():
        with open(template_file, "r", encoding="utf-8") as f:
            return f.read()
    return None


def generate_article(category, article_type, products, extra_data=None):
    """記事を生成する（AI APIを使わない版。テンプレート + データ注入）"""
    
    categories_data = load_categories()
    cat_info = next((c for c in categories_data["categories"] if c["slug"] == category), None)
    
    if not cat_info:
        print(f"エラー: カテゴリ '{category}' が見つかりません")
        return None
    
    # テンプレート読み込み
    template_map = {
        "single_review": "single_review",
        "comparison": "comparison",
        "best_of": "best_of",
        "buying_guide": "buying_guide"
    }
    
    template_name = template_map.get(article_type, "single_review")
    template = load_template(template_name)
    
    if not template:
        print(f"エラー: テンプレート '{template_name}' が見つかりません")
        return None
    
    # 現在日時
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    
    # 記事データ構造
    article_data = {
        "category": cat_info["name"],
        "category_slug": cat_info["slug"],
        "article_type": article_type,
        "generated_at": now.isoformat(),
        "date": date_str,
        "products": products,
        "extra": extra_data or {}
    }
    
    # テンプレート変数を置換
    article = template
    
    # 共通変数
    article = article.replace("{date}", date_str)
    article = article.replace("{year}", now.strftime("%Y"))
    article = article.replace("{category}", cat_info["name"])
    article = article.replace("{category_slug}", cat_info["slug"])
    
    # 記事タイプ別の変数置換
    if article_type == "single_review":
        product = products[0] if products else {}
        article = article.replace("{product_name}", product.get("name", ""))
        article = article.replace("{protect_point}", extra_data.get("focus_point", "性能"))
        article = article.replace("{positioning}", product.get("positioning", ""))
        article = article.replace("{key_feature}", product.get("key_feature", ""))
        article = article.replace("{test_period}", extra_data.get("test_period", "2週間"))
        article = article.replace("{test_method}", extra_data.get("test_method", "実際の使用"))
        article = article.replace("{evaluate_points}", extra_data.get("evaluate_points", "性能・デザイン・価格"))
        article = article.replace("{price}", product.get("price", ""))
        article = article.replace("{amazon_link}", product.get("amazon_link", "#"))
        article = article.replace("{competitor_name}", extra_data.get("competitor", ""))
        article = article.replace("{amazon_tracking_id}", categories_data.get("affiliate_programs", {}).get("amazon", {}).get("tracking_id", ""))
    
    elif article_type == "comparison":
        product_a = products[0] if len(products) > 0 else {}
        product_b = products[1] if len(products) > 1 else {}
        article = article.replace("{product_A}", product_a.get("name", ""))
        article = article.replace("{product_B}", product_b.get("name", ""))
        article = article.replace("{use_case}", extra_data.get("use_case", "日常使い"))
        article = article.replace("{key_difference}", extra_data.get("key_difference", "性能"))
        article = article.replace("{price_A}", product_a.get("price", ""))
        article = article.replace("{price_B}", product_b.get("price", ""))
        article = article.replace("{amazon_link_A}", product_a.get("amazon_link", "#"))
        article = article.replace("{amazon_link_B}", product_b.get("amazon_link", "#"))
    
    elif article_type == "best_of":
        count = extra_data.get("count", 5)
        article = article.replace("{number}", str(count))
        article = article.replace("{selection_criteria}", extra_data.get("criteria", "性能・価格・使いやすさ"))
        article = article.replace("{market_size}", cat_info.get("description", ""))
        
        # ランキング部分を生成
        ranking_section = ""
        for i, product in enumerate(products[:count], 1):
            ranking_section += f"""
### 第{i}位：{product.get('name', f'商品{i}')}

**価格**: {product.get('price', '要確認')}円
**評価**: ⭐{product.get('rating', '4.0')}/5.0
**一言**: {product.get('one_line', '')}

**おすすめの理由**: {product.get('reason', '')}

**スペック**: {product.get('specs', '')}

**向いている人**: {product.get('target_user', '')}

[Amazonで{product.get('name', '')}を見る]({product.get('amazon_link', '#')})

---
"""
        article = article.replace("（以下、第2位〜第{number}位まで同様）", ranking_section)
    
    elif article_type == "buying_guide":
        article = article.replace("{number}", str(extra_data.get("point_count", 5)))
        article = article.replace("{expert_background}", extra_data.get("expert_bg", "専門家"))
    
    # AI表記・PR表記を追加
    ai_disclaimer = categories_data.get("ai_disclaimer", "")
    pr_disclaimer = categories_data.get("disclaimer", "")
    
    # 記事先頭にAI表記を挿入（まだなければ）
    if "AIにより作成" not in article and "生成AI" not in article:
        article = f"> ※{ai_disclaimer}\n>\n> {pr_disclaimer}\n\n{article}"
    
    return article, article_data


def save_article(article, article_data, output_dir):
    """記事をファイルに保存"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    slug = article_data.get("category_slug", "article")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slug}_{timestamp}.md"
    
    filepath = output_path / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(article)
    
    # メタデータも保存
    meta_filepath = output_path / f"{filename}.meta.json"
    with open(meta_filepath, "w", encoding="utf-8") as f:
        json.dump(article_data, f, ensure_ascii=False, indent=2)
    
    return filepath


def list_categories():
    """利用可能なカテゴリを一覧表示"""
    data = load_categories()
    print("\n📋 利用可能なカテゴリ:")
    print("-" * 60)
    for cat in data["categories"]:
        print(f"  {cat['slug']:25s} | {cat['name']:20s} | 優先度: {cat['priority']}")
    print()


def list_templates():
    """利用可能なテンプレートを一覧表示"""
    print("\n📝 利用可能なテンプレート:")
    print("-" * 60)
    for template_file in TEMPLATES_DIR.glob("*.md"):
        name = template_file.stem
        print(f"  {name}")
    print()


def main():
    parser = argparse.ArgumentParser(description="AI記事自動生成スクリプト")
    parser.add_argument("--category", "-c", help="カテゴリスラッグ")
    parser.add_argument("--type", "-t", choices=["single_review", "comparison", "best_of", "buying_guide"],
                        default="single_review", help="記事タイプ")
    parser.add_argument("--products", "-p", help="商品名（カンマ区切り）")
    parser.add_argument("--count", type=int, default=5, help="ランキング記事の件数")
    parser.add_argument("--output", "-o", default=str(OUTPUT_DIR), help="出力ディレクトリ")
    parser.add_argument("--list-categories", action="store_true", help="カテゴリ一覧")
    parser.add_argument("--list-templates", action="store_true", help="テンプレート一覧")
    parser.add_argument("--focus", help="レビューの焦点")
    parser.add_argument("--use-case", help="比較記事のユースケース")
    
    args = parser.parse_args()
    
    if args.list_categories:
        list_categories()
        return
    
    if args.list_templates:
        list_templates()
        return
    
    if not args.category:
        print("エラー: --category は必須です")
        list_categories()
        sys.exit(1)
    
    # 商品データ（実際はAPIやスクレイピングで取得）
    products = []
    if args.products:
        for p in args.products.split(","):
            products.append({
                "name": p.strip(),
                "price": "要確認",
                "amazon_link": "#",
                "rating": "4.0",
                "one_line": "",
                "reason": "",
                "specs": "",
                "target_user": ""
            })
    
    extra_data = {
        "focus_point": args.focus or "性能",
        "use_case": args.use_case or "日常使い",
        "count": args.count,
        "criteria": "性能・価格・使いやすさ",
        "test_period": "2週間",
        "test_method": "実際の使用",
        "evaluate_points": "性能・デザイン・価格",
        "competitor": "",
        "point_count": 5,
        "expert_bg": "IT専門家"
    }
    
    result = generate_article(args.category, args.type, products, extra_data)
    if result:
        article, article_data = result
        filepath = save_article(article, article_data, args.output)
        print(f"✅ 記事を生成しました: {filepath}")
        print(f"📊 メタデータ: {filepath}.meta.json")
    else:
        print("❌ 記事生成に失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    main()
