import os
import json
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import requests

# 環境変数の読み込み（未設定でもサンプル＆RSSで即テスト動作可能）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AMAZON_TAG = os.getenv("AMAZON_TAG", "your-amazon-tag-22")
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "")
RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

JST = timezone(timedelta(hours=9))
TODAY_STR = datetime.now(JST).strftime("%Y-%m-%d %H:%M")


def fetch_candidates():
    """公開RSSフィードおよび楽天APIから最新のセール・特価候補を取得する"""
    candidates = []

    if RAKUTEN_APP_ID:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
        params = {
            "applicationId": RAKUTEN_APP_ID,
            "keyword": "セール 目玉",
            "sort": "-reviewCount",
            "hits": 15,
        }
        try:
            res = requests.get(url, params=params, timeout=15)
            if res.status_code == 200:
                data = res.json()
                for item in data.get("Items", []):
                    info = item["Item"]
                    candidates.append({
                        "title": info["itemName"],
                        "price": f"{info['itemPrice']}円（ポイント倍率: {info.get('pointRate', 1)}倍）",
                        "description": info["itemCaption"][:200],
                        "source_url": info["itemUrl"]
                    })
        except Exception as e:
            print(f"Rakuten API fetch notice: {e}")

    rss_urls = [
        "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf",
        "https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DealWatchBot/1.0)"}

    for rss_url in rss_urls:
        try:
            res = requests.get(rss_url, headers=headers, timeout=15)
            if res.status_code == 200:
                root = ET.fromstring(res.content)
                for elem in root.iter():
                    if elem.tag.endswith("item"):
                        title = ""
                        link = ""
                        desc = ""
                        for child in elem:
                            if child.tag.endswith("title") and child.text:
                                title = child.text.strip()
                            elif child.tag.endswith("link") and child.text:
                                link = child.text.strip()
                            elif child.tag.endswith("description") and child.text:
                                desc = child.text.strip()
                        keywords = ["セール", "円", "発売", "Amazon", "値引き", "実質", "安", "モデル", "搭載"]
                        if any(k in title for k in keywords):
                            candidates.append({
                                "title": title,
                                "price": "記事内・リンク先参照",
                                "description": desc[:200],
                                "source_url": link
                            })
        except Exception as e:
            print(f"RSS fetch notice ({rss_url}): {e}")

    return candidates[:20]


def analyze_with_gemini(candidates):
    """Gemini APIで注目商品を最大5件厳選し、JSON形式で返す"""
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEYが未設定のため、初期動作確認用のサンプルデータで生成します。")
        return [
            {
                "product_name": "Anker Prime Wall Charger (67W, 3 ports, GaN)",
                "category": "ガジェット",
                "deal_reason": "・ノートPCもスマホもこれ1台で急速充電可能\n・折りたたみ式プラグで持ち運びに最適\n・セール時はポイント還元込みで実質最安クラスに到達",
                "sns_text": "【本日の注目ガジェット】Ankerの67W 3ポート充電器が実質最安クラスで狙い目！PCとスマホの充電器を1つにまとめたい人はこれ一択です。#ガジェット #セール",
                "score": 95
            },
            {
                "product_name": "ロジクール ワイヤレスマウス トラックボール M575S",
                "category": "PC周辺機器",
                "deal_reason": "・腕や手首が疲れにくい定番トラックボール\n・長寿命バッテリーで最大24ヶ月使用可能\n・Amazonおよび楽天の還元対象になりやすい鉄板モデル",
                "sns_text": "【定番アイテム】デスクワークの手首の疲れを激減させるロジクールの名機M575S。セール・ポイント還元時の買い替えが圧倒的にお得です。#デスク環境",
                "score": 91
            }
        ]

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""
あなたはガジェット・日用品の価格調査およびお買い得判定の専門家です。
以下の候補リストから、一般消費者が「今チェックしておくと得をする注目商品・セール情報」を最大5件厳選し、JSON配列形式で出力してください。

【出力フォーマット（必ず以下のJSONスキーマのみを出力してください）】
[
  {{
    "product_name": "Amazonや楽天で検索しやすい具体的な商品名・型番（40文字以内）",
    "category": "ガジェット または 日用品・家電",
    "deal_reason": "なぜ注目・お買い得なのかを箇条書き3行（・から始める）で簡潔に解説",
    "sns_text": "X（旧Twitter）にそのまま投稿できる110文字以内の魅力的な紹介文（ハッシュタグ付き）",
    "score": 80から99までの整数（おすすめ度）
  }}
]

【候補データ】
{json.dumps(candidates, ensure_ascii=False)}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3
        }
    }

    res = requests.post(endpoint, json=payload, timeout=30)
    res.raise_for_status()
    result_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(result_text)


def build_affiliate_urls(product_name):
    """商品名からAmazonおよび楽天市場のアフィリエイト検索URLを自動生成する"""
    encoded_name = urllib.parse.quote(product_name)
    amazon_url = f"https://www.amazon.co.jp/s?k={encoded_name}&tag={AMAZON_TAG}"

    rakuten_search = f"https://search.rakuten.co.jp/search/mall/{encoded_name}/"
    if RAKUTEN_AFFILIATE_ID:
        encoded_dest = urllib.parse.quote(rakuten_search, safe="")
        rakuten_url = f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_AFFILIATE_ID}/?pc={encoded_dest}"
    else:
        rakuten_url = rakuten_search

    return amazon_url, rakuten_url


def generate_html(deals):
    """スマホ・PC対応の比較サイト（public/index.html）を自動生成する"""
    os.makedirs("public", exist_ok=True)
    cards_html = ""

    for idx, deal in enumerate(deals, 1):
        amz_url, rkt_url = build_affiliate_urls(deal["product_name"])
        reasons_html = deal["deal_reason"].replace("\n", "<br>")

        cards_html += f"""
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-4">
            <div class="flex items-center justify-between mb-2">
                <span class="bg-blue-100 text-blue-800 text-xs font-bold px-2.5 py-1 rounded">#{idx} {deal['category']}</span>
                <span class="text-amber-600 font-bold text-sm">注目度スコア: {deal['score']} / 100</span>
            </div>
            <h2 class="text-lg font-bold text-slate-900 mb-3">{deal['product_name']}</h2>
            <div class="bg-slate-50 rounded-lg p-3 text-sm text-slate-700 mb-4 leading-relaxed">
                {reasons_html}
            </div>
            <div class="grid grid-cols-2 gap-3">
                <a href="{amz_url}" target="_blank" rel="nofollow noopener"
                   class="flex items-center justify-center bg-amber-500 hover:bg-amber-600 text-white font-bold py-2.5 px-4 rounded-lg text-sm transition">
                   Amazonで最安値を見る
                </a>
                <a href="{rkt_url}" target="_blank" rel="nofollow noopener"
                   class="flex items-center justify-center bg-red-600 hover:bg-red-700 text-white font-bold py-2.5 px-4 rounded-lg text-sm transition">
                   楽天市場で実質価格を見る
                </a>
            </div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>本日の実質最安値・お買い得ガジェット速報</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800">
    <header class="bg-slate-900 text-white py-6 px-4 shadow-md">
        <div class="max-w-2xl mx-auto">
            <h1 class="text-xl font-bold">⚡ AI厳選：実質最安値・注目ガジェット速報</h1>
            <p class="text-xs text-slate-400 mt-1">最終自動更新: {TODAY_STR} (JST) / 毎日自動解析</p>
        </div>
    </header>
    <main class="max-w-2xl mx-auto p-4">
        <p class="text-xs text-slate-500 mb-4">※当サイトは適格販売により収入を得るプログラムに参加しています。リアルタイムの在庫・ポイント還元率は各リンク先でご確認ください。</p>
        {cards_html}
    </main>
</body>
</html>
"""
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("public/index.html を生成しました。")


def notify_discord(deals):
    """SNS投稿用のテキストとリンクをDiscordに自動通知する"""
    if not DISCORD_WEBHOOK_URL:
        return

    lines = [f"📢 **【{TODAY_STR} 実質最安値・SNS投稿ドラフト】**\n"]
    for deal in deals[:3]:
        amz_url, _ = build_affiliate_urls(deal["product_name"])
        lines.append(f"**■ {deal['product_name']}** (Score: {deal['score']})")
        lines.append(f"```\n{deal['sns_text']}\n👉 {amz_url}\n```")

    payload = {"content": "\n".join(lines)[:1950]}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Discord通知エラー: {e}")


if __name__ == "__main__":
    print("1. 候補データを取得中...")
    raw_candidates = fetch_candidates()
    print(f"   取得件数: {len(raw_candidates)}件")

    print("2. AIで買い時判定＆テキスト生成中...")
    selected_deals = analyze_with_gemini(raw_candidates)

    print("3. Webサイト更新＆通知送信中...")
    generate_html(selected_deals)
    notify_discord(selected_deals)
    print("完了しました！")
