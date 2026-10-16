import os
import time
import json
import html
import hashlib
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
RAKUTEN_ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")


def guess_site_url():
    """SITE_URL があれば優先し、無ければ GitHub Pages のURLをリポジトリ名から推測する"""
    url = os.getenv("SITE_URL", "")
    if not url:
        repo = os.getenv("GITHUB_REPOSITORY", "anzmanzyu/auto-deal-bot")
        owner, _, name = repo.partition("/")
        url = f"https://{owner}.github.io/{name}/"
    return url if url.endswith("/") else url + "/"


SITE_URL = guess_site_url()
RAKUTEN_ORIGIN = os.getenv("RAKUTEN_ORIGIN", "https://anzmanzyu.github.io")
SITE_NAME = "AI厳選 ガジェット特価速報"
SITE_TAGLINE = "Amazon・楽天のお買い得ガジェットを、AIが毎日2回厳選"
OG_IMAGE = "og.png"  # public/og.png（1200x630）

JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
TODAY_STR = NOW.strftime("%Y-%m-%d %H:%M")
TODAY_DATE = NOW.strftime("%Y-%m-%d")
WEEKDAYS = "月火水木金土日"
UPDATE_HOURS = (7, 18)  # workflow の cron（UTC 22:00 / 9:00）を日本時間にしたもの

HISTORY_PATH = "data/history.json"
HISTORY_DAYS = 30
PRODUCTS_PATH = "data/products.json"
PRODUCT_RECORDS = 120  # 1商品あたりの価格記録の上限
PRODUCT_KEEP_DAYS = 180  # これより長く掲載されていない商品ページは削除する
EVENTS_PATH = "data/events.json"
EVENT_LOOKAHEAD_DAYS = 14

BADGES = {"main": "🔥 本日の目玉", "impulse": "🛒 ついで買い定番"}

# AIが「ついで買い枠」を返さなかった場合に補う定番品
IMPULSE_STAPLES = [
    {
        "product_name": "Anker USB-C ケーブル 1m 2本セット",
        "category": "日用品・家電",
        "slot": "impulse",
        "badge": BADGES["impulse"],
        "catch_copy": "予備に1本、ついでに安心",
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
        "catch_copy": "切らす前にストック",
        "deal_reason": "・長持ちで定番のアルカリ乾電池\n・リモコンやマウスの予備に必須\n・1,000円前後で即決しやすい",
        "sns_text": "【ストック推奨】長持ちの定番乾電池エボルタネオ。切らす前にセールでまとめ買いしておくのが吉。#日用品",
        "score": 80,
        "image_url": ""
    },
]

# 商品画像が無いときに表示するジャンル別イラスト public/img/items/*.svg（上から順に判定）
ITEM_ART = [
    (("ミニPC", "Mac mini", "NUC"), "minipc"),
    (("ヘッドホン", "ヘッドフォン", "ヘッドセット"), "headphones"),
    (("イヤホン", "AirPods", "Buds"), "earbuds"),
    (("スピーカー", "サウンドバー", "Echo"), "speaker"),
    (("バッテリー", "Power Bank", "PowerCore"), "battery"),
    (("乾電池", "電池", "エボルタ", "エネループ", "単3", "単4"), "drycell"),
    (("充電器", "Charger", "GaN", "アダプタ"), "charger"),
    (("ケーブル",), "cable"),
    (("マウス", "トラックボール"), "mouse"),
    (("キーボード",), "keyboard"),
    (("モニター", "ディスプレイ"), "monitor"),
    (("Fire TV", "テレビ", "TV", "プロジェクター", "Chromecast"), "tv"),
    (("ウォッチ", "Watch", "バンド", "Fitbit"), "watch"),
    (("iPad", "タブレット", "Tablet", "Kindle", "Fire HD", "Fire Max", "液タブ", "ペンタブ"), "tablet"),
    (("ノート", "MacBook", "Chromebook", "Surface", "パソコン", "PC"), "laptop"),
    (("iPhone", "Pixel", "Galaxy", "スマホ", "スマートフォン", "Xperia", "AQUOS"), "phone"),
    (("カメラ", "GoPro", "Insta360", "Osmo"), "camera"),
    (("SSD", "HDD", "USBメモリ", "microSD", "SDカード", "NAS"), "storage"),
    (("ルーター", "Wi-Fi", "WiFi", "メッシュ"), "router"),
    (("Switch", "PlayStation", "PS5", "ゲーム", "コントローラー"), "game"),
    (("掃除機", "ルンバ"), "cleaner"),
    (("ノンフライヤー", "エアフライヤー", "炊飯器", "電子レンジ", "オーブン", "トースター", "ケトル", "圧力鍋",
      "ホットクック", "ブレンダー", "コーヒーメーカー"), "kitchen"),
    (("炭酸水", "天然水", "ミネラルウォーター", "飲料", "コーヒー", "お茶"), "drink"),
    (("洗剤", "ティッシュ", "トイレットペーパー"), "household"),
]

# 商品イラストの背景色
CARD_TONES = [
    "from-amber-100 to-orange-200",
    "from-sky-100 to-indigo-200",
    "from-pink-100 to-rose-200",
    "from-emerald-100 to-teal-200",
]
IMPULSE_TONE = "from-lime-100 to-emerald-200"
RANK_STYLES = {
    1: "from-amber-300 to-yellow-500 text-amber-950",
    2: "from-slate-200 to-slate-400 text-slate-800",
    3: "from-orange-300 to-amber-600 text-white",
    4: "from-sky-300 to-indigo-400 text-white",
}


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
    if RAKUTEN_ACCESS_KEY:
        # 新方式: アクセスキー + 許可ドメイン(Origin)で認証する
        params["accessKey"] = RAKUTEN_ACCESS_KEY
        url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
    else:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    # 楽天に登録済みの許可サイト（独自ドメインに移っても github.io のまま送る）
    headers = {"Origin": RAKUTEN_ORIGIN, "Referer": RAKUTEN_ORIGIN + "/auto-deal-bot/"}
    items = []
    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        res.raise_for_status()
        for item in res.json().get("Items", []):
            info = item.get("Item", item)
            images = info.get("mediumImageUrls") or info.get("smallImageUrls") or []
            image_url = ""
            if images:
                first = images[0]
                image_url = first.get("imageUrl", "") if isinstance(first, dict) else str(first)
                image_url = image_url.replace("_ex=128x128", "_ex=400x400")  # 小さすぎるので高解像度版に
            items.append({
                "title": info.get("itemName", ""),
                "price": f"{info.get('itemPrice', '')}円（ポイント倍率: {info.get('pointRate', 1)}倍）",
                "price_yen": info.get("itemPrice"),
                "point_rate": info.get("pointRate", 1),
                "description": info.get("itemCaption", "")[:200],
                "source_url": info.get("itemUrl", ""),
                "image_url": image_url,
                "slot_hint": slot_hint,
            })
    except Exception as e:
        detail = ""
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                body = resp.json()
                detail = " " + str(body.get("error", "")) + " " + str(body.get("error_description", body.get("message", "")))[:200]
            except Exception:
                detail = ""
        print(f"Rakuten API fetch notice ({keyword}): {safe_status(e)}{detail}")
    return items


def fetch_candidates():
    """公開RSSフィードおよび楽天APIから最新のセール・特価候補を取得する"""
    candidates = []

    if RAKUTEN_APP_ID:
        queries = [
            ("ワイヤレスイヤホン", "main", 4, 3000, None),
            ("モバイルモニター", "main", 3, 8000, None),
            ("スマートウォッチ", "main", 3, 3000, None),
            ("ロボット掃除機", "main", 3, 10000, None),
            ("モバイルバッテリー", "impulse", 3, 1000, 4000),
            ("USB-C 充電ケーブル", "impulse", 3, 500, 2500),
            # リピート買いされやすい1,000〜2,000円台の日用品
            ("炭酸水 500ml 24本", "impulse", 2, 1000, 2999),
            ("乾電池 単3 まとめ買い", "impulse", 2, 800, 2999),
            ("電源タップ", "impulse", 2, 1000, 2999),
        ]
        for i, (keyword, slot_hint, hits, min_price, max_price) in enumerate(queries):
            if i:
                time.sleep(1.2)  # 楽天APIのレート制限(1秒1回)対策
            candidates += fetch_rakuten(keyword, slot_hint, hits, min_price, max_price)

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

    candidates = candidates[:36]
    for no, c in enumerate(candidates, 1):
        c["no"] = no
    return candidates


def sample_deals():
    print("AIが利用できないため、初期動作確認用のサンプルデータで生成します。")
    return [
        {
            "product_name": "Anker Prime Wall Charger (67W, 3 ports, GaN)",
            "category": "ガジェット",
            "slot": "main",
            "badge": "⚡ 実質最安級",
            "catch_copy": "PCもスマホもこれ1台",
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
            "catch_copy": "手首が疲れない定番機",
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
            "catch_copy": "ケーブル不要の直挿し型",
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
- image_url が「あり」の候補（楽天の実在商品）を優先し、できるだけ4件以上はそこから選ぶこと。その場合 product_name は候補の商品名を短く整えたものにする
- 候補データに含まれない詳細なスペック数値（重量や解像度など）は推測で書かず、利用シーンやお得感を中心に紹介すること

【出力フォーマット（必ず以下のJSONオブジェクトのみを出力してください）】
{{
  "deals": [
    {{
      "product_name": "Amazonや楽天で検索しやすい具体的な商品名・型番（40文字以内）",
      "category": "ガジェット または 日用品・家電",
      "slot": "main または impulse",
      "badge": "🔥 本日の目玉 / ⚡ 実質最安級 / 🛒 ついで買い定番 のいずれか（impulse枠は必ず 🛒 ついで買い定番）",
      "catch_copy": "商品の一番の魅力をひと言で表すキャッチコピー（16文字以内、価格や割引率の数字は書かない）",
      "deal_reason": "なぜ注目・お買い得なのかを箇条書き3行（・から始める）で簡潔に解説",
      "sns_text": "X（旧Twitter）にそのまま投稿できる110文字以内の魅力的な紹介文（ハッシュタグ付き）",
      "score": 80から99までの整数（おすすめ度）,
      "candidate_no": 元にした候補データの no（候補に無い商品を選んだ場合は 0）
    }}
  ]
}}

【候補データ】
{json.dumps(compact_candidates(candidates), ensure_ascii=False)}
"""


def compact_candidates(candidates):
    """AIに渡す候補を必要な項目だけに絞る（無料枠の文字数上限対策）"""
    rows = []
    for c in candidates:
        row = {"no": c.get("no"), "title": str(c.get("title", ""))[:70], "price": c.get("price", ""), "slot_hint": c.get("slot_hint", "")}
        if c.get("image_url"):
            row["image_url"] = "あり"
        else:
            row["description"] = str(c.get("description", ""))[:80]
        rows.append(row)
    return rows


def parse_deals(text):
    text = str(text).strip()
    # コードブロックや前置きの文章が付いていても、JSON部分だけを読む
    start, end = text.find("{"), text.rfind("}")
    if not text.startswith(("{", "[")) and 0 <= start < end:
        text = text[start:end + 1]
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
    # JSONの形式チェックで400になることがあるため、同じモデル→別モデルの順に再試行する
    fallbacks = [m for m in ("llama-3.3-70b-versatile", "openai/gpt-oss-20b") if m in available and m != model]
    for attempt_model in [model, model] + fallbacks[:1]:
        payload = {
            "model": attempt_model,
            "messages": [{"role": "user", "content": build_prompt(candidates)}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        }
        res = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        if res.status_code != 400:
            break
        print(f"Groq: {attempt_model} が400エラー（{groq_error_code(res)}）のため再試行します。")
    res.raise_for_status()
    return parse_deals(res.json()["choices"][0]["message"]["content"])


def groq_error_code(res):
    """エラー本文から原因コードだけを取り出す（キーなどは含まれない）"""
    try:
        return res.json().get("error", {}).get("code") or res.status_code
    except ValueError:
        return res.status_code


def reason_lines(text):
    """「・」区切りの解説文を1行ずつのリストにする"""
    lines = [line.strip().lstrip("・-•*").strip() for line in str(text).splitlines()]
    return [line for line in lines if line]


def normalize_deals(deals, candidates=()):
    """AI出力の欠損を補い、ついで買い枠2件を必ず含む5〜6件に整える"""
    # 価格はAIに書かせず、楽天APIで取得した候補と画像URLが一致したときだけ載せる
    by_no = {c.get("no"): c for c in candidates if c.get("image_url")}
    cleaned = []
    for d in deals:
        if not isinstance(d, dict) or not d.get("product_name"):
            continue
        slot = "impulse" if d.get("slot") == "impulse" else "main"
        try:
            src = by_no.get(int(d.get("candidate_no") or 0), {})
        except (TypeError, ValueError):
            src = {}
        image_url = str(src.get("image_url") or "")
        try:
            score = int(d.get("score", 85))
        except (TypeError, ValueError):
            score = 85
        reasons = reason_lines(d.get("deal_reason", ""))
        catch_copy = str(d.get("catch_copy") or (reasons[0] if reasons else ""))[:24]
        price = src
        cleaned.append({
            "product_name": str(d["product_name"])[:60],
            "category": str(d.get("category") or ("日用品・家電" if slot == "impulse" else "ガジェット")),
            "slot": slot,
            "badge": BADGES["impulse"] if slot == "impulse" else str(d.get("badge") or BADGES["main"]),
            "catch_copy": catch_copy,
            "deal_reason": str(d.get("deal_reason", "")),
            "sns_text": str(d.get("sns_text", "")),
            "score": max(0, min(100, score)),
            "image_url": image_url if image_url.startswith("https://") else "",
            "price_yen": price.get("price_yen"),
            "point_rate": price.get("point_rate"),
            "item_url": rakuten_item_url(src.get("source_url")),
        })

    # 目玉枠はおすすめ度の高い順に並べてランキングにする
    main = sorted((d for d in cleaned if d["slot"] == "main"), key=lambda d: d["score"], reverse=True)[:4]
    impulse = [d for d in cleaned if d["slot"] == "impulse"][:2]
    for staple in IMPULSE_STAPLES:
        if len(impulse) >= 2:
            break
        if all(staple["product_name"] != d["product_name"] for d in impulse):
            impulse.append(dict(staple, price_yen=None, point_rate=None))
    # 目玉枠を先頭、ついで買い枠を最後に並べる
    return main + impulse


def with_amazon_tag(url):
    return f"{url}{'&' if '?' in url else '?'}tag={AMAZON_TAG}"


def with_rakuten_affiliate(url):
    if not RAKUTEN_AFFILIATE_ID:
        return url
    return f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_AFFILIATE_ID}/?pc={urllib.parse.quote(url, safe='')}"


AMAZON_SALE_URL = with_amazon_tag("https://www.amazon.co.jp/gp/goldbox")
RAKUTEN_TOP_URL = with_rakuten_affiliate("https://www.rakuten.co.jp/")


def rakuten_item_url(url):
    """楽天市場の個別商品ページURLだけを通す（ニュース記事などは除外）"""
    url = str(url or "")
    return url if url.startswith("https://item.rakuten.co.jp/") else ""


def build_affiliate_urls(product_name, item_url=""):
    """Amazonは商品名検索、楽天は商品ページ（無ければ検索ページ）のアフィリエイトURLを生成する"""
    encoded_name = urllib.parse.quote(product_name)
    amazon_url = with_amazon_tag(f"https://www.amazon.co.jp/s?k={encoded_name}")
    rakuten_target = rakuten_item_url(item_url) or f"https://search.rakuten.co.jp/search/mall/{encoded_name}/"
    rakuten_url = with_rakuten_affiliate(rakuten_target)
    return amazon_url, rakuten_url


def build_tweet_url(deal, page_url):
    """X投稿画面を開くURL。リンクはアフィリエイトではなくサイトのトップにする"""
    points = reason_lines(deal.get("deal_reason", ""))[:2] or [deal.get("catch_copy", "")]
    lines = [f"【本日の注目特価】{deal['product_name']}"]
    lines += [f"・{p}" for p in points if p]
    lines += ["詳細・現在の価格はこちら👇", SITE_URL, "#ガジェット #セール"]
    return "https://twitter.com/intent/tweet?" + urllib.parse.urlencode({"text": "\n".join(lines)})


def load_events():
    """data/events.json から、開催中または開催間近の大型セールを読み込む"""
    try:
        with open(EVENTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"セール予定ファイルを読み込めませんでした: {e}")
        return []

    events = []
    for e in data if isinstance(data, list) else []:
        try:
            start = datetime.fromisoformat(e["start"])
            end = datetime.fromisoformat(e["end"])
        except (KeyError, TypeError, ValueError):
            continue
        start = start if start.tzinfo else start.replace(tzinfo=JST)
        end = end if end.tzinfo else end.replace(tzinfo=JST)
        if end < NOW or start > NOW + timedelta(days=EVENT_LOOKAHEAD_DAYS):
            continue
        store = e.get("store", "")
        url = str(e.get("url") or "")
        if not url.startswith("https://"):
            url = "https://www.amazon.co.jp/gp/goldbox" if store == "amazon" else "https://www.rakuten.co.jp/"
        if store == "amazon":
            url = with_amazon_tag(url)
        elif store == "rakuten":
            url = with_rakuten_affiliate(url)
        events.append({
            "name": str(e.get("name", "")),
            "note": str(e.get("note", "")),
            "store": {"amazon": "Amazon", "rakuten": "楽天市場"}.get(store, store),
            "start": start,
            "end": end,
            "url": url,
        })
    events.sort(key=lambda e: e["start"])
    return events


def md_date(dt):
    """2026-10-15 → 10/15(木)"""
    return f"{dt.month}/{dt.day}({WEEKDAYS[dt.weekday()]})"


def md_datetime(dt):
    return f"{md_date(dt)} {dt.hour}:{dt.minute:02d}"


def next_update_text():
    for hour in UPDATE_HOURS:
        if NOW.hour < hour:
            return f"本日 {hour}:00頃"
    return f"明日 {UPDATE_HOURS[0]}:00頃"


def next_rakuten_point_day():
    """楽天市場「5と0のつく日」の直近の日付（ビルド時点。表示はJSでも更新する）"""
    for i in range(7):
        day = NOW + timedelta(days=i)
        if day.day % 5 == 0:
            return "今日は開催日！" if i == 0 else f"次回 {md_date(day)}"
    return ""


def item_art(deal):
    """商品名からジャンル別イラストのファイル名を決める"""
    name = deal["product_name"].lower()
    for keywords, art in ITEM_ART:
        if any(k.lower() in name for k in keywords):
            return art
    return "cart" if deal["slot"] == "impulse" else "gadget"


def thumbnail_html(deal, box_cls, tone, root):
    """商品画像、無ければ商品ジャンルのイラストで表示する"""
    art = f"{root}img/items/{item_art(deal)}.svg"
    if deal["image_url"]:
        return (f'<div class="{box_cls} shrink-0 rounded-3xl bg-white ring-1 ring-slate-100 overflow-hidden flex items-center justify-center">'
                f'<img src="{html.escape(deal["image_url"])}" alt="{html.escape(deal["product_name"])}" loading="lazy" '
                f'class="w-full h-full object-contain p-3" '
                # 画像が読み込めないときはジャンルのイラストに切り替える
                f'onerror="this.onerror=null;this.classList.add(\'p-5\');this.src=\'{art}\'"></div>')
    return (f'<div class="{box_cls} relative shrink-0 rounded-3xl bg-gradient-to-br {tone} overflow-hidden flex items-center justify-center" aria-hidden="true">'
            f'<span class="absolute h-[76%] aspect-square rounded-full bg-white/60"></span>'
            f'<img src="{art}" alt="" loading="lazy" class="relative w-[88%] h-[88%] object-contain"></div>')


def badges_html(deal):
    badge_cls = "bg-emerald-50 text-emerald-700 ring-emerald-100" if deal["slot"] == "impulse" else "bg-rose-50 text-rose-600 ring-rose-100"
    return (f'<div class="flex items-center gap-1.5 flex-wrap">'
            f'<span class="{badge_cls} ring-1 text-xs font-bold px-2.5 py-1 rounded-full">{html.escape(deal["badge"])}</span>'
            f'<span class="bg-sky-50 text-sky-700 ring-1 ring-sky-100 text-xs font-bold px-2.5 py-1 rounded-full">{html.escape(deal["category"])}</span>'
            f'</div>')


def score_html(score):
    return f"""
                <div class="flex items-center gap-2.5 mt-4" title="AIによるおすすめ度">
                    <span class="text-xs font-bold text-ink-soft whitespace-nowrap">AI注目度</span>
                    <div class="flex-1 h-2.5 bg-orange-100 rounded-full overflow-hidden">
                        <div class="h-full rounded-full bg-gradient-to-r from-amber-300 via-orange-400 to-rose-400" style="width:{score}%"></div>
                    </div>
                    <span class="text-lg font-extrabold text-orange-600 tabular-nums leading-none">{score}</span>
                </div>"""


def price_html(deal):
    if not deal.get("price_yen"):
        return ""
    try:
        price = f"¥{int(deal['price_yen']):,}"
    except (TypeError, ValueError):
        return ""
    point = f'<span class="text-xs font-bold text-rose-600 bg-rose-50 ring-1 ring-rose-100 px-2.5 py-1 rounded-full">ポイント{html.escape(str(deal.get("point_rate") or 1))}倍</span>'
    return f"""
                <div class="flex items-center gap-2 mt-4 flex-wrap">
                    <span class="text-xs font-bold text-ink-soft">楽天参考価格</span>
                    <span class="text-2xl font-extrabold text-ink tabular-nums leading-none">{price}</span>
                    {point}
                </div>"""


def reasons_html(deal, text_cls="text-sm"):
    items = "".join(
        f'<li class="flex gap-2.5"><span class="w-5 h-5 mt-0.5 shrink-0 rounded-full bg-emerald-100 text-emerald-600 text-[11px] font-extrabold flex items-center justify-center">✓</span>'
        f'<span>{html.escape(line)}</span></li>'
        for line in reason_lines(deal["deal_reason"])
    )
    return f'<ul class="space-y-2 {text_cls} text-ink leading-relaxed mt-4">{items}</ul>'


def cta_html(deal, page_url, root="", detail_link=True):
    amz_url, rkt_url = build_affiliate_urls(deal["product_name"], deal.get("item_url", ""))
    detail = ""
    if detail_link and deal.get("item_page"):
        detail = (f'<a href="{root}{deal["item_page"]}" class="mt-3 flex items-center justify-center gap-1.5 text-sm font-bold text-orange-600 '
                  f'bg-orange-50 hover:bg-orange-100 ring-1 ring-orange-100 rounded-full py-2.5 transition">'
                  f'<img src="{root}img/icons/chart.svg" alt="" class="w-5 h-5">価格の記録・詳細を見る</a>')
    return f"""
                <div class="grid grid-cols-2 gap-2.5 mt-5">
                    <a href="{html.escape(amz_url)}" target="_blank" rel="nofollow noopener sponsored"
                       class="btn btn-amz flex items-center justify-center gap-1 font-bold py-3 px-2 rounded-full text-[15px]">
                       Amazonで見る <span aria-hidden="true">›</span>
                    </a>
                    <a href="{html.escape(rkt_url)}" target="_blank" rel="nofollow noopener sponsored"
                       class="btn btn-rkt flex items-center justify-center gap-1 font-bold py-3 px-2 rounded-full text-[15px]">
                       楽天で見る <span aria-hidden="true">›</span>
                    </a>
                </div>
                {detail}
                <div class="flex items-center justify-between gap-2 mt-4">
                    <span class="text-xs text-ink-soft">※価格・ポイントはリンク先でご確認ください</span>
                    <a href="{html.escape(build_tweet_url(deal, page_url))}" target="_blank" rel="noopener"
                       class="shrink-0 bg-ink hover:bg-ink-soft text-white font-bold py-2 px-3.5 rounded-full text-xs transition">
                       𝕏 ポスト作成
                    </a>
                </div>"""


def featured_card(deal, page_url, root):
    """ランキング1位の大きなカード"""
    return f"""
            <article id="deal-1" class="card relative col-span-full ring-2 ring-amber-200 p-5 pt-16 md:p-8 md:pt-16">
                <div class="absolute top-4 left-4 md:top-5 md:left-6 flex items-center gap-1.5 bg-gradient-to-r from-amber-400 to-orange-500 text-white text-sm font-extrabold pl-1.5 pr-4 py-1.5 rounded-full shadow-md shadow-orange-200">
                    <span class="w-7 h-7 rounded-full bg-white flex items-center justify-center"><img src="{root}img/icons/trophy.svg" alt="" class="w-5 h-5"></span>本日のNo.1
                </div>
                <div class="flex flex-col md:flex-row gap-5 md:gap-8">
                    {thumbnail_html(deal, "w-full h-60 md:w-72 md:h-72", CARD_TONES[0], root)}
                    <div class="flex-1 min-w-0">
                        {badges_html(deal)}
                        <h3 class="text-xl md:text-2xl font-extrabold text-ink leading-snug mt-3">{html.escape(deal['product_name'])}</h3>
                        <p class="mt-1.5 text-orange-600 font-bold md:text-lg">{html.escape(deal['catch_copy'])}</p>
                        {score_html(deal['score'])}
                        {price_html(deal)}
                        {reasons_html(deal, "text-[15px] md:text-base")}
                        {cta_html(deal, page_url, root)}
                    </div>
                </div>
            </article>"""


def ranked_card(deal, rank, page_url, root):
    rank_style = RANK_STYLES.get(rank, RANK_STYLES[4])
    return f"""
            <article id="deal-{rank}" class="card card-hover relative p-5 md:p-6 flex flex-col">
                <div class="flex gap-4 md:flex-col">
                    <div class="relative shrink-0">
                        {thumbnail_html(deal, "w-24 h-24 md:w-full md:h-44", CARD_TONES[(rank - 1) % len(CARD_TONES)], root)}
                        <span class="absolute -top-2.5 -left-2.5 w-10 h-10 rounded-full bg-gradient-to-br {rank_style} text-sm font-extrabold flex items-center justify-center shadow-md ring-[3px] ring-white">{rank}位</span>
                    </div>
                    <div class="min-w-0 flex-1">
                        {badges_html(deal)}
                        <h3 class="text-[17px] md:text-lg font-extrabold text-ink leading-snug mt-2">{html.escape(deal['product_name'])}</h3>
                        <p class="mt-1 text-sm text-orange-600 font-bold">{html.escape(deal['catch_copy'])}</p>
                    </div>
                </div>
                {score_html(deal['score'])}
                {price_html(deal)}
                <div class="flex-1">{reasons_html(deal)}</div>
                {cta_html(deal, page_url, root)}
            </article>"""


def impulse_card(deal, idx, page_url, root):
    return f"""
            <article id="deal-{idx}" class="card card-hover p-4 md:p-6 flex flex-col">
                <div class="flex gap-4">
                    {thumbnail_html(deal, "w-20 h-20 md:w-24 md:h-24", IMPULSE_TONE, root)}
                    <div class="min-w-0 flex-1">
                        {badges_html(deal)}
                        <h3 class="text-[17px] font-extrabold text-ink leading-snug mt-2">{html.escape(deal['product_name'])}</h3>
                        <p class="mt-1 text-sm text-emerald-700 font-bold">{html.escape(deal['catch_copy'])}</p>
                    </div>
                </div>
                {price_html(deal)}
                <div class="flex-1">{reasons_html(deal)}</div>
                {cta_html(deal, page_url, root)}
            </article>"""


def section_head(icon, title, sub, root, tag=""):
    tag_html = (f'<span class="inline-block text-xs font-bold text-orange-700 bg-orange-100 rounded-full px-3 py-1 mb-1.5">{tag}</span>'
                if tag else "")
    return f"""
            <div class="mb-6">
                <div class="flex items-center gap-3.5 md:gap-4">
                    <span class="shrink-0 w-14 h-14 md:w-16 md:h-16 rounded-[1.25rem] bg-white shadow-soft ring-1 ring-orange-100 flex items-center justify-center">
                        <img src="{root}img/icons/{icon}.svg" alt="" class="w-10 h-10 md:w-11 md:h-11">
                    </span>
                    <div class="min-w-0">
                        {tag_html}
                        <h2 class="text-[1.4rem] md:text-3xl font-extrabold text-ink leading-snug">{title}</h2>
                    </div>
                </div>
                <p class="text-sm md:text-base text-ink-soft mt-3 leading-relaxed">{sub}</p>
            </div>"""


def event_attrs(event):
    state = "live" if event["start"] <= NOW else "soon"
    return (f'data-event-start="{event["start"].isoformat()}" data-event-end="{event["end"].isoformat()}" '
            f'data-state="{state}"')


def event_period(event):
    return f"{md_datetime(event['start'])} 〜 {md_datetime(event['end'])}"


def event_bar_html(events):
    """ページ最上部の大型セール告知（終了したものはJSで隠す）"""
    if not events:
        return ""
    items = ""
    for i, ev in enumerate(events):
        hidden = "" if i == 0 else " hidden"
        items += f"""
        <a href="{html.escape(ev['url'])}" target="_blank" rel="nofollow noopener sponsored" data-event-bar {event_attrs(ev)}{hidden}
           class="block max-w-5xl mx-auto px-4 py-2.5 text-center text-sm font-bold leading-relaxed hover:underline">
            <span class="ev-state text-xs font-extrabold px-2.5 py-0.5 rounded-full mr-1.5">{'開催中' if ev['start'] <= NOW else 'まもなく開始'}</span>
            {html.escape(ev['name'])}
            <span class="font-extrabold text-yellow-100 ml-1 whitespace-nowrap" data-event-countdown>{html.escape(event_period(ev))}</span>
            <span class="ml-1 underline whitespace-nowrap">会場を見る →</span>
        </a>"""
    return f'<div id="event-bar" class="bg-gradient-to-r from-rose-600 to-orange-600 text-white">{items}\n    </div>'


def sale_card(href, icon, bubble, label_html, store, title, body, link_text, link_cls, root, attrs=""):
    return f"""
                <a href="{html.escape(href)}" target="_blank" rel="nofollow noopener sponsored" {attrs}
                   class="card card-hover block p-5 md:p-6">
                    <div class="flex items-center gap-3">
                        <span class="shrink-0 w-14 h-14 rounded-2xl {bubble} flex items-center justify-center"><img src="{root}img/icons/{icon}.svg" alt="" class="w-10 h-10"></span>
                        <div class="min-w-0 flex flex-col items-start gap-1">
                            {label_html}
                            <span class="text-xs font-bold text-ink-soft">{html.escape(store)}</span>
                        </div>
                    </div>
                    <h3 class="font-extrabold text-xl text-ink leading-snug mt-4">{html.escape(title)}</h3>
                    {body}
                    <span class="inline-flex items-center gap-1 mt-4 text-sm font-bold {link_cls}">{link_text} <span aria-hidden="true">→</span></span>
                </a>"""


def sale_info_html(events, root):
    cards = ""
    for ev in events:
        note = f'<p class="text-sm text-ink-soft mt-2 leading-relaxed">{html.escape(ev["note"])}</p>' if ev["note"] else ""
        label = f'<span class="ev-state text-xs font-extrabold px-2.5 py-0.5 rounded-full whitespace-nowrap">{"開催中" if ev["start"] <= NOW else "まもなく開始"}</span>'
        body = f"""
                    <p class="text-sm text-ink-soft mt-2">{html.escape(event_period(ev))}</p>
                    <p class="text-[15px] font-extrabold text-rose-600 mt-1" data-event-countdown></p>
                    {note}"""
        cards += sale_card(ev["url"], "megaphone", "bg-orange-50", label, ev["store"], ev["name"], body,
                           "セール会場を見る", "text-orange-600", root, event_attrs(ev))
    cards += sale_card(
        RAKUTEN_TOP_URL, "coin", "bg-amber-50",
        '<span class="text-xs font-extrabold px-2.5 py-0.5 rounded-full bg-red-600 text-white whitespace-nowrap">毎月6回</span>',
        "楽天市場", "5と0のつく日",
        f"""
                    <p class="text-[15px] font-extrabold text-rose-600 mt-2" id="rakuten-day">{next_rakuten_point_day()}</p>
                    <p class="text-sm text-ink-soft mt-1 leading-relaxed">エントリー＆楽天カード決済でポイントアップ。高額ガジェットはこの日にまとめるのが定番です。</p>""",
        "楽天市場を見る", "text-red-600", root, "data-rakuten-day")
    cards += sale_card(
        AMAZON_SALE_URL, "clock", "bg-sky-50",
        '<span class="text-xs font-extrabold px-2.5 py-0.5 rounded-full bg-ink text-amber-200 whitespace-nowrap">毎日開催</span>',
        "Amazon", "タイムセール",
        """
                    <p class="text-[15px] font-extrabold text-rose-600 mt-2">人気商品が日替わりで登場</p>
                    <p class="text-sm text-ink-soft mt-1 leading-relaxed">数量限定の特選タイムセールは売り切れ次第終了。気になる商品は早めのチェックがおすすめです。</p>""",
        "タイムセール会場を見る", "text-orange-600", root)
    # 楽天・Amazonの常設カード2枚を足した枚数で、空きマスが出にくい列数にする
    cols = "md:grid-cols-2" if (len(events) + 2) % 2 == 0 and len(events) + 2 < 6 else "md:grid-cols-2 lg:grid-cols-3"
    return f"""
        <section id="sale-info" class="scroll-mt-24">
            {section_head("megaphone", "開催中・まもなく開始のセール", "大型セールやポイントアップ日に買うと、同じ商品でも実質価格が下がります。", root)}
            <div class="grid gap-5 {cols}">{cards}
            </div>
        </section>"""


def archive_html(history, root, page_date):
    items = ""
    for entry in history:
        products = entry.get("products", [])
        try:
            label = md_date(datetime.strptime(entry["date"], "%Y-%m-%d"))
        except ValueError:
            label = entry["date"]
        current = entry["date"] == page_date
        ring = "ring-2 ring-orange-300 bg-orange-50" if current else "ring-1 ring-orange-100 bg-white"
        top = html.escape(products[0]) if products else ""
        items += f"""
                <li><a href="{root}archive/{entry['date']}.html" class="block h-full rounded-2xl {ring} p-4 shadow-sm hover:shadow-soft hover:-translate-y-0.5 transition">
                    <span class="flex items-center justify-between gap-2">
                        <span class="font-extrabold text-ink">{label}</span>
                        <span class="text-xs font-bold text-orange-700 bg-orange-100 rounded-full px-2 py-0.5">{len(products)}件</span>
                    </span>
                    <span class="block text-sm text-ink-soft mt-1.5 leading-snug line-clamp-2">{top}</span>
                </a></li>"""
    return f"""
        <section id="archive" class="scroll-mt-24">
            {section_head("calendar", "過去のお買い得アーカイブ", "日ごとの厳選リストを30日分保存しています。値動きのチェックにどうぞ。", root)}
            <ul class="grid grid-cols-2 md:grid-cols-4 gap-3">{items}
            </ul>
        </section>"""


HOW_TO_STEPS = [
    ("clock", "bg-sky-50", "AIが毎日2回チェック", "家電・ガジェット系ニュースや楽天市場の人気商品など、公開情報から候補を自動で集めます。"),
    ("chart", "bg-amber-50", "注目度をスコア化", "値下げ幅・定番度・話題性をAIが判定し、買い時の商品をランキングにします。"),
    ("cart", "bg-emerald-50", "Amazon・楽天をワンタップ比較", "ボタンから両ストアの販売ページへ。ポイント還元込みの実質価格を比べて選べます。"),
]

FAQ = [
    ("掲載商品はどうやって選んでいますか？",
     "家電・ガジェット系ニュースや楽天市場の人気商品などの公開情報をもとに、AIが値下げ幅・定番度・話題性を判定して毎日2回自動で選んでいます。"),
    ("「実質最安値」とは何ですか？",
     "販売価格からポイント還元やクーポンを差し引いた、実際の負担額のことです。還元率は会員ランクやキャンペーンのエントリー状況で変わるため、最終的な価格は各ストアでご確認ください。"),
    ("「ついで買い定番」とは何ですか？",
     "送料無料ラインやポイントアップ条件に届かせたいときに追加しやすい、手頃な定番品です。ケーブルや乾電池など、いつか必ず使うものを選んでいます。"),
]


def about_html(root):
    steps = "".join(f"""
                <div class="card p-5 md:p-6">
                    <div class="flex items-center gap-3">
                        <span class="w-14 h-14 rounded-2xl {bubble} flex items-center justify-center"><img src="{root}img/icons/{icon}.svg" alt="" class="w-10 h-10"></span>
                        <span class="text-xs font-extrabold text-orange-700 bg-orange-100 rounded-full px-2.5 py-1">STEP {i}</span>
                    </div>
                    <h3 class="font-extrabold text-lg text-ink mt-4">{title}</h3>
                    <p class="text-sm text-ink-soft mt-1.5 leading-relaxed">{text}</p>
                </div>""" for i, (icon, bubble, title, text) in enumerate(HOW_TO_STEPS, 1))
    faq = "".join(f"""
                <details class="group card !rounded-2xl p-4 md:p-5">
                    <summary class="flex items-center justify-between gap-3 cursor-pointer font-bold text-ink list-none">
                        <span class="flex items-start gap-2.5"><span class="w-7 h-7 shrink-0 rounded-full bg-orange-100 text-orange-600 text-sm font-extrabold flex items-center justify-center">Q</span><span class="pt-0.5">{html.escape(q)}</span></span>
                        <span class="w-8 h-8 shrink-0 rounded-full bg-orange-50 text-orange-500 group-open:rotate-45 transition text-xl leading-none flex items-center justify-center">+</span>
                    </summary>
                    <p class="text-sm text-ink-soft mt-3 pl-[2.375rem] leading-relaxed">{html.escape(a)}</p>
                </details>""" for q, a in FAQ)
    return f"""
        <section id="about" class="scroll-mt-24">
            {section_head("robot", "このサイトの使い方", "セール情報を追いかける手間を、AIが代わりに引き受けます。", root)}
            <div class="grid gap-5 md:grid-cols-3">{steps}
            </div>
            <div class="grid gap-3 mt-6">{faq}
            </div>
        </section>"""


TAILWIND_CONFIG = """
        tailwind.config = {
            theme: {
                extend: {
                    colors: { ink: { DEFAULT: '#2b3150', soft: '#555d80' }, cream: '#fffaf3' },
                    boxShadow: { soft: '0 1px 2px rgba(43,49,80,.05), 0 12px 32px -12px rgba(43,49,80,.18)' }
                }
            }
        };
"""

# __ROOT__ はページの階層に合わせて render_page で置き換える
PAGE_CSS = """
        html { scroll-behavior: smooth; }
        body {
            font-family: 'M PLUS Rounded 1c', 'Hiragino Maru Gothic ProN', 'Hiragino Sans', 'Meiryo', system-ui, sans-serif;
            font-weight: 500; color: #2b3150; background: #fffaf3;
            line-break: strict; -webkit-font-smoothing: antialiased;
        }
        h1, h2 { word-break: auto-phrase; text-wrap: balance; }
        h3, p, li { word-break: auto-phrase; text-wrap: pretty; }
        .hero-bg {
            background:
                radial-gradient(55% 65% at 92% 18%, rgba(255, 205, 160, .75), transparent 70%),
                radial-gradient(45% 55% at 0% 95%, rgba(196, 240, 222, .9), transparent 70%),
                radial-gradient(40% 45% at 8% 0%, rgba(210, 234, 255, .95), transparent 70%),
                #fff5ea;
        }
        .pattern { background-image: url('__ROOT__img/pattern.svg'); background-size: 180px 180px; }
        .marker {
            background: linear-gradient(transparent 62%, #ffd66b 62%, #ffd66b 92%, transparent 92%);
            padding: 0 .08em; -webkit-box-decoration-break: clone; box-decoration-break: clone;
        }
        .card {
            background: #fff; border-radius: 1.75rem;
            box-shadow: 0 1px 2px rgba(43, 49, 80, .05), 0 12px 32px -12px rgba(43, 49, 80, .18);
        }
        .card:not([class*="ring-"]) { box-shadow: 0 0 0 1px #ffe9d6, 0 1px 2px rgba(43, 49, 80, .05), 0 12px 32px -12px rgba(43, 49, 80, .18); }
        .card-hover { transition: transform .2s, box-shadow .2s; }
        .card-hover:hover { transform: translateY(-3px); box-shadow: 0 0 0 1px #ffd9b8, 0 18px 40px -14px rgba(43, 49, 80, .28); }
        .btn { transition: transform .1s, box-shadow .1s, filter .15s; }
        .btn:hover { filter: brightness(1.05); }
        .btn:active { transform: translateY(3px); box-shadow: none; }
        .btn-amz { background: #ff9900; color: #1f2537; box-shadow: 0 4px 0 #db7f00; }
        .btn-rkt { background: #bf0000; color: #fff; box-shadow: 0 4px 0 #8a0000; }
        .btn-main { background: #e11d48; color: #fff; box-shadow: 0 4px 0 #9f1239; }
        .ev-state { background: #ffe066; color: #2b3150; }
        [data-state="live"] .ev-state { background: #fff; color: #e11d48; }
        #sale-info [data-state="live"] .ev-state, [data-rakuten-day][data-state="live"] .ev-state { background: #e11d48; color: #fff; }
        summary::-webkit-details-marker { display: none; }
        .no-scrollbar { scrollbar-width: none; }
        .no-scrollbar::-webkit-scrollbar { display: none; }
        [hidden] { display: none !important; }
"""

PAGE_JS = """
    (function () {
        function pad(n) { return (n < 10 ? '0' : '') + n; }
        function left(ms) {
            var s = Math.max(0, Math.floor(ms / 1000)), d = Math.floor(s / 86400),
                h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
            return d > 0 ? d + '日' + h + '時間' + pad(m) + '分' : h + ':' + pad(m) + ':' + pad(s % 60);
        }
        function tick() {
            var now = Date.now(), barShown = false;
            document.querySelectorAll('[data-event-start]').forEach(function (el) {
                var st = Date.parse(el.dataset.eventStart), en = Date.parse(el.dataset.eventEnd);
                var ended = now > en, live = now >= st && !ended;
                if (el.hasAttribute('data-event-bar')) {
                    var show = !ended && !barShown;
                    el.hidden = !show;
                    if (show) barShown = true;
                } else {
                    el.hidden = ended;
                }
                el.dataset.state = live ? 'live' : 'soon';
                var label = el.querySelector('.ev-state'), cd = el.querySelector('[data-event-countdown]');
                if (label) label.textContent = live ? '開催中' : 'まもなく開始';
                if (cd) cd.textContent = live ? '終了まで あと' + left(en - now) : '開始まで あと' + left(st - now);
            });
            var bar = document.getElementById('event-bar');
            if (bar) bar.hidden = !barShown;
        }
        function rakutenDay() {
            var el = document.getElementById('rakuten-day');
            if (!el) return;
            var j = new Date(Date.now() + 9 * 3600000), w = '日月火水木金土';
            for (var i = 0; i < 7; i++) {
                var t = new Date(Date.UTC(j.getUTCFullYear(), j.getUTCMonth(), j.getUTCDate() + i));
                if (t.getUTCDate() % 5 === 0) {
                    el.textContent = i === 0 ? '今日は開催日！' : '次回 ' + (t.getUTCMonth() + 1) + '/' + t.getUTCDate() + '(' + w[t.getUTCDay()] + ')';
                    el.closest('[data-rakuten-day]').dataset.state = i === 0 ? 'live' : 'soon';
                    return;
                }
            }
        }
        function updatedAgo() {
            document.querySelectorAll('[data-updated]').forEach(function (el) {
                var min = Math.floor((Date.now() - Date.parse(el.dataset.updated)) / 60000);
                if (isNaN(min) || min < 0) return;
                el.textContent = min < 60 ? '（' + Math.max(1, min) + '分前）' : min < 1440 ? '（' + Math.floor(min / 60) + '時間前）' : '';
            });
        }
        tick(); rakutenDay(); updatedAgo();
        setInterval(tick, 1000);
        setInterval(updatedAgo, 60000);
    })();
"""


def json_ld(deals, page_url, page_label):
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL, "description": SITE_TAGLINE, "inLanguage": "ja"},
            {
                "@type": "ItemList",
                "name": f"{page_label}のお買い得ガジェット",
                "itemListElement": [
                    {"@type": "ListItem", "position": i, "name": d["product_name"], "url": f"{page_url}#deal-{i}"}
                    for i, d in enumerate(deals, 1)
                ],
            },
        ],
    }
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def stat_card(icon, label, value, root):
    return f"""
                    <div class="bg-white rounded-2xl ring-1 ring-orange-100 shadow-sm p-2.5 md:p-4">
                        <p class="flex items-center gap-1 md:gap-1.5 text-xs font-bold text-ink-soft whitespace-nowrap"><img src="{root}img/icons/{icon}.svg" alt="" class="w-4 h-4 md:w-6 md:h-6">{label}</p>
                        <div class="text-ink font-extrabold leading-tight mt-1.5">{value}</div>
                    </div>"""


def render_page(deals, history, page_date, root, page_url, events=()):
    """スマホ・PC対応のページHTMLを組み立てる（root はサイト直下への相対パス）"""
    is_archive = root != ""
    page_dt = datetime.strptime(page_date, "%Y-%m-%d")
    page_label = f"{page_dt.month}月{page_dt.day}日({WEEKDAYS[page_dt.weekday()]})"
    main_deals = [d for d in deals if d["slot"] == "main"]
    impulse_deals = [d for d in deals if d["slot"] == "impulse"]

    # 2位以下が3件なら3列、2件以下なら2列にして空きマスを作らない
    ranking_cols = "md:grid-cols-2 lg:grid-cols-3" if len(main_deals) >= 4 else "md:grid-cols-2"
    ranking_cards = ""
    for rank, deal in enumerate(main_deals, 1):
        ranking_cards += featured_card(deal, page_url, root) if rank == 1 else ranked_card(deal, rank, page_url, root)
    impulse_cards = "".join(impulse_card(d, len(main_deals) + i, page_url, root) for i, d in enumerate(impulse_deals, 1))

    picks = ""
    for i, deal in enumerate(deals, 1):
        picks += (f'<a href="#deal-{i}" class="shrink-0 max-w-[16rem] flex items-center gap-2 bg-white hover:bg-orange-50 ring-1 ring-orange-100 shadow-sm '
                  f'rounded-full pl-1 pr-4 py-1 text-sm font-bold text-ink transition">'
                  f'<img src="{root}img/items/{item_art(deal)}.svg" alt="" class="w-9 h-9 shrink-0 rounded-full bg-orange-50">'
                  f'<span class="truncate">{html.escape(deal["product_name"])}</span></a>')

    top_names = "、".join(d["product_name"] for d in main_deals[:3])
    description = (f"{page_label}更新｜{top_names}など、AIが厳選した今日のお買い得ガジェット{len(deals)}選。"
                   f"Amazon・楽天のセール情報とポイントアップ日もまとめてチェックできます。")
    if is_archive:
        title = f"【{page_dt.year}年{page_label}】お買い得ガジェット{len(deals)}選｜{SITE_NAME}"
        h1 = f'{page_label}の<br><span class="marker">お買い得ガジェット</span>{len(deals)}選'
        lead = f"{page_dt.year}年{page_label}にAIが厳選したセール・値下げ情報のアーカイブです。価格やポイント倍率は変わっている可能性があるため、最新情報はトップページでご確認ください。"
        third_stat = ("calendar", "掲載日", md_date(page_dt), "")
        crumbs = (f'<nav class="text-sm text-ink-soft mb-4" aria-label="パンくずリスト"><a href="{root}index.html" class="hover:text-orange-600 underline-offset-2 hover:underline">ホーム</a>'
                  f' › <a href="{root}index.html#archive" class="hover:text-orange-600 underline-offset-2 hover:underline">アーカイブ</a> › <span class="text-ink font-bold">{md_date(page_dt)}</span></nav>')
        archive_notice = f"""
        <div class="bg-amber-50 ring-1 ring-amber-200 text-amber-950 rounded-[1.5rem] p-4 md:p-5 flex flex-col md:flex-row md:items-center gap-3 justify-between">
            <span class="flex items-center gap-3 text-[15px] font-bold"><img src="{root}img/icons/calendar.svg" alt="" class="w-9 h-9 shrink-0">このページは{page_dt.year}年{page_label}時点のアーカイブです。</span>
            <a href="{root}index.html" class="btn btn-amz shrink-0 font-bold px-5 py-3 rounded-full text-center">最新のお買い得情報を見る →</a>
        </div>"""
    else:
        title = f"【{md_date(page_dt)}更新】今日のお買い得ガジェット{len(deals)}選・セール情報｜{SITE_NAME}"
        h1 = 'AIが選ぶ、今日の<br><span class="marker">お買い得ガジェット</span>'
        lead = "Amazon・楽天市場のセールや値下げ情報から、AIが買い時の商品を毎日2回ピックアップ。ポイント還元込みの「実質価格」を各ストアですぐ比較できます。"
        third_stat = ("calendar", "次回更新", *next_update_text().split(" ", 1))
        crumbs = ""
        archive_notice = ""

    updated_iso = NOW.isoformat()
    tweet_page_url = "https://twitter.com/intent/tweet?" + urllib.parse.urlencode({
        "text": f"【{md_date(page_dt)}】AIが厳選した今日のお買い得ガジェット{len(deals)}選 #ガジェット #セール情報",
        "url": page_url,
    })
    stats = (stat_card("chart", "本日の厳選", f'<span class="text-2xl md:text-3xl">{len(deals)}</span><span class="text-sm ml-0.5">件</span>', root)
             + stat_card("clock", "最終更新", f'<span class="block text-sm md:text-base">{md_date(NOW)}</span><span class="block text-sm md:text-base">{NOW.hour}:{NOW.minute:02d}</span>'
                         f'<span class="block text-xs font-bold text-emerald-600" data-updated="{updated_iso}"></span>', root)
             + stat_card(third_stat[0], third_stat[1], ''.join(f'<span class="block text-sm md:text-base">{v}</span>' for v in third_stat[2:] if v), root))

    impulse_section = ""
    if impulse_cards:
        impulse_section = f"""
        <section id="impulse" class="scroll-mt-24 bg-emerald-50 ring-1 ring-emerald-100 rounded-[2rem] px-3 py-6 md:p-8 -mx-2 md:mx-0">
            {section_head("cart", "ついで買いで、もう1品お得に", "送料無料ラインやポイントアップ条件にあと少し届かない時に。いつか必ず使う手頃な定番品です。", root)}
            <div class="grid gap-5 md:grid-cols-2">{impulse_cards}
            </div>
        </section>"""

    nav_cls = "px-3 py-2 rounded-full hover:bg-orange-50 hover:text-orange-600 transition"
    return f"""{head_html(title, description, page_url, root, 'article' if is_archive else 'website', json_ld(deals, page_url, page_label))}
    {event_bar_html(events)}
    <header class="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-orange-100">
        <div class="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
            <a href="{root}index.html" class="flex items-center gap-2.5 min-w-0">
                <img src="{root}img/logo.svg" alt="" class="w-10 h-10 shrink-0">
                <span class="leading-tight min-w-0">
                    <span class="block text-xs font-bold text-orange-600">AI厳選</span>
                    <span class="block font-extrabold text-[17px] text-ink truncate">ガジェット特価速報</span>
                </span>
            </a>
            <nav class="hidden md:flex items-center gap-1 text-sm font-bold text-ink-soft">
                <a href="#ranking" class="{nav_cls}">ランキング</a>
                <a href="#impulse" class="{nav_cls}">ついで買い</a>
                <a href="#sale-info" class="{nav_cls}">セール情報</a>
                <a href="#archive" class="{nav_cls}">アーカイブ</a>
            </nav>
            <a href="{html.escape(AMAZON_SALE_URL)}" target="_blank" rel="nofollow noopener sponsored"
               class="btn btn-amz shrink-0 text-sm font-bold px-4 py-2.5 rounded-full">セール会場 ↗</a>
        </div>
    </header>

    <section class="hero-bg relative overflow-hidden">
        <div class="pattern absolute inset-0" aria-hidden="true"></div>
        <div class="relative max-w-5xl mx-auto px-4 pt-7 pb-16 md:pt-12 md:pb-24 md:grid md:grid-cols-[1.15fr_.85fr] md:items-center md:gap-6">
            <div class="min-w-0">
                {crumbs}
                <div class="inline-flex items-center gap-2 bg-white ring-1 ring-orange-100 shadow-sm rounded-full px-3.5 py-1.5 text-sm font-bold text-ink">
                    <span class="relative flex h-2.5 w-2.5"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span></span>
                    毎日7時・18時にAIが自動更新
                </div>
                <h1 class="mt-5 text-[1.85rem] md:text-5xl font-extrabold text-ink leading-[1.35] md:leading-[1.3]">{h1}</h1>
                <p class="mt-4 text-ink-soft text-[15px] md:text-lg leading-relaxed">{lead}</p>
                <img src="{root}img/hero.svg" alt="" class="md:hidden w-full max-w-[17rem] mx-auto mt-4 -mb-1">
                <div class="grid grid-cols-3 gap-2 md:gap-3 mt-5 md:mt-7">{stats}
                </div>
                <div class="flex flex-col sm:flex-row gap-3 mt-6">
                    <a href="#ranking" class="btn btn-main text-center font-extrabold px-6 py-3.5 rounded-full">{"この日" if is_archive else "今日"}のランキングを見る</a>
                    <a href="{html.escape(AMAZON_SALE_URL)}" target="_blank" rel="nofollow noopener sponsored" class="text-center bg-white hover:bg-orange-50 ring-1 ring-orange-200 text-ink font-bold px-6 py-3.5 rounded-full shadow-sm transition">Amazonタイムセール会場 ↗</a>
                </div>
            </div>
            <div class="hidden md:block">
                <img src="{root}img/hero.svg" alt="" class="w-full max-w-[28rem] ml-auto">
            </div>
            <div class="md:col-span-2 mt-7 md:mt-8">
                <p class="text-sm font-bold text-ink mb-2.5">{"この日" if is_archive else "今日"}のピックアップ</p>
                <div class="flex gap-2 overflow-x-auto no-scrollbar -mx-4 px-4 pb-1 md:mx-0 md:px-0 md:flex-wrap">{picks}</div>
            </div>
        </div>
        <svg class="absolute bottom-0 inset-x-0 w-full h-10 md:h-16" viewBox="0 0 1440 100" preserveAspectRatio="none" aria-hidden="true">
            <path fill="#fffaf3" d="M0 56 C 240 100 480 100 720 64 S 1200 8 1440 44 V100 H0 Z"/>
        </svg>
    </section>

    <main class="max-w-5xl mx-auto px-4 pt-6 pb-16 space-y-16 md:space-y-20">
        {archive_notice}
        <section id="ranking" class="scroll-mt-24">
            {section_head("trophy", "注目ガジェット ランキング", "AIがお買い得度・注目度の高い順に並べました。価格・ポイントはボタンから各ストアで確認できます。", root, page_label)}
            <div class="grid gap-5 md:gap-6 {ranking_cols}">{ranking_cards}
            </div>
        </section>
        {impulse_section}
        {sale_info_html(events, root)}
        <section class="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-orange-100 via-rose-100 to-violet-100 p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-5">
            <div class="pattern absolute inset-0" aria-hidden="true"></div>
            <div class="relative flex items-center gap-4">
                <span class="shrink-0 w-16 h-16 rounded-[1.25rem] bg-white shadow-soft flex items-center justify-center"><img src="{root}img/icons/share.svg" alt="" class="w-11 h-11"></span>
                <div>
                    <p class="text-lg md:text-xl font-extrabold text-ink">お得情報を友だちにも教えよう</p>
                    <p class="text-sm text-ink-soft mt-1 leading-relaxed">このページは毎日7時・18時に自動で更新されます。ブックマークもおすすめです。</p>
                </div>
            </div>
            <a href="{html.escape(tweet_page_url)}" target="_blank" rel="noopener" class="relative shrink-0 bg-ink hover:bg-ink-soft text-white font-bold px-6 py-3.5 rounded-full text-center shadow-md transition">𝕏 このページをポスト</a>
        </section>
        {about_html(root)}
        {archive_html(history, root, page_date)}
    </main>
{footer_html(root)}"""


def head_html(title, description, page_url, root, og_type, ld_json):
    """全ページ共通の <head> と【PR】表記"""
    og_image = f"{SITE_URL}{OG_IMAGE}"
    page_css = PAGE_CSS.replace("__ROOT__", root)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>{html.escape(title)}</title>
    <meta name="description" content="{html.escape(description)}">
    <link rel="canonical" href="{html.escape(page_url)}">
    <meta name="theme-color" content="#fff5ea">
    <link rel="icon" type="image/svg+xml" href="{root}img/logo.svg">
    <link rel="apple-touch-icon" href="{root}apple-touch-icon.png">
    <meta property="og:title" content="{html.escape(title)}">
    <meta property="og:description" content="{html.escape(description)}">
    <meta property="og:type" content="{og_type}">
    <meta property="og:url" content="{html.escape(page_url)}">
    <meta property="og:site_name" content="{html.escape(SITE_NAME)}">
    <meta property="og:locale" content="ja_JP">
    <meta property="og:image" content="{html.escape(og_image)}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html.escape(title)}">
    <meta name="twitter:description" content="{html.escape(description)}">
    <meta name="twitter:image" content="{html.escape(og_image)}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@400;500;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>{TAILWIND_CONFIG}    </script>
    <style>{page_css}    </style>
    <script type="application/ld+json">{ld_json}</script>
    <script data-goatcounter="https://namikilog.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
</head>
<body class="bg-cream min-h-screen text-ink pb-24 md:pb-0">
    <div class="bg-white/80 text-ink-soft text-xs text-center py-1.5 px-4 border-b border-orange-100 leading-relaxed">【PR】当サイトはアフィリエイト広告（Amazonアソシエイト・楽天アフィリエイト）を利用しています</div>"""


def footer_html(root):
    """全ページ共通のフッター・スマホ下部ボタン"""
    return f"""
    <footer class="bg-white border-t border-orange-100 text-[13px] text-ink-soft">
        <div class="max-w-5xl mx-auto px-4 py-10 space-y-3 leading-relaxed">
            <p class="flex items-center gap-2.5 text-ink font-extrabold text-base"><img src="{root}img/logo.svg" alt="" class="w-8 h-8">{html.escape(SITE_NAME)}</p>
            <p>{html.escape(SITE_TAGLINE)}。セール・値下げ情報を毎日7時・18時に自動更新しています。</p>
            <p>Amazonのアソシエイトとして、当サイトは適格販売により収入を得ています。また、楽天アフィリエイトを利用しています。</p>
            <p>掲載内容はAIが公開情報をもとに自動生成したものです。価格・在庫・ポイント倍率は変動するため、購入前に必ず各販売ページでご確認ください。</p>
            <p class="text-xs">最終更新: {TODAY_STR}（日本時間） © {NOW.year} {html.escape(SITE_NAME)}</p>
        </div>
    </footer>

    <div class="fixed bottom-0 inset-x-0 z-40 md:hidden bg-white/95 backdrop-blur border-t border-orange-100 px-3 pt-2.5 pb-[calc(.75rem+env(safe-area-inset-bottom))] grid grid-cols-2 gap-2.5">
        <a href="{html.escape(AMAZON_SALE_URL)}" target="_blank" rel="nofollow noopener sponsored" class="btn btn-amz text-center font-bold py-3 rounded-full text-sm">Amazonセール会場</a>
        <a href="{html.escape(RAKUTEN_TOP_URL)}" target="_blank" rel="nofollow noopener sponsored" class="btn btn-rkt text-center font-bold py-3 rounded-full text-sm">楽天市場を見る</a>
    </div>
    <script>{PAGE_JS}</script>
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


def product_id(deal):
    """楽天の商品ページURL（無ければ商品名）から、商品ページ用の固定IDを作る"""
    key = deal.get("item_url") or deal["product_name"]
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def load_products():
    try:
        with open(PRODUCTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"商品データの読み込みに失敗したため新規作成します: {e}")
        return {}


def update_products(products, deals):
    """掲載した商品ごとに、掲載日時と楽天の参考価格を記録する（見本データは除く）"""
    for deal in deals:
        if deal.get("is_sample"):
            continue
        pid = product_id(deal)
        deal["item_page"] = f"item/{pid}.html"
        info = products.get(pid, {"records": []})
        for key in ("product_name", "category", "slot", "badge", "catch_copy", "deal_reason", "score", "image_url", "item_url"):
            if deal.get(key) or key not in info:
                info[key] = deal.get(key)
        records = [r for r in info["records"] if r.get("t") != TODAY_STR]
        records.append({"t": TODAY_STR, "price": deal.get("price_yen"), "point": deal.get("point_rate")})
        info["records"] = records[-PRODUCT_RECORDS:]
        info["last_seen"] = TODAY_STR
        products[pid] = info
    # 長く掲載されていない商品は削除してデータを肥大化させない
    cutoff = (NOW - timedelta(days=PRODUCT_KEEP_DAYS)).strftime("%Y-%m-%d")
    products = {k: v for k, v in products.items() if v.get("last_seen", "") >= cutoff}
    os.makedirs(os.path.dirname(PRODUCTS_PATH), exist_ok=True)
    with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=1)
    return products


def price_points(info):
    points = []
    for r in info.get("records", []):
        try:
            points.append((r["t"], int(r["price"]), r.get("point") or 1))
        except (KeyError, TypeError, ValueError):
            continue
    return points


def price_chart_svg(points):
    """価格の推移を折れ線グラフ（SVG）で描く"""
    w, h, pad_x, pad_y = 640, 240, 84, 28
    prices = [p for _, p, _ in points]
    lo, hi = min(prices), max(prices)
    span = max(hi - lo, max(hi * 0.05, 1))
    lo -= span * 0.15
    hi = lo + span * 1.3

    def xy(i, p):
        x = pad_x + (w - pad_x - 16) * (i / (len(points) - 1))
        y = pad_y + (h - pad_y * 2) * (1 - (p - lo) / (hi - lo))
        return x, y

    coords = [xy(i, p) for i, (_, p, _) in enumerate(points)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = f"{coords[0][0]:.1f},{h - pad_y} {line} {coords[-1][0]:.1f},{h - pad_y}"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#fff" stroke="#f97316" stroke-width="3"/>' for x, y in coords)
    labels = ""
    for value in (max(prices), min(prices)):
        _, y = xy(0, value)
        labels += (f'<line x1="{pad_x}" x2="{w - 16}" y1="{y:.1f}" y2="{y:.1f}" stroke="#fed7aa" stroke-dasharray="4 5"/>'
                   f'<text x="{pad_x - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="17" font-weight="700" fill="#7c6f64">¥{value:,}</text>')
    first, last = points[0][0], points[-1][0]
    labels += (f'<text x="{pad_x}" y="{h - 6}" font-size="15" fill="#7c6f64">{html.escape(first[5:16].replace("-", "/"))}</text>'
               f'<text x="{w - 16}" y="{h - 6}" text-anchor="end" font-size="15" fill="#7c6f64">{html.escape(last[5:16].replace("-", "/"))}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="w-full h-auto" role="img" aria-label="楽天参考価格の推移">'
            f'<defs><linearGradient id="pg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#fdba74" stop-opacity=".45"/>'
            f'<stop offset="1" stop-color="#fdba74" stop-opacity="0"/></linearGradient></defs>'
            f'{labels}<polygon points="{area}" fill="url(#pg)"/>'
            f'<polyline points="{line}" fill="none" stroke="#f97316" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round"/>{dots}</svg>')


def price_history_html(info):
    points = price_points(info)
    seen = len(info.get("records", []))
    if not points:
        return f"""
            <section class="card p-5 md:p-7">
                <h2 class="text-lg md:text-xl font-extrabold text-ink">価格の記録</h2>
                <p class="text-sm text-ink-soft mt-3 leading-relaxed">この商品は楽天の参考価格を取得できなかったため、価格の記録はありません（掲載{seen}回）。最新の価格は各ストアでご確認ください。</p>
            </section>"""
    prices = [p for _, p, _ in points]
    latest = prices[-1]
    if len(prices) >= 2 and latest <= min(prices):
        verdict = ("bg-emerald-50 text-emerald-700 ring-emerald-100", "これまでの記録で最も安い価格")
    elif len(prices) >= 2 and latest < max(prices):
        verdict = ("bg-amber-50 text-amber-700 ring-amber-100", f"最安記録より ¥{latest - min(prices):,} 高め")
    elif len(prices) >= 2:
        verdict = ("bg-rose-50 text-rose-600 ring-rose-100", "記録中では高めの価格です")
    else:
        verdict = ("bg-sky-50 text-sky-700 ring-sky-100", "記録を始めたばかりです")
    stats = "".join(
        f'<div class="bg-orange-50/60 rounded-2xl p-3 text-center"><p class="text-xs font-bold text-ink-soft">{label}</p>'
        f'<p class="text-lg md:text-xl font-extrabold text-ink tabular-nums mt-1">{value}</p></div>'
        for label, value in (("最新", f"¥{latest:,}"), ("最安記録", f"¥{min(prices):,}"), ("最高記録", f"¥{max(prices):,}"), ("掲載回数", f"{seen}回"))
    )
    chart = price_chart_svg(points) if len(points) >= 2 else ""
    rows = "".join(
        f'<tr class="border-t border-orange-100"><td class="py-2.5 pr-3 whitespace-nowrap">{html.escape(t[:16].replace("-", "/"))}</td>'
        f'<td class="py-2.5 pr-3 text-right font-bold tabular-nums">¥{p:,}</td>'
        f'<td class="py-2.5 text-right whitespace-nowrap">{html.escape(str(pt))}倍</td></tr>'
        for t, p, pt in reversed(points)
    )
    return f"""
            <section class="card p-5 md:p-7">
                <div class="flex items-center justify-between gap-3 flex-wrap">
                    <h2 class="text-lg md:text-xl font-extrabold text-ink">楽天参考価格の記録</h2>
                    <span class="{verdict[0]} ring-1 text-sm font-bold px-3 py-1 rounded-full">{verdict[1]}</span>
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-2.5 mt-4">{stats}</div>
                <div class="mt-5">{chart}</div>
                <table class="w-full text-sm mt-4">
                    <thead><tr class="text-xs text-ink-soft"><th class="text-left font-bold pb-2">掲載日時</th><th class="text-right font-bold pb-2 pr-3">価格</th><th class="text-right font-bold pb-2">ポイント</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                <p class="text-xs text-ink-soft mt-4 leading-relaxed">当サイトが毎日7時・18時の更新時に、楽天市場の商品検索で取得した参考価格です。現在の価格・在庫・ポイント倍率は各ストアでご確認ください。</p>
            </section>"""


def render_item_page(pid, info):
    """商品ごとの詳細・価格記録ページ"""
    root = "../"
    page_url = f"{SITE_URL}item/{pid}.html"
    deal = dict(info, slot=info.get("slot") or "main", badge=info.get("badge") or BADGES["main"],
                category=info.get("category") or "ガジェット", catch_copy=info.get("catch_copy") or "",
                deal_reason=info.get("deal_reason") or "", image_url=info.get("image_url") or "")
    name = deal["product_name"]
    points = price_points(info)
    latest = points[-1] if points else None
    if latest:
        deal["price_yen"], deal["point_rate"] = latest[1], latest[2]
    seen = info.get("records", [])
    first_seen = seen[0]["t"][:10].replace("-", "/") if seen else ""
    title = f"{name}の価格推移・セール情報｜{SITE_NAME}"
    description = (f"{name}の楽天参考価格の記録と、AIが選んだおすすめポイント。"
                   + (f"記録中の最安 ¥{min(p for _, p, _ in points):,}・掲載{len(seen)}回。" if points else "")
                   + "Amazon・楽天の販売ページもすぐ確認できます。")
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE_URL},
        {"@type": "ListItem", "position": 2, "name": name, "item": page_url},
    ]}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    return f"""{head_html(title, description, page_url, root, "article", ld_json)}
    <header class="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-orange-100">
        <div class="max-w-3xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
            <a href="{root}index.html" class="flex items-center gap-2.5 min-w-0">
                <img src="{root}img/logo.svg" alt="" class="w-10 h-10 shrink-0">
                <span class="leading-tight min-w-0">
                    <span class="block text-xs font-bold text-orange-600">AI厳選</span>
                    <span class="block font-extrabold text-[17px] text-ink truncate">ガジェット特価速報</span>
                </span>
            </a>
            <a href="{root}index.html" class="btn btn-main shrink-0 text-sm font-bold px-4 py-2.5 rounded-full">今日の特価 →</a>
        </div>
    </header>

    <main class="max-w-3xl mx-auto px-4 pt-6 pb-16 space-y-6">
        <nav class="text-sm text-ink-soft" aria-label="パンくずリスト"><a href="{root}index.html" class="hover:text-orange-600 underline-offset-2 hover:underline">ホーム</a> › <span class="text-ink font-bold">{html.escape(name)}</span></nav>
        <article class="card p-5 md:p-8">
            <div class="flex flex-col md:flex-row gap-5 md:gap-7">
                {thumbnail_html(deal, "w-full h-60 md:w-64 md:h-64", CARD_TONES[0], root)}
                <div class="flex-1 min-w-0">
                    {badges_html(deal)}
                    <h1 class="text-xl md:text-2xl font-extrabold text-ink leading-snug mt-3">{html.escape(name)}</h1>
                    <p class="mt-1.5 text-orange-600 font-bold">{html.escape(deal['catch_copy'])}</p>
                    <p class="mt-2 text-xs text-ink-soft">初掲載 {first_seen}・最終掲載 {html.escape(str(info.get('last_seen', ''))[:10].replace('-', '/'))}</p>
                    {price_html(deal)}
                    {reasons_html(deal, "text-[15px]")}
                    {cta_html(deal, page_url, root, False)}
                </div>
            </div>
        </article>
        {price_history_html(info)}
        <a href="{root}index.html" class="block card card-hover p-5 text-center font-extrabold text-ink">今日のお買い得ランキングを見る →</a>
    </main>
{footer_html(root)}"""


def generate_site(deals):
    """トップページ・日別アーカイブ・sitemap.xml・robots.txt を生成する"""
    os.makedirs("public/archive", exist_ok=True)
    history = update_history(load_history(), deals)
    products = update_products(load_products(), deals)
    events = load_events()

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(render_page(deals, history, TODAY_DATE, "", SITE_URL, events))
    archive_url = f"{SITE_URL}archive/{TODAY_DATE}.html"
    with open(f"public/archive/{TODAY_DATE}.html", "w", encoding="utf-8") as f:
        f.write(render_page(deals, history, TODAY_DATE, "../", archive_url, events))

    # 商品ページは毎回すべて作り直す（記録が消えた商品のページは削除する）
    os.makedirs("public/item", exist_ok=True)
    for name in os.listdir("public/item"):
        if name.endswith(".html") and name[:-5] not in products:
            os.remove(os.path.join("public/item", name))
    for pid, info in products.items():
        with open(f"public/item/{pid}.html", "w", encoding="utf-8") as f:
            f.write(render_item_page(pid, info))

    # 実在するアーカイブだけをサイトマップに載せる
    archive_dates = sorted((n[:-5] for n in os.listdir("public/archive") if n.endswith(".html")), reverse=True)
    urls = [f"  <url><loc>{SITE_URL}</loc><lastmod>{TODAY_DATE}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    for d in archive_dates:
        urls.append(f"  <url><loc>{SITE_URL}archive/{d}.html</loc><lastmod>{d}</lastmod><priority>0.6</priority></url>")
    for pid, info in products.items():
        urls.append(f"  <url><loc>{SITE_URL}item/{pid}.html</loc><lastmod>{info['last_seen'][:10]}</lastmod><priority>0.7</priority></url>")
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
            deals = normalize_deals(func(candidates), candidates)
            if len([d for d in deals if d["slot"] == "main"]) >= 2:
                print(f"{name}で判定しました。")
                return deals
            print(f"{name}の出力が不足していたため次の手段を試します。")
        except Exception as e:
            print(f"{name} APIエラー（{safe_status(e)}）")
    fallback = normalize_deals(sample_deals())
    for d in fallback:
        d["is_sample"] = True  # 見本データはSNSへ投稿しない
    return fallback


def pick_sns_deal(deals):
    """SNSに投稿する1件（目玉枠でおすすめ度が最も高い商品）を選ぶ"""
    main = [d for d in deals if d["slot"] == "main" and not d.get("is_sample")]
    return max(main, key=lambda d: d["score"]) if main else None


def sns_body(deal, limit):
    """【PR】を先頭に付けた紹介文。AIの文が無ければ商品名とキャッチコピーで作る"""
    text = deal.get("sns_text") or f"{deal['product_name']}\n{deal.get('catch_copy', '')}\n#ガジェット #セール"
    text = text.replace("【PR】", "").strip()
    return ("【PR】" + text)[:limit]


def upload_x_media(auth, image_url):
    """楽天の商品画像をXにアップロードし media_id を返す（失敗時は空文字）"""
    img = requests.get(image_url, timeout=20)
    img.raise_for_status()
    files = {"media": ("item.jpg", img.content, img.headers.get("Content-Type", "image/jpeg"))}
    # v2 のアップロードを優先し、使えなければ v1.1 を試す
    for endpoint, extra in (("https://api.x.com/2/media/upload", {"media_category": "tweet_image"}),
                            ("https://upload.twitter.com/1.1/media/upload.json", {})):
        try:
            res = requests.post(endpoint, auth=auth, files=files, data=extra, timeout=30)
            res.raise_for_status()
            body = res.json()
            media_id = (body.get("data") or {}).get("id") or body.get("media_id_string")
            if media_id:
                return str(media_id)
        except Exception as e:
            print(f"X画像アップロード notice（{safe_status(e)}）")
    return ""


def post_to_x(deal):
    """1投目は画像＋紹介文（URLなし）、2投目の返信でサイトURLへ誘導する"""
    from requests_oauthlib import OAuth1
    auth = OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)
    payload = {"text": sns_body(deal, 135)}
    if deal.get("image_url"):
        try:
            media_id = upload_x_media(auth, deal["image_url"])
        except Exception as e:
            print(f"X画像取得 notice（{safe_status(e)}）")
            media_id = ""
        if media_id:
            payload["media"] = {"media_ids": [media_id]}
    res = requests.post("https://api.x.com/2/tweets", auth=auth, json=payload, timeout=30)
    res.raise_for_status()
    tweet_id = res.json()["data"]["id"]
    reply = {
        "text": f"▼詳細・現在の価格チェックはこちら（毎日7時・18時AI自動更新）\n{SITE_URL}",
        "reply": {"in_reply_to_tweet_id": tweet_id},
    }
    res = requests.post("https://api.x.com/2/tweets", auth=auth, json=reply, timeout=30)
    res.raise_for_status()
    print("Xに投稿しました（画像" + ("あり" if "media" in payload else "なし") + "・返信でURL）。")


def post_to_threads(deal):
    """画像付き（無ければテキスト）で1投稿にまとめて公開する"""
    user_id = THREADS_USER_ID
    if not user_id:  # ユーザーID未登録ならトークンから自分のIDを調べる
        res = requests.get("https://graph.threads.net/v1.0/me", params={"fields": "id", "access_token": THREADS_ACCESS_TOKEN}, timeout=15)
        res.raise_for_status()
        user_id = res.json()["id"]
    base = f"https://graph.threads.net/v1.0/{user_id}"
    params = {"text": f"{sns_body(deal, 400)}\n\n▼詳細・現在の価格はこちら\n{SITE_URL}", "access_token": THREADS_ACCESS_TOKEN}
    if deal.get("image_url"):
        params.update(media_type="IMAGE", image_url=deal["image_url"])
    else:
        params["media_type"] = "TEXT"
    res = requests.post(f"{base}/threads", data=params, timeout=30)
    res.raise_for_status()
    creation_id = res.json()["id"]
    time.sleep(5)  # コンテナの生成完了を待つ
    res = requests.post(f"{base}/threads_publish", data={"creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN}, timeout=30)
    res.raise_for_status()
    print("Threadsに投稿しました。")


def post_to_sns(deals):
    """設定済みのSNSにだけ1件投稿する。失敗してもサイト更新には影響させない"""
    if os.getenv("SKIP_SNS") == "true":
        print("手動実行のためSNS投稿をスキップします。")
        return
    try:
        deal = pick_sns_deal(deals)
    except Exception as e:
        print(f"SNS投稿の準備でエラー（{type(e).__name__}）")
        return
    if not deal:
        print("SNS投稿: AIで選んだ商品が無いためスキップします。")
        return
    targets = (
        ("X", all((X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)), post_to_x),
        ("Threads", bool(THREADS_ACCESS_TOKEN), post_to_threads),
    )
    for name, configured, func in targets:
        if not configured:
            print(f"{name}: キー未設定のため投稿をスキップします。")
            continue
        try:
            func(deal)
        except Exception as e:
            print(f"{name} 投稿エラー（{safe_status(e)}）")


if __name__ == "__main__":
    print("1. 候補データを取得中...")
    raw_candidates = fetch_candidates()
    print(f"   取得件数: {len(raw_candidates)}件")

    print("2. AIで買い時判定＆テキスト生成中...")
    selected_deals = select_deals(raw_candidates)
    print(f"   掲載件数: {len(selected_deals)}件（ついで買い枠 {sum(d['slot'] == 'impulse' for d in selected_deals)}件、写真付き {sum(bool(d['image_url']) for d in selected_deals)}件）")

    print("3. Webサイト更新＆通知送信中...")
    generate_site(selected_deals)
    notify_discord(selected_deals)

    print("4. SNS自動投稿中...")
    post_to_sns(selected_deals)
    print("完了しました！")
