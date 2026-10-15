import os
import json
import html
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import requests

# 環境変数の読み込み（未設定でもサンプル＆RSSで即テスト動作可能）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-flash-latest"
AMAZON_TAG = os.getenv("AMAZON_TAG", "your-amazon-tag-22")
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "")
RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"


def guess_site_url():
    """SITE_URL があれば優先し、無ければ GitHub Pages のURLをリポジトリ名から推測する"""
    url = os.getenv("SITE_URL", "")
    if not url:
        repo = os.getenv("GITHUB_REPOSITORY", "anzmanzyu/auto-deal-bot")
        owner, _, name = repo.partition("/")
        url = f"https://{owner}.github.io/{name}/"
    return url if url.endswith("/") else url + "/"


SITE_URL = guess_site_url()
SITE_TITLE = "AI厳選：実質最安値・注目ガジェット速報"

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
TODAY_STR = NOW.strftime("%Y-%m-%d %H:%M")
TODAY_DATE = NOW.strftime("%Y-%m-%d")

HISTORY_PATH = "data/history.json"
HISTORY_DAYS = 30

BADGES = {"main": "🔥 本日の目玉", "impulse": "🛒 ついで買い定番"}

# AIが「ついで買い枠」を返さなかった場合に補う定番品
IMPULSE_STAPLES = [
    {
        "product_name": "Anker USB-C ケーブル 1m 2本セット",
        "category": "日用品・家電",
        "slot": "impulse",
        "badge": BADGES["impulse"],
        "deal_reason": "・1,000円台で買える定番の充電ケーブル\n・予備や職場用に1本あると便利\n・高額品のついでにカートへ入れやすい",
        "sns_text": "【ついで買い定番】AnkerのUSB-Cケーブルは予備に1本あると安心。セールのついでにまとめ買いがおすすめ。#ガジェット",
        "score": 82,
        "image_url": ""
    },
    {
        "product_name": "パナソニック エボルタネオ 単3形 8本パック",
        "category": "日用品・家電",
        "slot": "impulse",
        "badge": BADGES["impulse"],
        "deal_reason": "・長持ちで定番のアルカリ乾電池\n・リモコンやマウスの予備に必須\n・1,000円前後で即決しやすい",
        "sns_text": "【ストック推奨】長持ちの定番乾電池エボルタネオ。切らす前にセールでまとめ買いしておくのが吉。#日用品",
        "score": 80,
        "image_url": ""
    },
]


def safe_status(e):
    return getattr(getattr(e, "response", None), "status_code", type(e).__name__)


def fetch_rakuten(keyword, slot_hint, hits, min_price=None, max_price=None):
    """楽天市場APIから商品候補を取得する（画像URL付き）"""
    params = {
        "applicationId": RAKUTEN_APP_ID,
        "keyword": keyword,
        "sort": "-reviewCount",
        "hits": hits,
        "imageFlag": 1,
    }
    if min_price:
        params["minPrice"] = min_price
    if max_price:
        params["maxPrice"] = max_price
    items = []
    try:
        res = requests.get("https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601", params=params, timeout=15)
        res.raise_for_status()
        for item in res.json().get("Items", []):
            info = item.get("Item", item)
            images = info.get("mediumImageUrls") or info.get("smallImageUrls") or []
            image_url = ""
            if images:
                first = images[0]
                image_url = first.get("imageUrl", "") if isinstance(first, dict) else str(first)
            items.append({
                "title": info.get("itemName", ""),
                "price": f"{info.get('itemPrice', '')}円（ポイント倍率: {info.get('pointRate', 1)}倍）",
                "description": info.get("itemCaption", "")[:200],
                "source_url": info.get("itemUrl", ""),
                "image_url": image_url,
                "slot_hint": slot_hint,
            })
    except Exception as e:
        print(f"Rakuten API fetch notice ({keyword}): {safe_status(e)}")
    return items


def fetch_candidates():
    """公開RSSフィードおよび楽天APIから最新のセール・特価候補を取得する"""
    candidates = []

    if RAKUTEN_APP_ID:
        candidates += fetch_rakuten("セール 目玉 ガジェット", "main", 10)
        candidates += fetch_rakuten("送料無料 定番 まとめ買い", "impulse", 8, 800, 3500)

    rss_urls = [
        "https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf",
        "https://k-tai.watch.impress.co.jp/data/rss/1.0/ktw/feed.rdf"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DealWatchBot/1.0)"}
    keywords = ["セール", "円", "発売", "Amazon", "値引き", "実質", "安", "モデル", "搭載"]

    for rss_url in rss_urls:
        try:
            res = requests.get(rss_url, headers=headers, timeout=15)
            res.raise_for_status()
            root = ET.fromstring(res.content)
            for elem in root.iter():
                if not elem.tag.endswith("item"):
                    continue
                title = link = desc = ""
                for child in elem:
                    if child.tag.endswith("title") and child.text:
                        title = child.text.strip()
                    elif child.tag.endswith("link") and child.text:
                        link = child.text.strip()
                    elif child.tag.endswith("description") and child.text:
                        desc = child.text.strip()
                if any(k in title for k in keywords):
                    candidates.append({
                        "title": title,
                        "price": "記事内・リンク先参照",
                        "description": desc[:200],
                        "source_url": link,
                        "image_url": "",
                        "slot_hint": "main",
                    })
        except Exception as e:
            print(f"RSS fetch notice ({rss_url}): {safe_status(e)}")

    return candidates[:30]


def sample_deals():
    print("AIが利用できないため、初期動作確認用のサンプルデータで生成します。")
    return [
        {
            "product_name": "Anker Prime Wall Charger (67W, 3 ports, GaN)",
            "category": "ガジェット",
            "slot": "main",
            "badge": "⚡ 実質最安級",
            "deal_reason": "・ノートPCもスマホもこれ1台で急速充電可能\n・折りたたみ式プラグで持ち運びに最適\n・セール時はポイント還元込みで実質最安クラスに到達",
            "sns_text": "【本日の注目ガジェット】Ankerの67W 3ポート充電器が実質最安クラスで狙い目！PCとスマホの充電器を1つにまとめたい人はこれ一択です。#ガジェット #セール",
            "score": 95,
            "image_url": ""
        },
        {
            "product_name": "ロジクール ワイヤレスマウス トラックボール M575S",
            "category": "ガジェット",
            "slot": "main",
            "badge": BADGES["main"],
            "deal_reason": "・腕や手首が疲れにくい定番トラックボール\n・長寿命バッテリーで最大24ヶ月使用可能\n・Amazonおよび楽天の還元対象になりやすい鉄板モデル",
            "sns_text": "【定番アイテム】デスクワークの手首の疲れを激減させるロジクールの名機M575S。セール・ポイント還元時の買い替えが圧倒的にお得です。#デスク環境",
            "score": 91,
            "image_url": ""
        },
        {
            "product_name": "Anker Nano Power Bank 5000mAh",
            "category": "ガジェット",
            "slot": "main",
            "badge": BADGES["main"],
            "deal_reason": "・ポケットに入るコンパクトなモバイルバッテリー\n・USB-C直挿しでケーブル不要\n・通勤・旅行の電池切れ対策に",
            "sns_text": "【持ち歩き必須】ケーブル不要で直挿しできるAnkerの小型モバイルバッテリー。セール中なら買い時です。#ガジェット",
            "score": 88,
            "image_url": ""
        },
    ] + [dict(d) for d in IMPULSE_STAPLES]


def build_prompt(candidates):
    return f"""
あなたはガジェット・日用品の価格調査およびお買い得判定の専門家です。
Amazon・楽天のアフィリエイトは「リンクを踏んで24時間以内に買った別商品」も報酬対象になります。
そのため、以下の候補リストと一般的な市場知識をもとに、合計5〜6件を次の内訳で厳選してください。

- 目玉ガジェット・家電枠（slot: "main"）を3〜4件：値引き率や注目度が高い製品
- ついで買い・即決定番枠（slot: "impulse"）を必ず2件：モバイルバッテリー、充電ケーブル、乾電池、炭酸水、日用品など
  1,000〜3,000円台で「安くて今すぐカートに入れやすい定番品」。候補に無ければ定番品を自分で選んでよい

【出力フォーマット（必ず以下のJSONオブジェクトのみを出力してください）】
{{
  "deals": [
    {{
      "product_name": "Amazonや楽天で検索しやすい具体的な商品名・型番（40文字以内）",
      "category": "ガジェット または 日用品・家電",
      "slot": "main または impulse",
      "badge": "🔥 本日の目玉 / ⚡ 実質最安級 / 🛒 ついで買い定番 のいずれか（impulse枠は必ず 🛒 ついで買い定番）",
      "deal_reason": "なぜ注目・お買い得なのかを箇条書き3行（・から始める）で簡潔に解説",
      "sns_text": "X（旧Twitter）にそのまま投稿できる110文字以内の魅力的な紹介文（ハッシュタグ付き）",
      "score": 80から99までの整数（おすすめ度）,
      "image_url": "元にした候補データに image_url があればそのまま転記、無ければ空文字"
    }}
  ]
}}

【候補データ】
{json.dumps(candidates, ensure_ascii=False)}
"""


def parse_deals(text):
    result = json.loads(text)
    if isinstance(result, dict):
        result = result.get("deals", [])
    if not isinstance(result, list):
        raise ValueError("AIの出力が配列ではありません")
    return result


def analyze_with_gemini(candidates):
    """Gemini APIで注目商品を厳選する"""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": build_prompt(candidates)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}
    }
    res = requests.post(endpoint, json=payload, timeout=30)
    res.raise_for_status()
    return parse_deals(res.json()["candidates"][0]["content"]["parts"][0]["text"])


def analyze_with_groq(candidates):
    """Groq（クレカ不要の無料枠あり）で注目商品を厳選する"""
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    # 提供モデルは入れ替わるため、指定モデルが無ければ利用可能な文章生成モデルから選ぶ
    models_res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=15)
    models_res.raise_for_status()
    available = [m["id"] for m in models_res.json().get("data", [])]
    model = GROQ_MODEL
    if model not in available:
        preferred = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3-32b", "openai/gpt-oss-20b"]
        text_models = [m for m in available if not any(x in m for x in ("whisper", "tts", "guard", "orpheus", "compound"))]
        model = next((m for m in preferred if m in available), text_models[0] if text_models else model)
        print(f"Groq: {GROQ_MODEL} が利用できないため {model} を使用します。")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(candidates)}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }
    res = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    res.raise_for_status()
    return parse_deals(res.json()["choices"][0]["message"]["content"])


def normalize_deals(deals):
    """AI出力の欠損を補い、ついで買い枠2件を必ず含む5〜6件に整える"""
    cleaned = []
    for d in deals:
        if not isinstance(d, dict) or not d.get("product_name"):
            continue
        slot = "impulse" if d.get("slot") == "impulse" else "main"
        image_url = str(d.get("image_url") or "")
        try:
            score = int(d.get("score", 85))
        except (TypeError, ValueError):
            score = 85
        cleaned.append({
            "product_name": str(d["product_name"])[:60],
            "category": str(d.get("category") or ("日用品・家電" if slot == "impulse" else "ガジェット")),
            "slot": slot,
            "badge": BADGES["impulse"] if slot == "impulse" else str(d.get("badge") or BADGES["main"]),
            "deal_reason": str(d.get("deal_reason", "")),
            "sns_text": str(d.get("sns_text", "")),
            "score": score,
            "image_url": image_url if image_url.startswith("https://") else "",
        })

    main = [d for d in cleaned if d["slot"] == "main"][:4]
    impulse = [d for d in cleaned if d["slot"] == "impulse"][:2]
    for staple in IMPULSE_STAPLES:
        if len(impulse) >= 2:
            break
        if all(staple["product_name"] != d["product_name"] for d in impulse):
            impulse.append(dict(staple))
    # 目玉枠を先頭、ついで買い枠を最後に並べる
    return main + impulse


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


def build_tweet_url(deal, page_url):
    amz_url, _ = build_affiliate_urls(deal["product_name"])
    text = f"{deal['sns_text']}\n{amz_url}"
    return "https://twitter.com/intent/tweet?" + urllib.parse.urlencode({"text": text, "url": page_url})


def thumbnail_html(deal):
    """商品画像、無ければカテゴリ別のアイコンで表示する"""
    if deal["image_url"]:
        return (f'<img src="{html.escape(deal["image_url"])}" alt="{html.escape(deal["product_name"])}" '
                f'loading="lazy" class="w-24 h-24 object-contain rounded-lg bg-white border border-slate-200 shrink-0">')
    if deal["slot"] == "impulse" or "日用品" in deal["category"]:
        icon, colors = "🏠", "from-emerald-100 to-emerald-200"
    else:
        icon, colors = "⚡", "from-sky-100 to-indigo-200"
    return (f'<div class="w-24 h-24 rounded-lg bg-gradient-to-br {colors} flex items-center justify-center '
            f'text-4xl shrink-0" aria-hidden="true">{icon}</div>')


def render_page(deals, history, page_date, root, page_url):
    """スマホ・PC対応のページHTMLを組み立てる（root はサイト直下への相対パス）"""
    cards_html = ""
    for idx, deal in enumerate(deals, 1):
        amz_url, rkt_url = build_affiliate_urls(deal["product_name"])
        reasons_html = html.escape(deal["deal_reason"]).replace("\n", "<br>")
        badge_color = "bg-emerald-100 text-emerald-800" if deal["slot"] == "impulse" else "bg-rose-100 text-rose-800"
        cards_html += f"""
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-4">
            <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="{badge_color} text-xs font-bold px-2.5 py-1 rounded">{html.escape(deal['badge'])}</span>
                    <span class="bg-blue-100 text-blue-800 text-xs font-bold px-2.5 py-1 rounded">#{idx} {html.escape(deal['category'])}</span>
                </div>
                <span class="text-amber-600 font-bold text-sm">注目度スコア: {deal['score']} / 100</span>
            </div>
            <div class="flex gap-4 mb-4">
                {thumbnail_html(deal)}
                <div class="min-w-0">
                    <h2 class="text-lg font-bold text-slate-900 mb-2">{html.escape(deal['product_name'])}</h2>
                    <div class="text-sm text-slate-700 leading-relaxed">{reasons_html}</div>
                </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <a href="{html.escape(amz_url)}" target="_blank" rel="nofollow noopener sponsored"
                   class="flex items-center justify-center bg-amber-500 hover:bg-amber-600 text-white font-bold py-2.5 px-4 rounded-lg text-sm transition">
                   Amazonで最安値を見る
                </a>
                <a href="{html.escape(rkt_url)}" target="_blank" rel="nofollow noopener sponsored"
                   class="flex items-center justify-center bg-red-600 hover:bg-red-700 text-white font-bold py-2.5 px-4 rounded-lg text-sm transition">
                   楽天市場で実質価格を見る
                </a>
            </div>
            <a href="{html.escape(build_tweet_url(deal, page_url))}" target="_blank" rel="noopener"
               class="mt-3 flex items-center justify-center bg-slate-900 hover:bg-slate-700 text-white font-bold py-2 px-4 rounded-lg text-xs transition">
               𝕏 ポスト作成
            </a>
        </div>
        """

    archive_items = ""
    for entry in history:
        names = " / ".join(entry.get("products", [])[:3])
        archive_items += f"""
            <li><a href="{root}archive/{entry['date']}.html" class="block py-2 hover:bg-slate-50 rounded px-2">
                <span class="font-bold text-slate-800">{entry['date']}</span>
                <span class="text-slate-500 text-xs block truncate">{html.escape(names)}</span>
            </a></li>"""

    top_names = "、".join(d["product_name"] for d in deals[:3])
    description = f"{page_date}のAI厳選お買い得ガジェット・日用品。{top_names}など。Amazon・楽天の実質価格をチェック。"
    title = f"{page_date} 実質最安値・お買い得ガジェット速報 | {SITE_TITLE}"
    home_link = "" if root == "" else f'<a href="{root}index.html" class="text-xs text-sky-300 underline">最新のお買い得情報へ</a>'

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <meta name="description" content="{html.escape(description)}">
    <link rel="canonical" href="{html.escape(page_url)}">
    <meta property="og:title" content="{html.escape(title)}">
    <meta property="og:description" content="{html.escape(description)}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{html.escape(page_url)}">
    <meta property="og:site_name" content="{html.escape(SITE_TITLE)}">
    <meta property="og:locale" content="ja_JP">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{html.escape(title)}">
    <meta name="twitter:description" content="{html.escape(description)}">
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 min-h-screen text-slate-800">
    <header class="bg-slate-900 text-white py-6 px-4 shadow-md">
        <div class="max-w-2xl mx-auto">
            <h1 class="text-xl font-bold">⚡ {html.escape(SITE_TITLE)}</h1>
            <p class="text-xs text-slate-400 mt-1">{page_date} 版 / 最終自動更新: {TODAY_STR} (JST) / 毎日自動解析</p>
            {home_link}
        </div>
    </header>
    <main class="max-w-2xl mx-auto p-4">
        <p class="text-xs text-slate-500 mb-4">※当サイトは適格販売により収入を得るプログラムに参加しています。リアルタイムの在庫・ポイント還元率は各リンク先でご確認ください。</p>
        {cards_html}
    </main>
    <footer class="max-w-2xl mx-auto p-4 pb-10">
        <section class="bg-white rounded-xl border border-slate-200 p-5">
            <h2 class="font-bold text-slate-900 mb-2">📅 過去のお買い得アーカイブ一覧</h2>
            <ul class="divide-y divide-slate-100 text-sm">{archive_items}
            </ul>
        </section>
    </footer>
</body>
</html>
"""


def load_history():
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in data if isinstance(e, dict) and e.get("date")]
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"履歴ファイルの読み込みに失敗したため新規作成します: {e}")
        return []


def update_history(history, deals):
    entry = {"date": TODAY_DATE, "products": [d["product_name"] for d in deals]}
    history = [e for e in history if e["date"] != TODAY_DATE]
    history.insert(0, entry)
    history.sort(key=lambda e: e["date"], reverse=True)
    history = history[:HISTORY_DAYS]
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history


def generate_site(deals):
    """トップページ・日別アーカイブ・sitemap.xml・robots.txt を生成する"""
    os.makedirs("public/archive", exist_ok=True)
    history = update_history(load_history(), deals)

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(render_page(deals, history, TODAY_DATE, "", SITE_URL))
    archive_url = f"{SITE_URL}archive/{TODAY_DATE}.html"
    with open(f"public/archive/{TODAY_DATE}.html", "w", encoding="utf-8") as f:
        f.write(render_page(deals, history, TODAY_DATE, "../", archive_url))

    # 実在するアーカイブだけをサイトマップに載せる
    archive_dates = sorted((n[:-5] for n in os.listdir("public/archive") if n.endswith(".html")), reverse=True)
    urls = [f"  <url><loc>{SITE_URL}</loc><lastmod>{TODAY_DATE}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    for d in archive_dates:
        urls.append(f"  <url><loc>{SITE_URL}archive/{d}.html</loc><lastmod>{d}</lastmod><priority>0.6</priority></url>")
    with open("public/sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n")
    with open("public/robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")

    print(f"public/index.html・public/archive/{TODAY_DATE}.html・sitemap.xml・robots.txt を生成しました。")


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


def select_deals(candidates):
    """Gemini → Groq → サンプルの順に試し、どれかが失敗しても処理を止めない"""
    for name, key, func in (("Gemini", GEMINI_API_KEY, analyze_with_gemini), ("Groq", GROQ_API_KEY, analyze_with_groq)):
        if not key:
            continue
        try:
            deals = normalize_deals(func(candidates))
            if len([d for d in deals if d["slot"] == "main"]) >= 2:
                print(f"{name}で判定しました。")
                return deals
            print(f"{name}の出力が不足していたため次の手段を試します。")
        except Exception as e:
            print(f"{name} APIエラー（{safe_status(e)}）")
    return normalize_deals(sample_deals())


if __name__ == "__main__":
    print("1. 候補データを取得中...")
    raw_candidates = fetch_candidates()
    print(f"   取得件数: {len(raw_candidates)}件")

    print("2. AIで買い時判定＆テキスト生成中...")
    selected_deals = select_deals(raw_candidates)
    print(f"   掲載件数: {len(selected_deals)}件（ついで買い枠 {sum(d['slot'] == 'impulse' for d in selected_deals)}件）")

    print("3. Webサイト更新＆通知送信中...")
    generate_site(selected_deals)
    notify_discord(selected_deals)
    print("完了しました！")
