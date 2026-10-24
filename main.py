import os
import re
import sys
import time
import json
import html
import hashlib
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import requests

# 環境変数の読み込み（未設定でもサンプル＆RSSで即テスト動作可能）
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-flash-latest"
AMAZON_TAG = os.getenv("AMAZON_TAG", "your-amazon-tag-22")
RAKUTEN_AFFILIATE_ID = os.getenv("RAKUTEN_AFFILIATE_ID", "")
VC_SID = os.getenv("VC_SID", "").strip()
VC_PID = os.getenv("VC_PID", "").strip()
# 【PR】表記とフッターに載せる広告プログラム（バリューコマースはYahoo!ショッピングのボタンを出す時だけ）
AD_PARTNERS = "楽天アフィリエイト" + ("・バリューコマース" if VC_SID and VC_PID else "")
YAHOO_APP_ID = os.getenv("YAHOO_APP_ID", "").strip()
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
OPERATOR_NAME = "Namiki"
OPERATOR_EMAIL = "takumi.tsuta.pr@gmail.com"
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
PRODUCT_RECORDS = 200  # 1商品あたりの価格記録の上限（紹介時＋1日1回の価格チェックで約半年分）
PRODUCT_KEEP_DAYS = 180  # これより長く掲載されていない商品ページは削除する
# 商品ページを検索に載せる条件（満たすまでは noindex・サイトマップ除外）
INDEX_MIN_RECORDS = 3  # 3回以上紹介した商品
INDEX_MIN_DAYS = 7  # または、価格の記録が1週間分（INDEX_MIN_POINTS 回以上）たまった商品
INDEX_MIN_POINTS = 5
TRACK_MAX_CALLS = 110  # 1回の更新で価格チェックに使う楽天APIの回数の上限（1回あたり約1.5秒）
TRACK_MAX_MISSES = 4  # 続けてこの日数見つからなかった商品は、販売終了とみなしてチェックをやめる
DROP_SHOW = 6  # トップの「値下がりを見つけた商品」に出す件数
DROP_PAGE_DAYS = 3  # 値下がり一覧ページ drops.html に載せる期間（日）と件数
DROP_PAGE_SHOW = 30
DROP_PAGE_MIN = 3  # この件数に満たない日は、値下がり一覧ページを検索に載せない
FEED_SHOW = 30  # RSSフィード feed.xml に載せる商品の件数
# IndexNow（Bingなどへ更新ページを通知する仕組み）の確認キー。公開しても問題ない値で、public/<キー>.txt として配信する
INDEXNOW_KEY = "6f3b9d2e8a1c4f7b9e0d5a2c8b7f1e4d"
EVENTS_PATH = "data/events.json"
EVENT_LOOKAHEAD_DAYS = 14
THREADS_STATE_PATH = "data/threads_state.json"  # 1コメ（自己返信）でURLを付けられるかの記録
THREADS_TOPIC = "ガジェット"  # Threadsは1投稿に1トピック。サイトの主題に合わせて固定

BADGES = {"main": "🔥 本日の目玉", "impulse": "🛒 ついで買い定番", "popular": "⭐ 高評価の人気品", "drop": "📉 前回より値下がり",
          "staple": "📊 定番・毎日価格チェック"}

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
    (("バッテリー", "Power Bank", "PowerCore", "ポータブル電源"), "battery"),
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
    (("カメラ", "GoPro", "Insta360", "Osmo", "ドライブレコーダー", "ドラレコ"), "camera"),
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
    "from-sky-50 to-sky-200",
    "from-orange-50 to-amber-200",
    "from-emerald-50 to-teal-100",
]
IMPULSE_TONE = "from-emerald-50 to-emerald-100"
RANK_STYLES = {
    1: "from-amber-300 to-yellow-500 text-amber-950",
    2: "from-slate-200 to-slate-400 text-slate-800",
    3: "from-orange-300 to-amber-600 text-white",
    4: "from-[#6b7396] to-[#2b3150] text-white",
}


def safe_status(e):
    return getattr(getattr(e, "response", None), "status_code", type(e).__name__)


def rakuten_request(params):
    """楽天市場の商品検索APIを1回呼び、商品のリストを返す（失敗したら例外）"""
    params = dict(params, applicationId=RAKUTEN_APP_ID)
    if RAKUTEN_ACCESS_KEY:
        # 新方式: アクセスキー + 許可ドメイン(Origin)で認証する
        params["accessKey"] = RAKUTEN_ACCESS_KEY
        url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
    else:
        url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
    # 楽天に登録済みの許可サイト（独自ドメインに移っても github.io のまま送る）
    headers = {"Origin": RAKUTEN_ORIGIN, "Referer": RAKUTEN_ORIGIN + "/auto-deal-bot/"}
    res = requests.get(url, params=params, headers=headers, timeout=15)
    res.raise_for_status()
    return [item.get("Item", item) for item in res.json().get("Items", [])]


def rakuten_error_detail(e):
    resp = getattr(e, "response", None)
    if resp is None:
        return ""
    try:
        body = resp.json()
        return " " + str(body.get("error", "")) + " " + str(body.get("error_description", body.get("message", "")))[:200]
    except Exception:
        return ""


def fetch_rakuten(keyword, slot_hint, hits, min_price=None, max_price=None, page=1):
    """楽天市場APIから商品候補を取得する（画像URL付き）"""
    params = {
        "keyword": keyword,
        "sort": "-reviewCount",
        "hits": hits,
        "page": page,
        "imageFlag": 1,
    }
    if min_price:
        params["minPrice"] = min_price
    if max_price:
        params["maxPrice"] = max_price
    items = []
    try:
        for info in rakuten_request(params):
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
                "review_count": info.get("reviewCount") or 0,
                "review_average": info.get("reviewAverage") or 0,
                "description": info.get("itemCaption", "")[:200],
                "source_url": info.get("itemUrl", ""),
                "item_code": info.get("itemCode", ""),
                "image_url": image_url,
                "slot_hint": slot_hint,
            })
    except Exception as e:
        print(f"Rakuten API fetch notice ({keyword}): {safe_status(e)}{rakuten_error_detail(e)}")
    return items


# 目玉枠の検索ジャンル（更新ごとに4つずつ順番に使う）
MAIN_QUERIES = [
    ("ワイヤレスイヤホン", 3000, None),
    ("モバイルモニター", 8000, None),
    ("スマートウォッチ", 3000, None),
    ("ロボット掃除機", 10000, None),
    ("ヘッドホン ノイズキャンセリング", 5000, None),
    ("ポータブルSSD", 5000, None),
    ("ミニPC", 20000, None),
    ("ワイヤレスキーボード", 3000, None),
    ("ワイヤレスマウス", 2000, None),
    ("Bluetoothスピーカー", 3000, None),
    ("タブレット", 15000, None),
    ("モバイルプロジェクター", 10000, None),
    ("Wi-Fiルーター", 5000, None),
    ("ゲーミングモニター", 15000, None),
    ("ドライブレコーダー", 5000, None),
    ("ポータブル電源", 15000, None),
]
# ついで買い枠（1,000〜3,000円台の定番品）
IMPULSE_QUERIES = [
    ("モバイルバッテリー", 1000, 4000),
    ("USB-C 充電ケーブル", 500, 2500),
    ("炭酸水 500ml 24本", 1000, 2999),
    ("乾電池 単3 まとめ買い", 800, 2999),
    ("電源タップ", 1000, 2999),
    ("USB充電器 PD", 1000, 3500),
    ("microSDカード", 1000, 3500),
    ("スマホスタンド", 800, 2999),
    ("ミネラルウォーター 2L 9本", 800, 2999),
]
# 定番商品：値下がりの有無に関わらず毎日価格を記録する（「〇〇 最安値」「〇〇 安い時期」で検索されやすい型番のある商品）
# (表示名, 楽天の検索語, 商品名に必ず含む語のグループ（各グループのどれか1つ）, 最低価格, 最高価格)
STAPLE_PRODUCTS = [
    ("ソニー ワイヤレスヘッドホン WH-1000XM5", "WH-1000XM5", (("wh-1000xm5",),), 30000, 70000),
    ("ソニー 完全ワイヤレスイヤホン WF-1000XM5", "WF-1000XM5", (("wf-1000xm5",),), 20000, 50000),
    ("Apple AirPods 4 ワイヤレスイヤホン", "AirPods 4", (("airpods 4",),), 15000, 35000),
    ("Anker Soundcore P40i ワイヤレスイヤホン", "Soundcore P40i", (("p40i",),), 4000, 12000),
    ("Anker Soundcore Liberty 4 NC ワイヤレスイヤホン", "Soundcore Liberty 4 NC", (("liberty 4 nc",),), 7000, 18000),
    ("ロジクール ワイヤレスマウス MX Master 3S", "MX Master 3S", (("mx master 3s",),), 9000, 22000),
    ("ロジクール トラックボール M575S", "ロジクール M575S", (("m575",),), 3000, 10000),
    ("ロジクール ワイヤレスキーボード MX Keys S", "MX Keys S", (("mx keys s",),), 10000, 25000),
    ("サンディスク エクストリーム ポータブルSSD 1TB", "サンディスク エクストリーム ポータブルSSD 1TB",
     (("sandisk", "サンディスク"), ("extreme", "エクストリーム"), ("1tb",), ("ssd",)), 8000, 30000),
    ("Samsung T7 Shield ポータブルSSD 1TB", "T7 Shield 1TB", (("t7 shield",), ("1tb",)), 8000, 30000),
    ("Xiaomi Smart Band 9 スマートバンド", "Xiaomi Smart Band 9", (("smart band 9",),), 3000, 9000),
    ("Fitbit Charge 6 スマートウォッチ", "Fitbit Charge 6", (("fitbit",), ("charge 6",)), 12000, 30000),
    ("Anker Nano Power Bank モバイルバッテリー", "Anker Nano Power Bank", (("anker", "アンカー"), ("nano power bank",)), 2500, 8000),
    ("Anker Nano Charger 充電器 30W", "Anker Nano Charger 30W", (("anker", "アンカー"), ("nano",), ("30w",)), 1500, 5000),
    ("Anker Prime Charger 充電器 100W", "Anker Prime Charger 100W", (("anker prime",), ("100w",)), 6000, 20000),
    ("パナソニック エネループ 単3形 充電池 8本", "エネループ 単3 8本", (("エネループ", "eneloop"), ("単3",), ("8本",)), 2500, 9000),
    ("JBL FLIP 6 Bluetoothスピーカー", "JBL FLIP 6", (("jbl",), ("flip 6", "flip6")), 9000, 22000),
    ("EcoFlow RIVER 3 ポータブル電源", "EcoFlow RIVER 3", (("ecoflow",), ("river 3",)), 15000, 50000),
    ("Amazon Fire TV Stick 4K Max", "Fire TV Stick 4K Max", (("fire tv stick",), ("4k max",)), 6000, 15000),
    ("バッファロー Wi-Fiルーター WSR-3000AX4P", "WSR-3000AX4P", (("wsr-3000ax4p",),), 5000, 15000),
    ("Nintendo Switch Proコントローラー", "Switch Proコントローラー", (("proコントローラー", "pro コントローラー"),), 5000, 12000),
    ("DJI Osmo Pocket 3", "Osmo Pocket 3", (("osmo pocket 3",),), 45000, 110000),
]
STAPLES_PATH = "data/staples.json"  # 定番商品ごとの、見つけた商品ページ（pid）と見つからなかった回数
STAPLE_MAX_SEARCH = 12  # 1回の更新で新しく探す定番商品の上限（楽天APIの回数を抑える）
STAPLE_MAX_MISSES = 3  # この回数見つからなかった定番商品は探すのをやめる
RECENT_DAYS = 3  # この日数以内に掲載した商品は候補から外す


def recent_item_urls():
    cutoff = (NOW - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d %H:%M")
    return {v.get("item_url") for v in load_products().values()
            if v.get("item_url") and v.get("last_seen", "") >= cutoff}


def fetch_candidates():
    """公開RSSフィードおよび楽天APIから最新のセール・特価候補を取得する"""
    candidates = []

    if RAKUTEN_APP_ID:
        # 毎回同じ商品にならないよう、ジャンルを更新ごとに入れ替える
        turn = NOW.toordinal() * 2 + (NOW.hour >= 12)
        main_q = [MAIN_QUERIES[(turn * 4 + i) % len(MAIN_QUERIES)] for i in range(4)]
        impulse_q = [IMPULSE_QUERIES[(turn * 3 + i) % len(IMPULSE_QUERIES)] for i in range(3)]
        recent = recent_item_urls()
        for i, (keyword, min_price, max_price) in enumerate(main_q + impulse_q):
            if i:
                time.sleep(1.2)  # 楽天APIのレート制限(1秒1回)対策
            slot_hint = "main" if i < len(main_q) else "impulse"
            # レビュー数上位の中から、ページもずらして取得する
            page = 1 + (turn // 2 + i) % 3
            items = fetch_rakuten(keyword, slot_hint, 6, min_price, max_price, page)
            # 直近に掲載した商品は除外して入れ替わりを作る
            fresh = [c for c in items if rakuten_item_url(c["source_url"]) not in recent]
            candidates += fresh[:4 if slot_hint == "main" else 3]

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
            "badge": BADGES["main"],
            "catch_copy": "PCもスマホもこれ1台",
            "deal_reason": "・ノートPCもスマホもこれ1台で急速充電可能\n・折りたたみ式プラグで持ち運びに最適\n・ノートPCとスマホの充電器をひとつにまとめられる",
            "sns_text": "【本日の注目ガジェット】Ankerの67W 3ポート充電器が狙い目！PCとスマホの充電器を1つにまとめたい人はこれ一択です。#ガジェット #セール",
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
そのため、以下の候補リストと一般的な市場知識をもとに、合計6件を次の内訳で厳選してください。

- 目玉ガジェット・家電枠（slot: "main"）を必ず4件：値引き率や注目度が高い製品
- ついで買い・即決定番枠（slot: "impulse"）を必ず2件：モバイルバッテリー、充電ケーブル、乾電池、炭酸水、日用品など
  1,000〜3,000円台で「安くて今すぐカートに入れやすい定番品」。候補に無ければ定番品を自分で選んでよい
- image_url が「あり」の候補（楽天の実在商品）を優先し、できるだけ4件以上はそこから選ぶこと。その場合 product_name は候補の商品名を短く整えたものにし、候補の商品名にブランド名や型番があれば必ず残す
- reviews（楽天レビューの平均評価と件数）が多く高評価な候補を重視すること
- deal_reason には価格・ポイント倍率や、レビュー・評価に関する言葉を一切書かないこと（サイトの別欄に表示するため）。「こんな人・こんな場面にうれしい」が伝わる、話し言葉寄りの自然な短文にし、「〜搭載」「〜可能」で終わる硬い言い回しは避けること
- 「最安」「最安値」「底値」「激安」「業界最安」など、価格を断定・誇張する表現は一切使わないこと
- 候補データに含まれない詳細なスペック数値（重量や解像度など）は推測で書かず、利用シーンやお得感を中心に紹介すること

【出力フォーマット（必ず以下のJSONオブジェクトのみを出力してください）】
{{
  "deals": [
    {{
      "product_name": "Amazonや楽天で検索しやすい具体的な商品名・型番（40文字以内）",
      "category": "ガジェット または 日用品・家電",
      "slot": "main または impulse",
      "catch_copy": "商品の一番の魅力をひと言で表すキャッチコピー（16文字以内、価格や割引率の数字は書かない）",
      "deal_reason": "おすすめポイントを箇条書き3行（・から始める、各20文字前後）",
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
        if c.get("review_count"):
            row["reviews"] = f"★{c.get('review_average')}（{int(c['review_count']):,}件）"
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


def tone_down(text):
    """価格を断定・誇張する言い回しを、根拠を問われない表現に置き換える"""
    return re.sub(r"(業界|実質)?最安(値|級|クラス)?|底値|激安", "お買い得", text)


def clean_product_name(name):
    """商品名から「楽天1位」「【送料無料】」などの売り文句を外す"""
    name = re.sub(r"【[^】]*】|［[^］]*］|\[[^\]]*\]", " ", str(name))
    name = re.sub(r"(楽天)?(ランキング)?\s*\d+\s*位(獲得|受賞)?(?=\s|$)|送料無料", " ", name)
    return re.sub(r"\s+", " ", name).strip()


# ブランド名・型番とはみなさない英数字（規格・単位・汎用語）
SPEC_WORD = re.compile(r"(?i)^(bluetooth|usb|type-?c|pd|qc|wi-?fi|gps|ai|led|lcd|oled|ips|va|tn|ssd|hdd|hdmi|anc|enc|fhd|uhd|hd|qhd|wqhd|"
                       r"[248]k|qi|gan|pc|usb-?[ac]|ipx?\d*|micro|microsd|sd|sdxc|sdhc|android|ios|windows|mac|ipad|iphone|switch|ps\d|"
                       r"cpu|gpu|ram|rom|rgb|dc|ac|mfi|pse|jis|nfc|esim|sim|lte|5g|4g|max|pro|mini|plus|new|set)$")
UNIT_WORD = re.compile(r"(?i)^[\d.,]+(gb|tb|mb|hz|khz|mah|wh|w|v|a|ml|l|mm|cm|m|g|kg|インチ|型|本|個|枚|台|in1)?$|^(bluetooth|usb|wi-?fi)[\d.]+$|^(pd|qc)[\d.]+w?$")
# カタカナ表記の主なメーカー名
JP_BRANDS = ("エレコム", "バッファロー", "サンワサプライ", "アイリスオーヤマ", "パナソニック", "ソニー", "シャープ", "サントリー", "キリン",
             "アサヒ", "伊藤園", "コカ・コーラ", "ウィルキンソン", "富士通", "東芝", "日立", "象印", "タイガー", "ドウシシャ", "山善", "アンカー", "シリコンパワー", "オシャモバ")


def model_words(name):
    """商品名に含まれるブランド名・型番らしき英数字（「Anker」「P40i」「WAVE」など）"""
    name = re.sub(r"\d+-in-\d+", " ", str(name))
    words = [b for b in JP_BRANDS if b in name]
    for w in re.findall(r"[A-Za-z][A-Za-z0-9+\-]*[A-Za-z0-9+]|[A-Za-z]{2,}|\d+[A-Za-z][A-Za-z0-9\-]*", name):
        w = w.strip("-+")
        if len(w) >= 2 and not SPEC_WORD.match(w) and not UNIT_WORD.match(w):
            words.append(w)
    return words


def display_name(info):
    """ページに出す商品名。短い商品名にブランド・型番が無ければ、楽天の正式な商品名から2語まで補う"""
    name = clean_product_name(info.get("product_name", "")) or str(info.get("product_name", ""))
    if model_words(name) or not info.get("item_name"):
        return name
    extra = [w for w in model_words(clean_product_name(info["item_name"])[:60]) if w.lower() not in name.lower()][:2]
    return f"{' '.join(extra)} {name}".strip() if extra else name


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
        # レビュー数値などは「AIのチェックポイント」欄に出すので、紹介文からは外す
        kept = [r for r in reasons if not re.search(r"レビュー|評価|★|件数|最安|底値|激安", r)]
        if kept and kept != reasons:
            reasons = kept
            d["deal_reason"] = chr(10).join("・" + r for r in reasons)
        catch_copy = tone_down(str(d.get("catch_copy") or (reasons[0] if reasons else "")))[:24]
        price = src
        cleaned.append({
            "product_name": (clean_product_name(d["product_name"]) or str(d["product_name"]))[:60],
            "category": str(d.get("category") or ("日用品・家電" if slot == "impulse" else "ガジェット")),
            "slot": slot,
            "badge": BADGES["impulse"] if slot == "impulse" else (
                BADGES["popular"] if float(src.get("review_average") or 0) >= 4.5 and int(src.get("review_count") or 0) >= 300
                else BADGES["main"]),
            "catch_copy": catch_copy,
            "deal_reason": str(d.get("deal_reason", "")),
            "sns_text": tone_down(str(d.get("sns_text", ""))),
            "score": max(0, min(100, score)),
            "image_url": image_url if image_url.startswith("https://") else "",
            "price_yen": price.get("price_yen"),
            "point_rate": price.get("point_rate"),
            "item_url": rakuten_item_url(src.get("source_url")),
            "item_code": src.get("item_code") or "",
            "item_name": str(src.get("title") or "")[:200],
            "review_count": src.get("review_count") or 0,
            "review_average": src.get("review_average") or 0,
            "candidate_no": src.get("no"),
        })

    # 目玉枠はおすすめ度の高い順に並べてランキングにする
    main = sorted((d for d in cleaned if d["slot"] == "main"), key=lambda d: d["score"], reverse=True)[:4]
    # AIが目玉枠を4件返さなかったときは、レビューの多い楽天候補で補う（紹介文は付けない）
    used = {d.get("candidate_no") for d in cleaned}
    spare = sorted((c for c in by_no.values() if c.get("slot_hint") == "main" and c.get("no") not in used),
                   key=lambda c: int(c.get("review_count") or 0), reverse=True)
    for c in spare[:max(0, 4 - len(main))]:
        name = re.sub(r"【[^】]*】|\[[^\]]*\]|＼[^／]*／|★[^★]*★", " ", str(c.get("title", ""))).split()
        main.append({
            "product_name": " ".join(name)[:40] or str(c.get("title", ""))[:40],
            "category": "ガジェット", "slot": "main",
            "badge": BADGES["popular"] if float(c.get("review_average") or 0) >= 4.5 and int(c.get("review_count") or 0) >= 300 else BADGES["main"],
            "catch_copy": "楽天でレビューの多い売れ筋", "deal_reason": "", "sns_text": "",
            "score": max(0, (main[-1]["score"] if main else 85) - 1),
            "image_url": c["image_url"], "price_yen": c.get("price_yen"), "point_rate": c.get("point_rate"),
            "item_url": rakuten_item_url(c.get("source_url")),
            "item_code": c.get("item_code") or "", "item_name": str(c.get("title") or "")[:200],
            "review_count": c.get("review_count") or 0, "review_average": c.get("review_average") or 0,
            "candidate_no": c.get("no"),
        })
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


def with_vc_affiliate(url):
    """バリューコマース経由のYahoo!ショッピング用アフィリエイトURL"""
    return f"https://ck.jp.ap.valuecommerce.com/servlet/referral?sid={VC_SID}&pid={VC_PID}&vc_url={urllib.parse.quote(url, safe='')}"


def yahoo_link(deal):
    """Yahoo!ショッピングの商品ページ（無ければ検索ページ）。VC未設定なら空文字"""
    if not (VC_SID and VC_PID):
        return ""
    target = deal.get("yahoo_item_url") or f"https://shopping.yahoo.co.jp/search?p={urllib.parse.quote(deal['product_name'])}"
    return with_vc_affiliate(target)


def attach_yahoo_items(deals):
    """商品名でYahoo!ショッピングを検索し、楽天の参考価格に近い商品ページを紐付ける"""
    if not (YAHOO_APP_ID and VC_SID and VC_PID):
        return
    found = 0
    for deal in deals:
        if deal.get("is_sample"):
            continue
        params = {"appid": YAHOO_APP_ID, "query": deal["product_name"][:60], "results": 10, "in_stock": "true"}
        price = deal.get("price_yen")
        if isinstance(price, (int, float)) and price > 0:
            params.update(price_from=int(price * 0.6), price_to=int(price * 1.4))
        try:
            res = requests.get("https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch", params=params, timeout=15)
            if res.status_code != 200:
                print(f"Yahoo検索 notice（{res.status_code}）: {res.text[:200].replace(YAHOO_APP_ID, '***')}")
                hits = []
                time.sleep(1)
                continue
            res.raise_for_status()
            hits = res.json().get("hits") or []
        except Exception as e:
            print(f"Yahoo検索 notice（{safe_status(e)}）")
            hits = []
        url = str((hits[0] if hits else {}).get("url") or "")
        if url.startswith("https://store.shopping.yahoo.co.jp/"):
            deal["yahoo_item_url"] = url
            found += 1
        time.sleep(1)
    print(f"   Yahoo!ショッピング商品ページ紐付け: {found}件")


def build_tweet_url(deal, page_url):
    """X投稿画面を開くURL。リンクはアフィリエイトではなくサイトの商品ページ（無ければトップ）にする"""
    points = reason_lines(deal.get("deal_reason", ""))[:2] or [deal.get("catch_copy", "")]
    lines = [f"【本日の注目特価】{deal['product_name']}"]
    if sns_price_line(deal):
        lines.append(sns_price_line(deal))
    lines += [f"・{p}" for p in points if p]
    lines += ["価格の推移・現在の価格はこちら👇", deal_page_url(deal), "#ガジェット #セール"]
    return "https://twitter.com/intent/tweet?" + urllib.parse.urlencode({"text": "\n".join(lines)})


def build_line_url(deal, page_url):
    """LINEで友だちやグループに送る画面を開くURL（商品ページがあればそのページを送る）"""
    url = deal_page_url(deal) if deal.get("item_page") else page_url
    return "https://social-plugins.line.me/lineit/share?" + urllib.parse.urlencode({"url": url})


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


# 商品名や紹介文から拾うスペック表記（ガジェットらしさを数字で見せる）
SPEC_PATTERNS = [
    (r"bluetooth\s?\d\.\d", lambda m: "Bluetooth " + re.sub(r"(?i)bluetooth\s?", "", m)),
    (r"\d+(?:\.\d+)?\s?インチ", None),
    (r"(?<![\d.])\d{1,3}(?:,?\d{3})*\s?mah", lambda m: m.replace(" ", "").replace("mah", "mAh").replace("MAH", "mAh")),
    (r"(?<![\d.])\d+(?:\.\d+)?\s?(?:TB|GB)(?![a-z])", None),
    (r"(?<![\d.a-z])\d+(?:\.\d+)?\s?W(?![a-z])", None),
    (r"(?<![\d.a-z])\d+(?:\.\d+)?\s?(?:kg|g)(?![a-z])", None),
    (r"(?<![\d.a-z])(?:2\.5K|2K|4K|8K)(?![a-z])|フルHD|WQHD|AMOLED|有機EL", None),
    (r"\d+\s?Hz", None),
    (r"USB[\s-]?C|Type[\s-]?C", lambda m: "USB-C"),
    (r"Wi-?Fi\s?\d[E]?", lambda m: "Wi-Fi " + re.sub(r"(?i)wi-?fi\s?", "", m)),
    (r"IPX?\d{1,2}", None),
]


def spec_chips(deal, limit=4):
    """商品名・キャッチ・理由から「Bluetooth 5.4」「606g」のようなスペックを最大4つ拾う"""
    text = unicodedata.normalize("NFKC", " ".join(str(deal.get(k) or "") for k in ("product_name", "catch_copy", "deal_reason")))
    found, seen = [], set()
    for pattern, fmt in SPEC_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            val = fmt(m.group(0)) if fmt else m.group(0).replace(" ", "")
            key = re.sub(r"[\s,]", "", val.lower())
            if key not in seen:
                seen.add(key)
                found.append(val)
    return found[:limit]


def specs_html(deal):
    chips = "".join(f'<span class="spec">{html.escape(v)}</span>' for v in spec_chips(deal))
    return f'<div class="flex flex-wrap gap-1.5 mt-2.5">{chips}</div>' if chips else ""


def hero_visual_html(deals, root):
    """トップの絵の代わりに、今日の上位商品の写真を並べる。写真が足りない日は従来のイラスト"""
    shots = [(i, d) for i, d in enumerate(deals, 1) if d["slot"] == "main" and d.get("image_url")][:3]
    if len(shots) < 3:
        return (f'<img src="{root}img/hero.svg" alt="" class="w-full max-w-[28rem] ml-auto">',
                f'<img src="{root}img/hero.svg" alt="" class="md:hidden w-full max-w-[17rem] mx-auto mt-4 -mb-1">')

    def tile(idx, deal, cls, img_pad):
        art = f"{root}img/items/{item_art(deal)}.svg"
        price = ""
        try:
            price = f'<span class="num">¥{int(deal["price_yen"]):,}</span>' if deal.get("price_yen") else ""
        except (TypeError, ValueError):
            pass
        return (f'<a href="#deal-{idx}" class="hero-shot {cls}">'
                f'<img src="{html.escape(deal["image_url"])}" alt="{html.escape(deal["product_name"])}" class="w-full h-full object-contain {img_pad}" '
                f'onerror="this.onerror=null;this.src=\'{art}\'">'
                f'<span class="hero-tag"><b>{"No.1" if idx == 1 else f"{idx}位"}</b>{price}</span></a>')

    (i1, d1), (i2, d2), (i3, d3) = shots
    desktop = (f'<div class="relative w-full max-w-[28rem] aspect-square ml-auto">'
               + tile(i1, d1, "absolute left-0 top-[12%] w-[62%] aspect-square -rotate-2", "p-5")
               + tile(i2, d2, "absolute right-0 top-0 w-[42%] aspect-square rotate-3", "p-3")
               + tile(i3, d3, "absolute right-[4%] bottom-[6%] w-[42%] aspect-square -rotate-1", "p-3")
               + '</div>')
    mobile = ('<div class="md:hidden grid grid-cols-3 gap-2.5 mt-5">'
              + "".join(tile(i, d, "relative aspect-square", "p-2") for i, d in shots) + '</div>')
    return desktop, mobile


def badges_html(deal):
    if deal.get("badge") not in BADGES.values():  # 過去データに残る根拠のないバッジは出さない
        deal = dict(deal, badge=BADGES["impulse"] if deal.get("slot") == "impulse" else BADGES["main"])
    badge_cls = "bg-emerald-50 text-emerald-700 ring-emerald-100" if deal["slot"] == "impulse" else "bg-orange-50 text-orange-700 ring-orange-100"
    return (f'<div class="flex items-center gap-1.5 flex-wrap">'
            f'<span class="{badge_cls} ring-1 text-xs font-bold px-2.5 py-1 rounded-full">{html.escape(deal["badge"])}</span>'
            f'<span class="bg-slate-50 text-ink-soft ring-1 ring-slate-200 text-xs font-bold px-2.5 py-1 rounded-full">{html.escape(deal["category"])}</span>'
            f'</div>')


def score_html(score):
    return f"""
                <div class="flex items-center gap-2.5 mt-4" title="楽天レビュー・価格の記録・商品説明をもとにAIが付けた目安です">
                    <span class="text-xs font-bold text-ink-soft whitespace-nowrap">AI注目度</span>
                    <div class="flex-1 h-2.5 bg-orange-100 rounded-full overflow-hidden">
                        <div class="h-full rounded-full bg-gradient-to-r from-amber-300 to-orange-500" style="width:{score}%"></div>
                    </div>
                    <span class="num text-lg font-extrabold text-orange-600 leading-none">{score}</span>
                </div>"""


def grounds_html(deal, show_score=True, open_=False):
    """AIが判断に使ったデータを、確認できる事実だけで短く示す"""
    rows = []
    try:
        count, avg = int(deal.get("review_count") or 0), float(deal.get("review_average") or 0)
    except (TypeError, ValueError):
        count, avg = 0, 0
    if count:
        rows.append(("評価", f'<b class="text-ink">★{avg:.2f}</b>（{count:,}件・楽天）'))
    if deal.get("item_url"):
        rows.append(("人気", "楽天でレビューの多い売れ筋"))
    else:
        rows.append(("定番", "どこでも手に入る定番品"))
    seen = int(deal.get("seen_count") or 0)
    if deal.get("record_low"):
        rows.append(("価格", '<b class="text-emerald-700">当サイトの記録で最安</b>'))
    elif deal.get("price_drop"):
        rows.append(("価格", f'<b class="text-emerald-700">前回の記録より ¥{deal["price_drop"]:,} ダウン</b>'))
    elif seen > 1:
        rows.append(("価格", f"{seen}回目の登場" + ("・前回の記録から変わらず" if deal.get("price_same") else "")))
    elif deal.get("price_yen"):
        rows.append(("価格", "今回が初登場・価格の記録をスタート"))
    if point_rate_value(deal) >= 2:
        rows.append(("還元", f'<b class="text-amber-700">楽天ポイント{point_rate_value(deal):g}倍</b>'))
    peek = f'<span class="ml-2 font-normal text-ink-soft whitespace-nowrap">★{avg:.1f}・{count:,}件</span>' if count and not open_ else ""
    items = "".join(f'<dt class="text-[11px] font-bold text-ink-soft bg-white ring-1 ring-slate-200 rounded-full px-2 py-0.5 text-center self-start">{label}</dt>'
                    f'<dd class="text-ink-soft">{text}</dd>' for label, text in rows)
    note = "※AI注目度は、上のデータと商品説明からAIが出した目安です。" if show_score else "※紹介文は、上のデータと商品説明をもとにAIが書いています。"
    return f"""
                <details class="group mt-4 rounded-2xl bg-slate-50 ring-1 ring-slate-200 px-4 py-3 text-[13px]"{" open" if open_ else ""}>
                    <summary class="flex items-center justify-between gap-2 cursor-pointer list-none font-bold text-ink select-none">
                        <span>AIのチェックポイント{peek}</span>
                        <span class="text-orange-600 text-xs group-open:rotate-180 transition" aria-hidden="true">▼</span>
                    </summary>
                    <dl class="grid grid-cols-[auto_1fr] gap-x-2.5 gap-y-2 mt-3 leading-relaxed">{items}</dl>
                    <p class="mt-2.5 text-[11px] text-ink-soft leading-relaxed">{note}</p>
                </details>"""


def point_rate_value(deal):
    try:
        return float(deal.get("point_rate") or 1)
    except (TypeError, ValueError):
        return 1.0


def price_trend(prev_prices, price):
    """前回掲載時からの値下がり額と、当サイトの記録で最も安いかどうか"""
    if not prev_prices or not price:
        return 0, False
    return max(prev_prices[-1] - price, 0), price <= min(prev_prices) and price < max(prev_prices)


def price_html(deal):
    if not deal.get("price_yen"):
        return ""
    try:
        price = f"¥{int(deal['price_yen']):,}"
    except (TypeError, ValueError):
        return ""
    chips = ""
    rate = point_rate_value(deal)
    if rate >= 2:  # 通常の1倍は表示しない
        chips += f'<span class="text-xs font-bold text-amber-800 bg-amber-50 ring-1 ring-amber-200 px-2.5 py-1 rounded-full">ポイント{rate:g}倍</span>'
    if deal.get("price_drop"):
        chips += (f'<span class="text-xs font-bold text-emerald-700 bg-emerald-50 ring-1 ring-emerald-200 px-2.5 py-1 rounded-full" '
                  f'title="当サイトが前回記録した楽天参考価格との差です">前回の記録より ¥{deal["price_drop"]:,} 値下がり</span>')
    if deal.get("record_low"):
        chips += ('<span class="text-xs font-bold text-white bg-emerald-600 px-2.5 py-1 rounded-full" '
                  'title="当サイトが記録した楽天参考価格の中で最も安い価格です">当サイト記録で最安</span>')
    return f"""
                <div class="flex items-center gap-x-2 gap-y-2 mt-4 flex-wrap">
                    <span class="text-xs font-bold text-ink-soft">楽天参考価格</span>
                    <span class="num text-[1.7rem] font-extrabold text-ink leading-none">{price}</span>
                    {chips}
                </div>"""


def reasons_html(deal, text_cls="text-sm"):
    items = "".join(
        f'<li class="flex gap-2.5"><span class="w-5 h-5 mt-0.5 shrink-0 rounded-full bg-emerald-100 text-emerald-600 text-[11px] font-extrabold flex items-center justify-center">✓</span>'
        f'<span>{html.escape(line)}</span></li>'
        for line in reason_lines(deal["deal_reason"])
    )
    return f'<ul class="space-y-2 {text_cls} text-ink leading-relaxed mt-4">{items}</ul>'


# GoatCounter でストアへのリンクのクリック数を数える（Cookieなし）。管理画面には click-ストア-場所 の名前で出る
CLICK_STORES = {"amazon": "Amazon", "rakuten": "楽天", "yahoo": "Yahoo!", "event": "セール会場"}
CLICK_PLACES = {"top": "トップ", "archive": "アーカイブ", "item": "商品ページ", "category": "カテゴリ", "drop": "値下がり欄",
                "header": "ヘッダー", "hero": "トップ上部", "bar": "画面下ボタン", "salecard": "セール情報", "eventbar": "セール告知バー"}
SHOP_CLICK_KEYS = {"amz": "amazon", "rkt": "rakuten", "yahoo": "yahoo"}


def click_attrs(store, place):
    return (f'data-goatcounter-click="click-{store}-{place}" '
            f'data-goatcounter-title="{CLICK_STORES[store]}（{CLICK_PLACES[place]}）"')


def cta_html(deal, page_url, root="", detail_link=True, place=None):
    place = place or ("top" if root == "" else "archive")
    amz_url, rkt_url = build_affiliate_urls(deal["product_name"], deal.get("item_url", ""))
    # ストアのボタンは同じ大きさで横に並べ、ブランド色は文字と縁取りだけに使う
    shops = [("amz", amz_url, "Amazon", "Amazonで見る"), ("rkt", rkt_url, "楽天", "楽天で見る")]
    yahoo_url = yahoo_link(deal)
    if yahoo_url:
        shops.append(("yahoo", yahoo_url, "Yahoo!", "Yahoo!ショッピングで見る"))
    buttons = "".join(
        f'\n                    <a href="{html.escape(url)}" target="_blank" rel="nofollow noopener sponsored" class="shop shop-{key}" title="{label}" '
        f'{click_attrs(SHOP_CLICK_KEYS[key], place)}><b>{name}</b><small>で見る <span aria-hidden="true">›</span></small></a>'
        for key, url, name, label in shops)
    detail = "<span></span>"
    if detail_link and deal.get("item_page"):
        detail = (f'<a href="{root}{deal["item_page"]}" class="inline-flex items-center gap-1.5 text-sm font-bold text-orange-600 '
                  f'hover:text-orange-700 hover:underline underline-offset-2">'
                  f'<img src="{root}img/icons/chart.svg" alt="" class="w-5 h-5">価格の記録・詳細 <span aria-hidden="true">›</span></a>')
    return f"""
                <div class="grid grid-cols-{len(shops)} gap-2 mt-5">{buttons}
                </div>
                <p class="text-[11px] text-ink-soft text-center mt-2">※価格・ポイントはリンク先でご確認ください</p>
                <div class="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-dashed border-orange-100">
                    {detail}
                    <span class="shrink-0 flex items-center gap-1.5">
                    <a href="{html.escape(build_line_url(deal, page_url))}" target="_blank" rel="noopener" data-goatcounter-click="share-line"
                       class="bg-[#06C755] hover:bg-[#05b34c] text-white font-bold py-1.5 px-3 rounded-full text-xs transition">
                       LINEで送る
                    </a>
                    <a href="{html.escape(build_tweet_url(deal, page_url))}" target="_blank" rel="noopener" data-goatcounter-click="share-x"
                       class="bg-white hover:bg-slate-50 ring-1 ring-slate-200 text-ink font-bold py-1.5 px-3 rounded-full text-xs transition">
                       𝕏 ポスト
                    </a>
                    </span>
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
                        {specs_html(deal)}
                        {score_html(deal['score'])}
                        {price_html(deal)}
                        {reasons_html(deal, "text-[15px] md:text-base")}
                        {grounds_html(deal, True, True)}
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
                        {specs_html(deal)}
                    </div>
                </div>
                {score_html(deal['score'])}
                {price_html(deal)}
                <div class="flex-1">{reasons_html(deal)}{grounds_html(deal)}</div>
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
                        {specs_html(deal)}
                    </div>
                </div>
                {price_html(deal)}
                <div class="flex-1">{reasons_html(deal)}{grounds_html(deal, False)}</div>
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
        <a href="{html.escape(ev['url'])}" target="_blank" rel="nofollow noopener sponsored" data-event-bar {event_attrs(ev)} {click_attrs("event", "eventbar")}{hidden}
           class="block max-w-5xl mx-auto px-4 py-2.5 text-center text-sm font-bold leading-relaxed hover:underline">
            <span class="ev-state text-xs font-extrabold px-2.5 py-0.5 rounded-full mr-1.5">{'開催中' if ev['start'] <= NOW else 'まもなく開始'}</span>
            {html.escape(ev['name'])}
            <span class="font-extrabold text-amber-200 ml-1 whitespace-nowrap" data-event-countdown>{html.escape(event_period(ev))}</span>
            <span class="ml-1 underline whitespace-nowrap">会場を見る →</span>
        </a>"""
    return f'<div id="event-bar" class="bg-ink text-white">{items}\n    </div>'


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
                           "セール会場を見る", "text-orange-600", root, f'{event_attrs(ev)} {click_attrs("event", "salecard")}')
    cards += sale_card(
        RAKUTEN_TOP_URL, "coin", "bg-amber-50",
        '<span class="text-xs font-extrabold px-2.5 py-0.5 rounded-full bg-red-600 text-white whitespace-nowrap">毎月6回</span>',
        "楽天市場", "5と0のつく日",
        f"""
                    <p class="text-[15px] font-extrabold text-rose-600 mt-2" id="rakuten-day">{next_rakuten_point_day()}</p>
                    <p class="text-sm text-ink-soft mt-1 leading-relaxed">エントリー＆楽天カード決済でポイントアップ。高額ガジェットはこの日にまとめるのが定番です。</p>""",
        "楽天市場を見る", "text-red-600", root, f'data-rakuten-day {click_attrs("rakuten", "salecard")}')
    cards += sale_card(
        AMAZON_SALE_URL, "clock", "bg-sky-50",
        '<span class="text-xs font-extrabold px-2.5 py-0.5 rounded-full bg-ink text-amber-200 whitespace-nowrap">毎日開催</span>',
        "Amazon", "タイムセール",
        """
                    <p class="text-[15px] font-extrabold text-orange-700 mt-2">人気商品が日替わりで登場</p>
                    <p class="text-sm text-ink-soft mt-1 leading-relaxed">数量限定の特選タイムセールは売り切れ次第終了。気になる商品は早めのチェックがおすすめです。</p>""",
        "タイムセール会場を見る", "text-orange-600", root, click_attrs("amazon", "salecard"))
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
    ("chart", "bg-amber-50", "注目度をスコア化", "楽天のレビュー評価・件数や価格の記録をもとにAIが判定。紹介した商品はその後も毎日価格をチェックし、値下がりした商品はトップにまとめます。"),
    ("cart", "bg-emerald-50", "各ストアをワンタップ比較", "ボタンからAmazon・楽天などの販売ページへ。価格やポイント還元はストアごとに違うので、見比べてから選べます。"),
]

FAQ = [
    ("掲載商品はどうやって選んでいますか？",
     "家電・ガジェット系ニュースや楽天市場の人気商品などの公開情報をもとに、AIが楽天のレビュー評価・件数、当サイトの価格記録、ポイント倍率などを見て毎日2回自動で選んでいます。各商品の「AIのチェックポイント」で、判断に使ったデータを確認できます。"),
    ("「実質価格」とは何ですか？",
     "販売価格からポイント還元やクーポンを差し引いた、実際の負担額のことです。還元率は会員ランクやキャンペーンのエントリー状況で変わるため、最終的な価格は各ストアでご確認ください。"),
    ("「値下がりを見つけた商品」とは何ですか？",
     "当サイトで紹介した商品は、紹介した後も1日1回、楽天市場の商品検索で価格をチェックしています。前回の記録より値下がりしていた商品を、トップページにまとめて表示しています。楽天市場での参考価格のため、Amazonなど他のストアの価格とは異なる場合があります。"),
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


# 見た目は Tailwind CSS。ワークフローで public/**/*.html から public/css/site.css をビルドする（設定は tailwind.config.js）
CSS_VERSION = NOW.strftime("%Y%m%d%H%M")

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
                radial-gradient(55% 65% at 92% 18%, rgba(255, 200, 150, .7), transparent 70%),
                radial-gradient(45% 55% at 0% 95%, rgba(255, 226, 160, .75), transparent 70%),
                radial-gradient(40% 45% at 8% 0%, rgba(222, 238, 255, .8), transparent 70%),
                #fff6ec;
        }
        .pattern {
            background-image: radial-gradient(rgba(43, 49, 80, .11) 1px, transparent 1.3px); background-size: 22px 22px;
            -webkit-mask-image: linear-gradient(to bottom, #000, transparent 85%); mask-image: linear-gradient(to bottom, #000, transparent 85%);
        }
        /* 価格・点数・スペックの数字は、すっきりした欧文書体で揃える */
        .num { font-family: 'Inter', 'M PLUS Rounded 1c', sans-serif; font-feature-settings: "tnum"; letter-spacing: -.01em; }
        .spec {
            font-family: 'Inter', 'M PLUS Rounded 1c', sans-serif; font-size: 11px; font-weight: 700; line-height: 1;
            color: #3b4366; background: #f1f3f8; border: 1px solid #dde1ec; border-radius: .4rem; padding: .3rem .45rem;
        }
        .hero-shot {
            display: block; background: #fff; border-radius: 1.5rem; overflow: hidden;
            box-shadow: 0 0 0 1px #ffe3cc, 0 18px 40px -16px rgba(43, 49, 80, .35); transition: transform .2s;
        }
        .hero-shot:hover { transform: translateY(-4px) rotate(0deg); }
        .hero-tag {
            position: absolute; left: .5rem; bottom: .5rem; display: inline-flex; align-items: center; gap: .35rem;
            background: rgba(43, 49, 80, .88); color: #fff; font-size: 11px; font-weight: 700; line-height: 1;
            padding: .35rem .55rem; border-radius: 999px;
        }
        .hero-tag b { color: #ffc46b; font-weight: 800; }
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
        .btn-main { background: linear-gradient(#ffa152, #ff8a3d); color: #2b3150; box-shadow: 0 4px 0 #e0661b; }
        /* ストアボタン: 3つとも同じ大きさ・同じ形で、ブランド色は店名の文字と縁取りだけ */
        .shop {
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
            min-height: 3.5rem; padding: .5rem .25rem; border-radius: 1rem; text-align: center; line-height: 1.2;
            background: var(--tint); color: #555d80; border: 1.5px solid var(--ring); border-bottom-width: 4px;
            transition: transform .1s, filter .15s;
        }
        .shop:hover { filter: brightness(.97); }
        .shop:active { transform: translateY(2px); border-bottom-width: 2px; }
        .shop b { color: var(--c); font-size: 15px; font-weight: 800; }
        .shop small { font-size: 11px; font-weight: 700; }
        .shop-amz { --c: #c45500; --ring: #ffd08a; --tint: #fff7e8; }
        .shop-rkt { --c: #bf0000; --ring: #f6bcbc; --tint: #fff3f3; }
        .shop-yahoo { --c: #e6002e; --ring: #ffbfcc; --tint: #fff2f5; }
        .shop-row { flex-direction: row; min-height: 0; padding: .7rem .5rem; font-size: 14px; font-weight: 800; color: var(--c); }
        /* 赤系は「開催中」「残り時間」など急ぎの情報だけに使う */
        .ev-state { background: #ffe066; color: #2b3150; }
        [data-state="live"] .ev-state { background: #e11d48; color: #fff; }
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
                        <div class="num text-ink font-extrabold leading-tight mt-1.5">{value}</div>
                    </div>"""


def render_page(deals, history, page_date, root, page_url, events=(), groups=None, drops=()):
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

    hero_desktop, hero_mobile = hero_visual_html(deals, root)
    picks = ""
    for i, deal in enumerate(deals, 1):
        picks += (f'<a href="#deal-{i}" class="shrink-0 max-w-[16rem] flex items-center gap-2 bg-white hover:bg-orange-50 ring-1 ring-orange-100 shadow-sm '
                  f'rounded-full pl-1 pr-4 py-1 text-sm font-bold text-ink transition">'
                  + (f'<img src="{html.escape(deal["image_url"])}" alt="" loading="lazy" class="w-9 h-9 shrink-0 rounded-full bg-white ring-1 ring-slate-100 object-contain p-0.5" '
                     f'onerror="this.onerror=null;this.src=\'{root}img/items/{item_art(deal)}.svg\'">'
                     if deal.get("image_url") else f'<img src="{root}img/items/{item_art(deal)}.svg" alt="" class="w-9 h-9 shrink-0 rounded-full bg-orange-50">')
                  + f'<span class="truncate">{html.escape(deal["product_name"])}</span></a>')

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
            <a href="{root}index.html" class="btn btn-main shrink-0 font-bold px-5 py-3 rounded-full text-center">最新のお買い得情報を見る →</a>
        </div>"""
    else:
        title = f"【{md_date(page_dt)}更新】今日のお買い得ガジェット{len(deals)}選・セール情報｜{SITE_NAME}"
        h1 = 'AIが選ぶ、今日の<br><span class="marker">お買い得ガジェット</span>'
        lead = "楽天市場の売れ筋やガジェット系ニュースから、AIがお買い得な商品を毎日2回ピックアップ。紹介した商品はその後も毎日価格をチェックし、値下がりや最安記録をひと目で確認できます。"
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
        <section id="impulse" class="scroll-mt-24 bg-[#f0f9f3] ring-1 ring-emerald-100 rounded-[2rem] px-3 py-6 md:p-8 -mx-2 md:mx-0">
            {section_head("cart", "ついで買いで、もう1品お得に", "送料無料ラインやポイントアップ条件にあと少し届かない時に。いつか必ず使う手頃な定番品です。", root)}
            <div class="grid gap-5 md:grid-cols-2">{impulse_cards}
            </div>
        </section>"""

    drop_section = ""
    if drops:
        drop_cards = "".join(drop_card(pid, info, root) for pid, info in drops)
        drop_section = f"""
        <section id="price-drop" class="scroll-mt-24">
            {section_head("chart", "値下がりを見つけた商品", "これまでに紹介した商品の楽天参考価格を毎日チェックし、前回の記録から下がったものを並べています。", root)}
            <div class="grid gap-5 md:grid-cols-2">{drop_cards}
            </div>
            <a href="{root}drops.html" class="block card card-hover p-4 mt-5 text-center font-extrabold text-ink">値下がりした商品をすべて見る →</a>
        </section>"""

    nav_cls = "px-3 py-2 rounded-full hover:bg-orange-50 hover:text-orange-600 transition"
    return f"""{head_html(title, description, page_url, root, 'article' if is_archive else 'website', json_ld(deals, page_url, page_label), is_archive)}
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
                <a href="#impulse" class="{nav_cls}">ついで買い</a>{f'<a href="#price-drop" class="{nav_cls}">値下がり</a>' if drops else ""}
                <a href="#sale-info" class="{nav_cls}">セール情報</a>
                <a href="#category" class="{nav_cls}">カテゴリ</a>
                <a href="#archive" class="{nav_cls}">アーカイブ</a>
            </nav>
            <a href="{html.escape(AMAZON_SALE_URL)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("amazon", "header")}
               class="btn btn-main shrink-0 text-sm font-bold px-4 py-2.5 rounded-full">セール会場 ↗</a>
        </div>
    </header>

    <section class="hero-bg relative overflow-hidden">
        <div class="pattern absolute inset-0" aria-hidden="true"></div>
        <div class="relative max-w-5xl mx-auto px-4 pt-7 pb-16 md:pt-12 md:pb-24 md:grid md:grid-cols-[1.15fr_.85fr] md:items-center md:gap-6">
            <div class="min-w-0">
                {crumbs}
                <div class="inline-flex items-center gap-2 bg-white ring-1 ring-orange-100 shadow-sm rounded-full px-3.5 py-1.5 text-sm font-bold text-ink">
                    <span class="relative flex h-2.5 w-2.5"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span></span>
                    毎日 朝・夕方にAIが自動更新
                </div>
                <h1 class="mt-5 text-[1.85rem] md:text-5xl font-extrabold text-ink leading-[1.35] md:leading-[1.3]">{h1}</h1>
                <p class="mt-4 text-ink-soft text-[15px] md:text-lg leading-relaxed">{lead}</p>
                {hero_mobile}
                <div class="grid grid-cols-3 gap-2 md:gap-3 mt-5 md:mt-7">{stats}
                </div>
                <div class="flex flex-col sm:flex-row gap-3 mt-6">
                    <a href="#ranking" class="btn btn-main text-center font-extrabold px-6 py-3.5 rounded-full">{"この日" if is_archive else "今日"}のランキングを見る</a>
                    <a href="{html.escape(AMAZON_SALE_URL)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("amazon", "hero")} class="text-center bg-white hover:bg-orange-50 ring-1 ring-orange-200 text-ink font-bold px-6 py-3.5 rounded-full shadow-sm transition">Amazonタイムセール会場 ↗</a>
                </div>
            </div>
            <div class="hidden md:block">
                {hero_desktop}
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
        {drop_section}
        {sale_info_html(events, root)}
        <section class="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-amber-100 via-orange-50 to-orange-100 p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-5">
            <div class="pattern absolute inset-0" aria-hidden="true"></div>
            <div class="relative flex items-center gap-4">
                <span class="shrink-0 w-16 h-16 rounded-[1.25rem] bg-white shadow-soft flex items-center justify-center"><img src="{root}img/icons/share.svg" alt="" class="w-11 h-11"></span>
                <div>
                    <p class="text-lg md:text-xl font-extrabold text-ink">お得情報を友だちにも教えよう</p>
                    <p class="text-sm text-ink-soft mt-1 leading-relaxed">このページは毎日 朝・夕方の2回、自動で更新されます。ブックマークもおすすめです。</p>
                </div>
            </div>
            <a href="{html.escape(tweet_page_url)}" target="_blank" rel="noopener" class="relative shrink-0 bg-ink hover:bg-ink-soft text-white font-bold px-6 py-3.5 rounded-full text-center shadow-md transition">𝕏 このページをポスト</a>
        </section>
        {category_section_html(groups, root) if groups else ""}
        {about_html(root)}
        {archive_html(history, root, page_date)}
    </main>
{footer_html(root)}"""


def head_html(title, description, page_url, root, og_type, ld_json, noindex=False):
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
    <meta name="msvalidate.01" content="5B773A1BB4BCC01CAD0CA396B7247115">
    <link rel="canonical" href="{html.escape(page_url)}">
    <link rel="alternate" type="application/rss+xml" title="{html.escape(SITE_NAME)}" href="{SITE_URL}feed.xml">{'<meta name="robots" content="noindex, follow">' if noindex else ''}
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
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@700;800&family=M+PLUS+Rounded+1c:wght@400;500;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="{root}css/site.css?v={CSS_VERSION}">
    <style>{page_css}    </style>
    <script type="application/ld+json">{ld_json}</script>
    <script data-goatcounter="https://namikilog.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
</head>
<body class="bg-cream min-h-screen text-ink pb-24 md:pb-0">
    <div class="bg-white/80 text-ink-soft text-xs text-center py-1.5 px-4 border-b border-orange-100 leading-relaxed">【PR】当サイトはアフィリエイト広告（Amazonアソシエイト・{AD_PARTNERS}）を利用しています</div>"""


def footer_html(root):
    """全ページ共通のフッター・スマホ下部ボタン"""
    return f"""
    <footer class="bg-white border-t border-orange-100 text-[13px] text-ink-soft">
        <div class="max-w-5xl mx-auto px-4 py-10 space-y-3 leading-relaxed">
            <p class="flex items-center gap-2.5 text-ink font-extrabold text-base"><img src="{root}img/logo.svg" alt="" class="w-8 h-8">{html.escape(SITE_NAME)}</p>
            <p>{html.escape(SITE_TAGLINE)}。セール・値下げ情報を毎日 朝・夕方の2回自動更新しています。</p>
            <p class="flex flex-wrap gap-x-4 gap-y-1 font-bold"><a href="{root}index.html#category" class="hover:text-orange-600 hover:underline">カテゴリから探す</a>{"".join(f'<a href="{root}sale/{g["slug"]}.html" class="hover:text-orange-600 hover:underline">{html.escape(guide_label(g))}</a>' for g in SALE_GUIDES)}<a href="{root}drops.html" class="hover:text-orange-600 hover:underline">値下がり一覧</a><a href="{root}index.html#archive" class="hover:text-orange-600 hover:underline">アーカイブ</a><a href="{root}about.html" class="hover:text-orange-600 hover:underline">運営者情報・お問い合わせ</a></p>
            <p>Amazonのアソシエイトとして、当サイトは適格販売により収入を得ています。また、{AD_PARTNERS}を利用しています。</p>
            <p>掲載内容はAIが公開情報をもとに自動生成したものです。価格・在庫・ポイント倍率は変動するため、購入前に必ず各販売ページでご確認ください。</p>
            <p class="text-xs">最終更新: {TODAY_STR}（日本時間） © {NOW.year} {html.escape(SITE_NAME)}</p>
        </div>
    </footer>

    <div class="fixed bottom-0 inset-x-0 z-40 md:hidden bg-white/95 backdrop-blur border-t border-orange-100 px-3 pt-2.5 pb-[calc(.75rem+env(safe-area-inset-bottom))] grid grid-cols-2 gap-2.5">
        <a href="{html.escape(AMAZON_SALE_URL)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("amazon", "bar")} class="shop shop-amz shop-row">Amazonセール会場 <span aria-hidden="true">›</span></a>
        <a href="{html.escape(RAKUTEN_TOP_URL)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("rakuten", "bar")} class="shop shop-rkt shop-row">楽天市場を見る <span aria-hidden="true">›</span></a>
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
        for key in ("product_name", "category", "slot", "badge", "catch_copy", "deal_reason", "score", "image_url", "item_url",
                    "item_code", "item_name", "review_count", "review_average"):
            if deal.get(key) or key not in info:
                info[key] = deal.get(key)
        records = [r for r in info["records"] if r.get("t") != TODAY_STR]
        try:
            cur = int(deal.get("price_yen"))
        except (TypeError, ValueError):
            cur = 0
        prev_prices = [p for _, p, _ in price_points({"records": records})]
        deal["price_drop"], deal["record_low"] = price_trend(prev_prices, cur)
        deal["price_same"] = bool(cur and prev_prices and prev_prices[-1] == cur)
        if deal.get("slot") == "main" and deal["price_drop"]:
            deal["badge"] = info["badge"] = BADGES["drop"]
        records.append({"t": TODAY_STR, "price": deal.get("price_yen"), "point": deal.get("point_rate")})
        info["records"] = records[-PRODUCT_RECORDS:]
        deal["seen_count"] = featured_count(info)
        info["last_seen"] = TODAY_STR
        if cur:
            info["last_checked"] = TODAY_STR  # 今日の価格は記録済みなので、今日の価格チェックからは外す
        if deal.get("item_code"):  # 紹介し直した商品は、販売終了扱いでも価格チェックを再開する
            info.pop("track_off", None)
            info.pop("track_miss", None)
        products[pid] = info
    # 長く掲載されていない商品は削除してデータを肥大化させない
    cutoff = (NOW - timedelta(days=PRODUCT_KEEP_DAYS)).strftime("%Y-%m-%d")
    products = {k: v for k, v in products.items() if v.get("staple") or v.get("last_seen", "") >= cutoff}
    save_products(products)
    return products


def save_products(products):
    os.makedirs(os.path.dirname(PRODUCTS_PATH), exist_ok=True)
    with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=1)


def featured_count(info):
    """価格チェックの記録を除いた、実際にサイトで紹介した回数"""
    return sum(1 for r in info.get("records", []) if r.get("via") != "track")


def item_url_key(url):
    """楽天の商品ページURLから「ショップ/商品管理番号」を取り出す（?以降は無視）"""
    m = re.match(r"https://item\.rakuten\.co\.jp/([^/?#]+)/([^/?#]+)", str(url or ""))
    return f"{m[1]}/{m[2]}" if m else ""


def tracking_queries(info):
    """価格チェックの検索条件。商品コードが分かれば1回、分からなければショップ内を探す"""
    if info.get("item_code"):
        return [{"itemCode": info["item_code"]}]
    shop = item_url_key(info.get("item_url")).split("/")[0]
    words = [w for w in clean_product_name(info.get("product_name", "")).split() if len(w) >= 2][:3]
    queries = [{"shopCode": shop, "keyword": " ".join(words), "field": 0}] if words else []
    return queries + [{"shopCode": shop, "sort": "-reviewCount"}]


def staple_match(name, groups):
    low = unicodedata.normalize("NFKC", str(name)).lower()
    return all(any(w in low for w in group) for group in groups)


def seed_staples():
    """定番商品を楽天で探して商品データに加える。以後は track_prices が毎日価格を記録する"""
    if not RAKUTEN_APP_ID:
        return
    try:
        with open(STAPLES_PATH, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    products = load_products()
    searched = added = 0
    for label, keyword, groups, lo, hi in STAPLE_PRODUCTS:
        entry = state.get(label, {})
        if entry.get("pid") in products or int(entry.get("miss") or 0) >= STAPLE_MAX_MISSES:
            continue
        if searched >= STAPLE_MAX_SEARCH:
            break
        time.sleep(1.2)  # 楽天APIのレート制限(1秒1回)対策
        searched += 1
        try:
            hits = rakuten_request({"keyword": keyword, "sort": "-reviewCount", "hits": 30, "availability": 1,
                                    "minPrice": lo, "maxPrice": hi, "imageFlag": 1})
        except Exception as e:
            print(f"定番商品の検索 notice（{label}: {safe_status(e)}{rakuten_error_detail(e)}）")
            continue
        item = next((h for h in hits if staple_match(h.get("itemName"), groups) and h.get("itemUrl")), None)
        if not item:
            state[label] = {"miss": int(entry.get("miss") or 0) + 1}
            continue
        pid = product_id({"item_url": item["itemUrl"], "product_name": label})
        images = item.get("mediumImageUrls") or []
        image = images[0].get("imageUrl", "") if images and isinstance(images[0], dict) else (str(images[0]) if images else "")
        info = products.get(pid, {"records": []})
        info.update({"staple": True, "item_url": item["itemUrl"], "item_code": item.get("itemCode"),
                     "item_name": str(item.get("itemName", ""))[:200], "review_count": item.get("reviewCount") or 0,
                     "review_average": item.get("reviewAverage") or 0})
        info.setdefault("product_name", label)
        info.setdefault("badge", BADGES["staple"])
        info.setdefault("catch_copy", "定番モデルの価格を毎日記録中")
        info.setdefault("deal_reason", "・値下がりの有無に関わらず、楽天の参考価格を毎日記録しています\n"
                                       "・グラフで今の価格が高いか安いかを確認できます\n"
                                       "・値下がりしたらトップの「値下がりを見つけた商品」に載ります")
        info.setdefault("score", 0)
        if not info.get("image_url"):
            info["image_url"] = image.replace("_ex=128x128", "_ex=400x400")
        info.setdefault("last_seen", TODAY_STR)
        try:
            price = int(item.get("itemPrice") or 0)
        except (TypeError, ValueError):
            price = 0
        if price > 0:
            info["records"] = (info.get("records") or []) + [{"t": TODAY_STR, "price": price, "point": item.get("pointRate", 1), "via": "track"}]
            info["last_checked"] = TODAY_STR
        products[pid] = info
        state[label] = {"pid": pid}
        added += 1
    if searched:
        save_products(products)
        os.makedirs(os.path.dirname(STAPLES_PATH), exist_ok=True)
        with open(STAPLES_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        print(f"   定番商品: {searched}件を検索し{added}件を追加しました。")


def track_prices(skip_pids=()):
    """これまでに紹介した商品の楽天参考価格を、紹介した後も1日1回チェックして記録する"""
    if not RAKUTEN_APP_ID:
        return
    products = load_products()
    targets = sorted((str(info.get("last_checked") or ""), pid) for pid, info in products.items()
                     if pid not in skip_pids and not info.get("track_off") and item_url_key(info.get("item_url"))
                     and str(info.get("last_checked") or "")[:10] != TODAY_DATE)
    calls = errors = 0
    found, missed = [], []
    for _, pid in targets:
        if calls >= TRACK_MAX_CALLS or errors >= 3:
            break
        info = products[pid]
        key = item_url_key(info["item_url"])
        item, failed = None, False
        for params in tracking_queries(info):
            if calls >= TRACK_MAX_CALLS:
                failed = True
                break
            time.sleep(1.2)  # 楽天APIのレート制限(1秒1回)対策
            calls += 1
            try:
                hits = rakuten_request(dict(params, hits=30, availability=0))
            except Exception as e:
                print(f"価格チェック notice（{safe_status(e)}{rakuten_error_detail(e)}）")
                if getattr(getattr(e, "response", None), "status_code", None) == 400:
                    continue  # 検索語が使えないなど、この商品だけの問題
                errors += 1
                failed = True
                break
            errors = 0
            item = next((h for h in hits if (info.get("item_code") and h.get("itemCode") == info["item_code"])
                         or item_url_key(h.get("itemUrl")) == key), None)
            if item:
                break
        if failed:
            continue
        if not item:
            missed.append(pid)
            continue
        info["last_checked"] = TODAY_STR
        info.pop("track_miss", None)
        info["item_code"] = item.get("itemCode") or info.get("item_code")
        if item.get("itemName"):
            info["item_name"] = str(item["itemName"])[:200]
        try:
            price = int(item.get("itemPrice") or 0)
        except (TypeError, ValueError):
            price = 0
        if price <= 0 or item.get("availability") == 0:
            continue  # 売り切れ中は記録しない
        records = [r for r in info.get("records", []) if not (r.get("via") == "track" and str(r.get("t", ""))[:10] == TODAY_DATE)]
        records.append({"t": TODAY_STR, "price": price, "point": item.get("pointRate", 1), "via": "track"})
        info["records"] = records[-PRODUCT_RECORDS:]
        found.append(pid)
    # ほとんど見つからないときは検索方法の問題とみなし、「販売終了」の判定に数えない
    if found or len(missed) < 5:
        for pid in missed:
            info = products[pid]
            info["last_checked"] = TODAY_STR
            info["track_miss"] = int(info.get("track_miss") or 0) + 1
            if info["track_miss"] >= TRACK_MAX_MISSES:
                info["track_off"] = True
    elif missed:
        print(f"価格チェック: {len(missed)}件すべて見つからなかったため、今回は販売終了の判定に数えません。")
    save_products(products)
    print(f"   価格チェック: 対象{len(targets)}件中 記録{len(found)}件・見つからず{len(missed)}件（API {calls}回）")


def price_drops(products, skip_pids=(), days=1, limit=DROP_SHOW):
    """前回の記録から値下がりした紹介済みの商品（直近 days 日以内に記録したもの・下げ幅の大きい順）"""
    since = (NOW - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    drops = []
    for pid, info in products.items():
        points = price_points(info)
        if pid in skip_pids or len(points) < 2 or points[-1][0] < since:
            continue
        prev, latest = points[-2][1], points[-1][1]
        if prev - latest >= max(50, prev * 0.02):
            drops.append(((prev - latest) / prev, pid, info))
    drops.sort(key=lambda x: x[0], reverse=True)
    return [(pid, info) for _, pid, info in drops[:limit]]


def item_indexable(info):
    """商品ページを検索に載せるか：ブランド名・型番が分かり、3回以上紹介したか価格の記録が1週間分以上たまった商品"""
    if not model_words(display_name(info)):
        return False  # 「ワイヤレスイヤホン Bluetooth5.4」のような名前は検索されにくく、同名の商品とも区別できない
    if featured_count(info) >= INDEX_MIN_RECORDS:
        return True
    points = price_points(info)
    if len(points) < INDEX_MIN_POINTS:
        return False
    try:
        span = datetime.strptime(points[-1][0][:10], "%Y-%m-%d") - datetime.strptime(points[0][0][:10], "%Y-%m-%d")
    except ValueError:
        return False
    return span.days >= INDEX_MIN_DAYS


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
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#fff" stroke="#f97316" stroke-width="3"/>' for x, y in coords) if len(coords) <= 40 else ""
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
    seen = featured_count(info)
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
        verdict = ("bg-orange-50 text-orange-700 ring-orange-100", "記録中では高めの価格です")
    else:
        verdict = ("bg-slate-50 text-ink-soft ring-slate-200", "記録を始めたばかりです")
    stats = "".join(
        f'<div class="bg-orange-50/60 rounded-2xl p-3 text-center"><p class="text-xs font-bold text-ink-soft">{label}</p>'
        f'<p class="text-lg md:text-xl font-extrabold text-ink tabular-nums mt-1">{value}</p></div>'
        for label, value in (("最新", f"¥{latest:,}"), ("最安記録", f"¥{min(prices):,}"), ("最高記録", f"¥{max(prices):,}"), ("記録回数", f"{len(points)}回"))
    )
    chart = price_chart_svg(points) if len(points) >= 2 else ""
    featured_times = {r.get("t") for r in info.get("records", []) if r.get("via") != "track"}
    rows = "".join(
        f'<tr class="border-t border-orange-100"><td class="py-2.5 pr-3 whitespace-nowrap">{html.escape(t[:16].replace("-", "/"))}'
        + (' <span class="ml-1 text-[11px] font-bold text-orange-700 bg-orange-50 ring-1 ring-orange-100 rounded-full px-1.5 py-0.5">紹介</span>' if t in featured_times else "")
        + f'</td><td class="py-2.5 pr-3 text-right font-bold tabular-nums">¥{p:,}</td>'
        f'<td class="py-2.5 text-right whitespace-nowrap">{html.escape(str(pt))}倍</td></tr>'
        for t, p, pt in list(reversed(points))[:30]
    )
    more = f"（直近30件を表示・全{len(points)}件）" if len(points) > 30 else ""
    return f"""
            <section class="card p-5 md:p-7">
                <div class="flex items-center justify-between gap-3 flex-wrap">
                    <h2 class="text-lg md:text-xl font-extrabold text-ink">楽天参考価格の記録</h2>
                    <span class="{verdict[0]} ring-1 text-sm font-bold px-3 py-1 rounded-full">{verdict[1]}</span>
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-2.5 mt-4">{stats}</div>
                <div class="mt-5">{chart}</div>
                <table class="w-full text-sm mt-4">
                    <thead><tr class="text-xs text-ink-soft"><th class="text-left font-bold pb-2">記録日時{more}</th><th class="text-right font-bold pb-2 pr-3">価格</th><th class="text-right font-bold pb-2">ポイント</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
                <p class="text-xs text-ink-soft mt-4 leading-relaxed">当サイトが楽天市場の商品検索で取得した参考価格です。「紹介」は当サイトで紹介したときの価格で、紹介した後も1日1回価格をチェックして記録しています（掲載{seen}回）。現在の価格・在庫・ポイント倍率は各ストアでご確認ください。</p>
            </section>"""


def next_sale_guide():
    """商品ページの「いつ安い？」で案内する、次の大型セール（特集ページのあるもの）"""
    for guide in SALE_GUIDES:
        if guide.get("until", "") > TODAY_DATE:
            return guide
    return None


def when_cheap_html(info, root):
    """「いつ安い？」：記録中の最安値とその日、今の価格の位置づけ、次の大型セール（記録が3回以上ある商品だけ）"""
    points = price_points(info)
    if len(points) < 3:
        return ""
    name = display_name(info)
    prices = sorted(p for _, p, _ in points)
    low = prices[0]
    low_day = next(t for t, p, _ in points if p == low)[:10]
    usual = prices[len(prices) // 2]
    latest = points[-1][1]
    if latest <= low:
        now_text = f"今の楽天参考価格 ¥{latest:,} も、記録上の最安値と同じです。"
    elif abs(latest - usual) <= usual * 0.03:
        now_text = f"今の楽天参考価格 ¥{latest:,} は、いつもとほぼ同じ価格です（記録の中央値 ¥{usual:,}）。急ぎでなければ、セールまで待つ選択肢もあります。"
    elif latest < usual:
        now_text = f"今の楽天参考価格 ¥{latest:,} は、いつもより ¥{usual - latest:,} 安めです（記録の中央値 ¥{usual:,}）。"
    else:
        now_text = f"今の楽天参考価格 ¥{latest:,} は、いつもより ¥{latest - usual:,} 高めです（記録の中央値 ¥{usual:,}）。"
    md = lambda t: f"{t[5:7].lstrip('0')}月{t[8:10].lstrip('0')}日"
    if low == prices[-1]:
        record_text = f"当サイトの記録（{md(points[0][0])}から{len(points)}回）では、ずっと <b class=\"text-ink\">¥{low:,}</b> のまま変わっていません。"
        now_text = "値下がりしたらトップページの「値下がりを見つけた商品」でお知らせします。"
    else:
        record_text = f"当サイトの記録（{len(points)}回）で最も安かったのは、<b class=\"text-ink\">{md(low_day)}の ¥{low:,}</b> です。"
    guide = next_sale_guide()
    sale = ""
    if guide:
        when = "・".join(f"{k} {v}" for k, v in guide["dates"]) or "日程は未発表です（" + "・".join(f"{k} {v}" for k, v in guide["past"][:2]) + "）"
        sale = (f'<p class="mt-3">次の大型セールは<a href="{root}sale/{guide["slug"]}.html" class="font-bold text-orange-600 underline underline-offset-2">{html.escape(guide_label(guide))}</a>です。'
                f'{html.escape(when)}。セール中の価格も毎日記録するので、このページで普段の価格と比べられます。</p>')
    return f"""
            <section class="card p-5 md:p-7">
                <h2 class="text-lg md:text-xl font-extrabold text-ink">{html.escape(name)}はいつ安い？</h2>
                <div class="text-[15px] text-ink-soft leading-relaxed mt-3">
                    <p>{record_text}{html.escape(now_text)}</p>
                    {sale}
                </div>
                <p class="text-xs text-ink-soft mt-3 leading-relaxed">楽天市場の商品検索で取得した参考価格をもとにしています。Amazonの価格やクーポン・ポイントは含みません。</p>
            </section>"""


def render_item_page(pid, info):
    """商品ごとの詳細・価格記録ページ"""
    root = "../"
    page_url = f"{SITE_URL}item/{pid}.html"
    deal = dict(info, slot=info.get("slot") or "main", badge=info.get("badge") or BADGES["main"],
                category=info.get("category") or "ガジェット", catch_copy=info.get("catch_copy") or "",
                deal_reason=info.get("deal_reason") or "", image_url=info.get("image_url") or "")
    name = deal["product_name"] = display_name(info)
    points = price_points(info)
    latest = points[-1] if points else None
    if latest:
        deal["price_yen"], deal["point_rate"] = latest[1], latest[2]
        deal["price_drop"], deal["record_low"] = price_trend([p for _, p, _ in points[:-1]], latest[1])
        deal["price_same"] = len(points) >= 2 and points[-2][1] == latest[1]
    deal["seen_count"] = featured_count(info)
    seen = [r for r in info.get("records", []) if r.get("via") != "track"] or info.get("records", [])
    first_seen = seen[0]["t"][:10].replace("-", "/") if seen else ""
    checked = f"・価格チェック {latest[0][:10].replace('-', '/')}" if latest else ""
    if info.get("staple") and not featured_count(info):
        seen_text = f"記録開始 {first_seen}"
        checked = checked.lstrip("・")
        seen_text += "・" if checked else ""
    else:
        seen_text = f"初掲載 {first_seen}・最終掲載 {html.escape(str(info.get('last_seen', ''))[:10].replace('-', '/'))}"
    title = f"{name}の価格推移・" + ("安い時期" if len(points) >= 3 else "セール情報") + f"｜{SITE_NAME}"
    description = (f"{name}の楽天参考価格の記録" + ("を毎日更新中。" if info.get("staple") else "と、AIが選んだおすすめポイント。")
                   + (f"記録中の最安 ¥{min(p for _, p, _ in points):,}・価格の記録{len(points)}回。" if points else "")
                   + "Amazon・楽天の販売ページもすぐ確認できます。")
    cat = product_category(name)
    crumbs = [("ホーム", SITE_URL, f"{root}index.html")]
    if cat:
        crumbs.append((cat["name"], f"{SITE_URL}category/{cat['slug']}.html", f"{root}category/{cat['slug']}.html"))
    crumbs.append((name, page_url, ""))
    noindex = not item_indexable(info)
    graph = [{"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": n, "name": label, "item": url} for n, (label, url, _) in enumerate(crumbs, 1)]}]
    if latest and not noindex:
        # 検索結果に価格が出るよう、最新の楽天参考価格を Offer として載せる（他サイトのレビュー評価は載せない）
        product = {"@type": "Product", "name": name, "url": page_url,
                   "offers": {"@type": "Offer", "price": latest[1], "priceCurrency": "JPY",
                              "url": rakuten_item_url(info.get("item_url")) or page_url,
                              "availability": "https://schema.org/InStock"}}
        if deal["image_url"]:
            product["image"] = deal["image_url"]
        if deal["catch_copy"]:
            product["description"] = deal["catch_copy"]
        brand = model_words(name)
        if brand and re.fullmatch(r"[A-Za-z][A-Za-z\-]+|[^\x00-\x7f]+", brand[0]):
            product["brand"] = {"@type": "Brand", "name": brand[0]}
        graph.append(product)
    ld = {"@context": "https://schema.org", "@graph": graph}
    crumb_html = " › ".join(f'<a href="{href}" class="hover:text-orange-600 underline-offset-2 hover:underline">{html.escape(label)}</a>' if href
                            else f'<span class="text-ink font-bold">{html.escape(label)}</span>' for label, _, href in crumbs)
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    return f"""{head_html(title, description, page_url, root, "article", ld_json, noindex)}
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
        <nav class="text-sm text-ink-soft" aria-label="パンくずリスト">{crumb_html}</nav>
        <article class="card p-5 md:p-8">
            <div class="flex flex-col md:flex-row gap-5 md:gap-7">
                {thumbnail_html(deal, "w-full h-60 md:w-64 md:h-64", CARD_TONES[0], root)}
                <div class="flex-1 min-w-0">
                    {badges_html(deal)}
                    <h1 class="text-xl md:text-2xl font-extrabold text-ink leading-snug mt-3">{html.escape(name)}</h1>
                    <p class="mt-1.5 text-orange-600 font-bold">{html.escape(deal['catch_copy'])}</p>
                    <p class="mt-2 text-xs text-ink-soft">{seen_text}{checked}</p>
                    {price_html(deal)}
                    {reasons_html(deal, "text-[15px]")}
                    {grounds_html(deal, False, True)}
                    {cta_html(deal, page_url, root, False, "item")}
                </div>
            </div>
        </article>
        {when_cheap_html(info, root)}
        {price_history_html(info)}
        {f'<a href="{root}category/{cat["slug"]}.html" class="block card card-hover p-5 text-center font-extrabold text-ink">{html.escape(cat["name"])}のセール情報をもっと見る →</a>' if cat else ""}
        <a href="{root}index.html" class="block card card-hover p-5 text-center font-extrabold text-ink">今日のお買い得ランキングを見る →</a>
    </main>
{footer_html(root)}"""


# カテゴリ別まとめページ public/category/<slug>.html（商品名のキーワードで振り分け、上から順に判定）
CATEGORY_MIN_ITEMS = 3  # 商品がこの件数そろうまで、カテゴリページは検索に載せない
CATEGORIES = [
    {"slug": "mobile-monitor", "name": "モバイルモニター", "keywords": ("モバイルモニター", "モバイルディスプレイ", "ポータブルモニター", "タッチモニター"),
     "lead": "ノートPCのサブ画面やSwitchの外出先プレイに便利なモバイルモニターのセール・値下げ情報です。",
     "tips": ["USB-Cケーブル1本で映像と電源をまかなえるか（DisplayPort Alt Mode対応）を、手持ちのPC・スマホと合わせて確認しましょう。",
              "持ち歩くなら15.6インチ前後・1kg以下、据え置きのサブ画面なら解像度（2K・4K）やスタンドの有無を優先すると選びやすくなります。",
              "ノーブランド品は価格差が大きいので、レビュー件数と保証期間もあわせてチェックしましょう。"]},
    {"slug": "gaming-monitor", "name": "ゲーミングモニター", "keywords": ("ゲーミングモニター", "Hz"),
     "lead": "144Hz以上の高リフレッシュレートモニターを中心に、ゲーミングモニターのセール・値下げ情報をまとめています。",
     "tips": ["PS5やSwitch 2で使うなら、本体側が出せるリフレッシュレート（120Hzなど）を上回る性能は活かしきれない点に注意しましょう。",
              "PCゲーム中心なら、24〜27インチで180Hz以上が人気の価格帯です。",
              "パネルの種類（IPS・VA・TN）で色の鮮やかさや応答速度が変わります。"]},
    {"slug": "mobile-battery", "name": "モバイルバッテリー", "keywords": ("モバイルバッテリー", "Power Bank", "PowerCore"),
     "lead": "スマホやノートPCを外出先で充電できるモバイルバッテリーのセール・値下げ情報です。",
     "tips": ["10,000mAhでスマホ約2回分が目安です。ノートPCも充電するなら、出力45W以上のUSB PD対応を選びましょう。",
              "飛行機に持ち込めるのは、原則160Wh以下（一般的なモバイルバッテリーはほぼ該当）です。",
              "PSEマーク付きの製品を選ぶと安心です。"]},
    {"slug": "portable-power", "name": "ポータブル電源・ソーラーパネル", "keywords": ("ポータブル電源", "ソーラーパネル", "ソーラー", "Solar", "Jackery", "EcoFlow", "PowerArQ"),
     "lead": "キャンプや防災に使えるポータブル電源・ソーラーパネルのセール・値下げ情報です。",
     "tips": ["容量（Wh）は、使いたい家電の消費電力×使用時間で見積もると失敗しにくくなります。",
              "長く使うなら、充放電の寿命が長いリン酸鉄リチウムイオン電池のモデルが人気です。",
              "大型セールでは、本体とソーラーパネルのセットが大きく値下がりしやすい傾向があります。"]},
    {"slug": "earbuds", "name": "ワイヤレスイヤホン・ヘッドホン", "keywords": ("イヤホン", "ヘッドホン", "ヘッドフォン", "AirPods", "Buds", "完全ワイヤレス"),
     "lead": "完全ワイヤレスイヤホンやヘッドホンのセール・値下げ情報をまとめています。",
     "tips": ["電車や飛行機で使うなら、ノイズキャンセリング（ANC）対応が快適です。",
              "iPhoneならAAC、AndroidならLDACなど、スマホ側が対応するコーデックもあわせて確認しましょう。",
              "通話が多い人は、マイクのノイズ低減（ENCなど）の有無もチェックしましょう。"]},
    {"slug": "speaker", "name": "Bluetoothスピーカー", "keywords": ("スピーカー", "サウンドバー"),
     "lead": "アウトドアやお風呂で使えるBluetoothスピーカーのセール・値下げ情報です。",
     "tips": ["屋外や水まわりで使うなら、防水・防塵等級（IP67など）を確認しましょう。",
              "同じ機種を2台つなげるステレオ再生に対応したモデルもあります。"]},
    {"slug": "smartwatch", "name": "スマートウォッチ", "keywords": ("スマートウォッチ", "ウォッチ", "Watch", "スマートバンド"),
     "lead": "健康管理や通知確認に便利なスマートウォッチのセール・値下げ情報です。",
     "tips": ["iPhoneで使う場合、一部の機能（通知への返信など）が使えないモデルもあります。",
              "バッテリー持ちは数日〜2週間程度と、モデルによって大きく差があります。"]},
    {"slug": "storage", "name": "SDカード・ストレージ", "keywords": ("microSD", "SDカード", "SSD", "HDD", "USBメモリ"),
     "lead": "microSDカードやSSDなど、ストレージのセール・値下げ情報です。",
     "tips": ["Switchやドラレコ用のmicroSDは、書き込み速度の規格（U3・V30など）を確認しましょう。",
              "大容量品ほど、セール時の値下がり幅が大きくなりやすい傾向があります。"]},
    {"slug": "charger-cable", "name": "充電器・ケーブル", "keywords": ("充電器", "充電ステーション", "ケーブル", "GaN", "アダプタ", "電源タップ", "延長コード"),
     "lead": "USB PD急速充電器やケーブル、電源タップのセール・値下げ情報です。",
     "tips": ["ノートPCも充電するなら65W以上、スマホ中心なら20〜30Wが目安です。",
              "GaN（窒化ガリウム）採用の充電器は、同じ出力でも小型・軽量です。",
              "送料無料ラインやポイントアップ条件にあと少し届かないときの「ついで買い」にも向いています。"]},
    {"slug": "dashcam", "name": "ドライブレコーダー", "keywords": ("ドライブレコーダー", "ドラレコ"),
     "lead": "前後2カメラやミラー型を中心に、ドライブレコーダーのセール・値下げ情報です。",
     "tips": ["あおり運転対策なら、前後2カメラのモデルがおすすめです。",
              "夜間の映像は、解像度だけでなくHDRや暗所撮影の性能で差が出ます。"]},
    {"slug": "robot-cleaner", "name": "ロボット掃除機", "keywords": ("ロボット掃除機", "掃除ロボット", "Roomba", "ルンバ", "DEEBOT"),
     "lead": "ルンバやDEEBOTなど、ロボット掃除機のセール・値下げ情報です。",
     "tips": ["ゴミ収集ステーション付きのモデルは、ゴミ捨ての手間が数週間に1回まで減ります。",
              "水拭き対応モデルは、モップの自動洗浄・乾燥の有無で手入れの手間が大きく変わります。",
              "家具の下を通すなら、本体の高さ（薄型かどうか）を確認しましょう。"]},
    {"slug": "keyboard-mouse", "name": "キーボード・マウス", "keywords": ("キーボード", "マウス", "トラックボール"),
     "lead": "ワイヤレスキーボードやマウスなど、PC周辺機器のセール・値下げ情報です。",
     "tips": ["複数のPC・タブレットを切り替えて使うなら、マルチペアリング対応が便利です。",
              "静音クリックのマウスは、カフェや夜の作業でも気になりにくくなります。"]},
    {"slug": "water", "name": "炭酸水・ミネラルウォーター", "keywords": ("炭酸水", "ミネラルウォーター", "天然水", "SODA"),
     "lead": "炭酸水やミネラルウォーターの箱買い・まとめ買いのセール情報です。送料無料ラインに届かせたいときの「ついで買い」にも向いています。",
     "tips": ["1本あたりの価格（総額÷本数）で比べると、セール価格のお得さが分かりやすくなります。",
              "長期保存水は、防災用の備蓄にも使えます。"]},
    {"slug": "drycell", "name": "乾電池", "keywords": ("乾電池", "電池"),
     "lead": "アルカリ乾電池のまとめ買いセール情報です。",
     "tips": ["40本セットなどの大容量パックは、1本あたりの価格がかなり下がります。",
              "リモコンや時計など消費電力の小さい機器には、アルカリ乾電池が長持ちで向いています。"]},
    {"slug": "tv-streaming", "name": "Fire TV・映像機器", "keywords": ("Fire TV", "テレビ", "プロジェクター", "Chromecast"),
     "lead": "Fire TV Stickやプロジェクターなど、映像機器のセール・値下げ情報です。",
     "tips": ["Fire TV Stickは、Amazonの大型セールで大きく値下がりしやすい定番商品です。",
              "4Kテレビで使うなら、4K対応モデル（4K Maxなど）を選びましょう。"]},
]

# 大型セールの特集ページ public/sale/<slug>.html（日程が発表されたら dates を更新する。label が無ければ「名前+年」で表示）
SALE_GUIDES = [
    {
        "slug": "black-friday", "name": "Amazonブラックフライデー", "year": 2026, "until": "2026-12-02",  # until: 商品ページの「次の大型セール」に出す期限（終わる目安の翌日）
        "dates": [],  # 例: [("先行セール", "11月20日(金)〜11月22日(日)"), ("本セール", "11月23日(月)〜11月30日(月)")]
        "past": [("2025年 先行セール", "11月21日(金)〜11月23日(日)"), ("2025年 本セール", "11月24日(月)〜12月1日(月)")],
        "lead": "Amazonブラックフライデーは、プライム会員以外も参加できる年末の大型セールです。ガジェット・家電は1年の中でも値下がりしやすいタイミングなので、狙いのジャンルと事前準備をまとめました。",
        "prep": [
            ("ポイントアップキャンペーンにエントリー", "期間中の合計購入額に応じてポイント還元が上乗せされるキャンペーンは、エントリーが必要です。2025年は本セールの約10日前から受付が始まりました。"),
            ("ほしい物リストに入れて普段の価格を見ておく", "セール価格が本当に安いかは、普段の価格と比べないと分かりません。当サイトの各商品ページの「価格の記録」も参考にしてください。"),
            ("先行セールもチェック", "2025年は本セールの3日前から先行セールがあり、一部の対象商品は本セールと同じ価格で先に購入できました。"),
            ("楽天のイベントとも比べる", "同じ時期に楽天市場でもブラックフライデーやお買い物マラソンが開かれることがあります。ポイント込みの実質価格で比べましょう。"),
        ],
        "faq": [
            ("2026年のAmazonブラックフライデーはいつから？", "2026年の日程は、まだAmazonから発表されていません（このページの最終更新時点）。2025年は先行セールが11月21日から、本セールが11月24日から12月1日まででした。発表され次第、このページを更新します。"),
            ("プライム会員でなくても参加できますか？", "はい。プライム感謝祭やプライムデーと違い、ブラックフライデーは会員以外も参加できます。ただし、配送の特典などは会員と異なります。"),
            ("どんなガジェットが安くなりやすいですか？", "Amazonデバイス（Fire TV Stick・Echo・Kindleなど）、Ankerなどの充電器・モバイルバッテリー、ワイヤレスイヤホン、モニターなどが値下がりしやすい定番です。"),
        ],
        "source": ("マイナビニュース（2025年11月14日）", "https://news.mynavi.jp/article/20251114-3666546/"),
    },
    {
        "slug": "rakuten-super-sale", "name": "楽天スーパーSALE", "year": 2026, "label": "楽天スーパーSALE 2026年12月", "until": "2026-12-12",
        "dates": [],  # 例: [("本セール", "12月4日(木)20:00〜12月11日(木)1:59")]
        "past": [("2025年12月", "12月4日(木)20:00〜12月11日(木)1:59")],
        "lead": "楽天スーパーSALEは、3月・6月・9月・12月の年4回開かれる楽天市場の大型セールです。半額以下の商品が並ぶうえ、複数のショップで買うほどポイント倍率が上がる「ショップ買いまわり」があるので、ガジェットとついで買いをまとめて買う絶好のタイミングです。",
        "prep": [
            ("キャンペーンにエントリー", "ショップ買いまわりなどのポイントアップは、事前のエントリーが必要です。エントリーはセール開始前から受付が始まります。"),
            ("買うものを10ショップ分リストにしておく", "ショップ買いまわりは、1,000円以上の買い物をしたショップの数に応じてポイント倍率が上がります（上限あり）。本命のガジェットに、充電ケーブルや乾電池など1,000円台の日用品を組み合わせると達成しやすくなります。"),
            ("普段の価格を確認しておく", "セール価格が本当に安いかは、普段の価格と比べないと分かりません。当サイトの各商品ページの「価格の記録」も参考にしてください。"),
            ("開始直後と最終日のタイムセールに注意", "開始直後や終了間際は、数量限定の半額・タイムセールが集中します。狙いの商品は事前にお気に入り登録しておきましょう。"),
        ],
        "faq": [
            ("次の楽天スーパーSALEはいつ？", "2026年12月の日程は、まだ楽天市場から発表されていません（このページの最終更新時点）。2025年12月は、12月4日(木)20:00〜12月11日(木)1:59でした。発表され次第、このページを更新します。"),
            ("ショップ買いまわりとは？", "期間中に1,000円以上（税込）の買い物をしたショップの数に応じて、ポイント倍率が上がるキャンペーンです。上限や対象条件は回によって異なるので、公式のキャンペーンページで確認しましょう。"),
            ("どんなガジェットが安くなりやすいですか？", "モバイルバッテリーや充電器、ワイヤレスイヤホン、モバイルモニターなど、楽天のショップが多く扱うジャンルは半額・クーポン対象になりやすい定番です。"),
        ],
        "source": ("ライフハッカー・ジャパン（2025年12月）", "https://www.lifehacker.jp/article/rakuten-supersale-2025-1205-2/"),
    },
    {
        "slug": "amazon-hatsuuri", "name": "Amazon初売り", "year": 2027, "until": "2027-01-08",
        "dates": [],  # 例: [("初売り", "1月3日(日)9:00〜1月7日(木)23:59")]
        "past": [("2026年", "1月3日(土)9:00〜1月7日(水)23:59"), ("2025年", "1月3日(金)9:00〜1月7日(火)23:59")],
        "lead": "Amazon初売りは、毎年1月3日から開かれるAmazonの年始セールです。プライム会員以外も参加でき、年末年始の買い替えや新生活の準備に使いやすいタイミングです。",
        "prep": [
            ("ポイントアップ・スタンプラリーにエントリー", "初売りでは、エントリーが必要なポイントキャンペーンが行われることが多く、2026年は12月27日から受付が始まりました。"),
            ("事前公開ページで目玉商品をチェック", "2026年は12月27日に、お買い得商品の一部が事前公開されました。ほしい物リストに入れておくと、当日の値下がりに気づきやすくなります。"),
            ("普段の価格を確認しておく", "セール価格が本当に安いかは、普段の価格と比べないと分かりません。当サイトの各商品ページの「価格の記録」も参考にしてください。"),
            ("楽天の新春セールとも比べる", "同じ時期に楽天市場でも新春のセールやお買い物マラソンが開かれることがあります。ポイント込みの実質価格で比べましょう。"),
        ],
        "faq": [
            ("2027年のAmazon初売りはいつから？", "2027年の日程は、まだAmazonから発表されていません（このページの最終更新時点）。2026年は1月3日(土)9:00〜1月7日(水)23:59の5日間で、例年1月3日から始まっています。発表され次第、このページを更新します。"),
            ("プライム会員でなくても参加できますか？", "はい。初売りは会員以外も参加できます。ただし、配送の特典などは会員と異なります。"),
            ("どんなガジェットが安くなりやすいですか？", "Amazonデバイス（Fire TV Stick・Echo・Kindleなど）、Ankerなどの充電器・モバイルバッテリー、ワイヤレスイヤホンなどが値下がりしやすい定番です。"),
        ],
        "source": ("ECのミカタ（2025年12月）", "https://ecnomikata.com/ecnews/ecmall/49140/"),
    },
]


def guide_label(guide):
    return guide.get("label") or f"{guide['name']}{guide['year']}"


def product_category(name):
    """商品名からカテゴリ（CATEGORIES の要素）を決める。当てはまらなければ None"""
    low = str(name).lower()
    for cat in CATEGORIES:
        if any(k.lower() in low for k in cat["keywords"]):
            return cat
    return None


def products_by_category(products):
    groups = {cat["slug"]: [] for cat in CATEGORIES}
    for pid, info in products.items():
        cat = product_category(clean_product_name(info.get("product_name", "")))
        if cat:
            groups[cat["slug"]].append((pid, info))
    for items in groups.values():
        items.sort(key=lambda x: x[1].get("last_seen", ""), reverse=True)
    return groups


def simple_header_html(root, max_w="max-w-3xl"):
    return f"""
    <header class="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-orange-100">
        <div class="{max_w} mx-auto px-4 h-16 flex items-center justify-between gap-3">
            <a href="{root}index.html" class="flex items-center gap-2.5 min-w-0">
                <img src="{root}img/logo.svg" alt="" class="w-10 h-10 shrink-0">
                <span class="leading-tight min-w-0">
                    <span class="block text-xs font-bold text-orange-600">AI厳選</span>
                    <span class="block font-extrabold text-[17px] text-ink truncate">ガジェット特価速報</span>
                </span>
            </a>
            <a href="{root}index.html" class="btn btn-main shrink-0 text-sm font-bold px-4 py-2.5 rounded-full">今日の特価 →</a>
        </div>
    </header>"""


def item_list_card(pid, info, root):
    """カテゴリページ用の商品カード（価格の記録の要約つき）"""
    name = display_name(info)
    deal = {"product_name": name, "image_url": info.get("image_url") or "", "slot": info.get("slot") or "main"}
    points = price_points(info)
    seen = featured_count(info)
    if points:
        prices = [p for _, p, _ in points]
        price_line = (f'<span class="num text-xl font-extrabold text-ink">¥{prices[-1]:,}</span>'
                      f'<span class="text-xs text-ink-soft">最新の楽天参考価格</span>')
        if len(prices) >= 2 and prices[-1] < prices[-2]:
            price_line += f'<span class="text-xs font-bold text-emerald-700">前回の記録より ¥{prices[-2] - prices[-1]:,} 値下がり</span>'
        elif len(prices) >= 2:
            price_line += f'<span class="text-xs font-bold text-emerald-700">最安記録 ¥{min(prices):,}</span>'
    else:
        price_line = '<span class="text-xs text-ink-soft">価格は各ストアでご確認ください</span>'
    amz_url, rkt_url = build_affiliate_urls(name, info.get("item_url", ""))
    last = str(info.get("last_seen", ""))[:10].replace("-", "/")
    return f"""
            <article class="card p-4 md:p-5 flex gap-4">
                {thumbnail_html(deal, "w-24 h-24 md:w-28 md:h-28", CARD_TONES[0], root)}
                <div class="flex-1 min-w-0">
                    <h3 class="font-extrabold text-ink leading-snug"><a href="{root}item/{pid}.html" class="hover:text-orange-600 hover:underline underline-offset-2">{html.escape(name)}</a></h3>
                    <p class="text-sm text-orange-600 font-bold mt-1">{html.escape(info.get("catch_copy") or "")}</p>
                    <div class="flex items-baseline gap-x-2 gap-y-1 flex-wrap mt-2">{price_line}</div>
                    <p class="text-xs text-ink-soft mt-1">最終掲載 {last}・掲載{seen}回</p>
                    <div class="flex gap-2 mt-3 flex-wrap text-sm font-bold">
                        <a href="{root}item/{pid}.html" class="text-orange-600 hover:underline underline-offset-2">価格の記録 ›</a>
                        <a href="{html.escape(amz_url)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("amazon", "category")} class="text-ink-soft hover:text-ink hover:underline underline-offset-2">Amazon ›</a>
                        <a href="{html.escape(rkt_url)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("rakuten", "category")} class="text-ink-soft hover:text-ink hover:underline underline-offset-2">楽天 ›</a>
                    </div>
                </div>
            </article>"""


def drop_card(pid, info, root):
    """「値下がりを見つけた商品」用のカード（前回の記録→最新の価格）"""
    name = display_name(info)
    deal = {"product_name": name, "image_url": info.get("image_url") or "", "slot": info.get("slot") or "main"}
    prices = [p for _, p, _ in price_points(info)]
    prev, latest = prices[-2], prices[-1]
    chips = (f'<span class="text-[11px] md:text-xs font-bold text-emerald-700 bg-emerald-50 ring-1 ring-emerald-200 px-2 py-0.5 rounded-full">'
             f'¥{prev - latest:,} 値下がり</span>')
    if latest <= min(prices[:-1]):
        chips += ('<span class="text-[11px] md:text-xs font-bold text-white bg-emerald-600 px-2 py-0.5 rounded-full" '
                  'title="当サイトが記録した楽天参考価格の中で最も安い価格です">記録中の最安</span>')
    amz_url, rkt_url = build_affiliate_urls(name, info.get("item_url", ""))
    return f"""
            <article class="card card-hover p-4 md:p-5 flex gap-3 md:gap-4">
                {thumbnail_html(deal, "w-20 h-20 md:w-28 md:h-28", CARD_TONES[0], root)}
                <div class="flex-1 min-w-0">
                    <h3 class="text-[15px] md:text-base font-extrabold text-ink leading-snug line-clamp-2"><a href="{root}item/{pid}.html" class="hover:text-orange-600 hover:underline underline-offset-2">{html.escape(name)}</a></h3>
                    <div class="flex items-baseline gap-x-1.5 gap-y-1 flex-wrap mt-1.5">
                        <span class="text-xs text-ink-soft line-through tabular-nums"><span class="sr-only">前回の記録 </span>¥{prev:,}</span>
                        <span class="text-xs text-ink-soft" aria-hidden="true">→</span>
                        <span class="num text-xl font-extrabold text-ink"><span class="sr-only">最新 </span>¥{latest:,}</span>
                    </div>
                    <div class="flex gap-1.5 flex-wrap mt-1.5">{chips}</div>
                    <div class="flex gap-x-3 gap-y-1 mt-2.5 flex-wrap text-[13px] md:text-sm font-bold">
                        <a href="{root}item/{pid}.html" class="text-orange-600 hover:underline underline-offset-2">価格の記録 ›</a>
                        <a href="{html.escape(amz_url)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("amazon", "drop")} class="text-ink-soft hover:text-ink hover:underline underline-offset-2">Amazon ›</a>
                        <a href="{html.escape(rkt_url)}" target="_blank" rel="nofollow noopener sponsored" {click_attrs("rakuten", "drop")} class="text-ink-soft hover:text-ink hover:underline underline-offset-2">楽天 ›</a>
                    </div>
                </div>
            </article>"""


def category_links_html(groups, root, current=""):
    """カテゴリへのリンク一覧（商品があるカテゴリだけ）"""
    links = ""
    for cat in CATEGORIES:
        count = len(groups.get(cat["slug"], []))
        if not count:
            continue
        active = "bg-orange-500 text-white ring-orange-500" if cat["slug"] == current else "bg-white text-ink ring-orange-100 hover:bg-orange-50"
        links += (f'<a href="{root}category/{cat["slug"]}.html" class="{active} ring-1 shadow-sm rounded-full px-4 py-2 text-sm font-bold transition">'
                  f'{html.escape(cat["name"])} <span class="text-xs opacity-70">{count}</span></a>')
    return f'<div class="flex flex-wrap gap-2">{links}</div>' if links else ""


def category_section_html(groups, root):
    """トップページの「カテゴリから探す」と特集ページへの入口"""
    links = category_links_html(groups, root)
    sale_links = "".join(
        f'<a href="{root}sale/{g["slug"]}.html" class="block card card-hover p-5 font-extrabold text-ink">'
        f'{html.escape(guide_label(g))} の狙い目と準備 <span aria-hidden="true">›</span></a>'
        for g in SALE_GUIDES)
    return f"""
        <section id="category" class="scroll-mt-24">
            {section_head("cart", "カテゴリから探す", "これまでに紹介した商品を、ジャンルごとに価格の記録と一緒にまとめています。", root)}
            {links}
            <div class="grid gap-3 md:grid-cols-2 mt-5">{sale_links}</div>
        </section>"""


def render_category_page(cat, items, groups, top_deals):
    root = "../"
    page_url = f"{SITE_URL}category/{cat['slug']}.html"
    name = cat["name"]
    title = f"{name}のセール・値下げ情報と価格推移｜{SITE_NAME}"
    names = "、".join(display_name(i) for _, i in items[:2])
    description = (f"{name}のセール・値下げ情報を、楽天参考価格の記録と一緒にまとめています。"
                   + (f"{names}など{len(items)}件掲載。" if items else "") + "毎日 朝・夕方に自動更新。")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": name, "item": page_url}]},
        {"@type": "ItemList", "name": f"{name}のセール・値下げ情報", "itemListElement": [
            {"@type": "ListItem", "position": n, "name": display_name(i), "url": f"{SITE_URL}item/{pid}.html"}
            for n, (pid, i) in enumerate(items[:30], 1)]},
    ]}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    cards = "".join(item_list_card(pid, info, root) for pid, info in items[:30])
    if not cards:
        cards = '<p class="card p-5 text-ink-soft">このカテゴリの商品は、まだ掲載されていません。毎日の更新で見つかり次第ここに追加されます。</p>'
    tips = "".join(f'<li class="flex gap-2.5"><span class="w-5 h-5 mt-0.5 shrink-0 rounded-full bg-emerald-100 text-emerald-600 text-[11px] font-extrabold flex items-center justify-center">✓</span>'
                   f'<span>{html.escape(t)}</span></li>' for t in cat["tips"])
    today = "".join(f'<li><a href="{root}index.html#deal-{n}" class="hover:text-orange-600 hover:underline underline-offset-2">{html.escape(d["product_name"])}</a></li>'
                    for n, d in enumerate(top_deals[:4], 1))
    noindex = len(items) < CATEGORY_MIN_ITEMS
    return f"""{head_html(title, description, page_url, root, "article", ld_json, noindex)}
    {simple_header_html(root)}
    <main class="max-w-3xl mx-auto px-4 pt-6 pb-16 space-y-6">
        <nav class="text-sm text-ink-soft" aria-label="パンくずリスト"><a href="{root}index.html" class="hover:text-orange-600 underline-offset-2 hover:underline">ホーム</a> › <span class="text-ink font-bold">{html.escape(name)}</span></nav>
        <section class="card p-5 md:p-7">
            <h1 class="text-2xl md:text-3xl font-extrabold text-ink leading-snug">{html.escape(name)}のセール・値下げ情報</h1>
            <p class="mt-3 text-ink-soft leading-relaxed">{html.escape(cat["lead"])}当サイトが毎日 朝・夕方に紹介した商品と、楽天参考価格の記録を新しい順に並べています。</p>
            <p class="mt-2 text-xs text-ink-soft">掲載 {len(items)}件・最終更新 {TODAY_STR}</p>
        </section>
        <section class="space-y-4">{cards}
        </section>
        <section class="card p-5 md:p-7">
            <h2 class="text-lg md:text-xl font-extrabold text-ink">{html.escape(name)}を選ぶときのポイント</h2>
            <ul class="space-y-2 text-[15px] text-ink leading-relaxed mt-4">{tips}</ul>
        </section>
        <section class="card p-5 md:p-7">
            <h2 class="text-lg md:text-xl font-extrabold text-ink">ほかのカテゴリ</h2>
            <div class="mt-4">{category_links_html(groups, root, cat["slug"])}</div>
            {f'<h2 class="text-lg md:text-xl font-extrabold text-ink mt-6">今日のお買い得</h2><ul class="list-disc pl-5 mt-3 space-y-1 text-[15px] font-bold text-ink">{today}</ul>' if today else ""}
        </section>
    </main>
{footer_html(root)}"""


def render_feed(products):
    """RSSフィード public/feed.xml（最近サイトで紹介した商品を新しい順に。価格チェックだけの更新は載せない）"""
    def stamp(info):
        return str(info.get("last_seen", ""))
    items = sorted(products.items(), key=lambda kv: stamp(kv[1]), reverse=True)[:FEED_SHOW]
    entries = []
    for pid, info in items:
        points = price_points(info)
        price = f"楽天参考価格 ¥{points[-1][1]:,}" if points else ""
        try:
            pub = datetime.strptime(stamp(info)[:16], "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        except ValueError:
            pub = NOW
        desc = "。".join(x for x in (info.get("catch_copy") or "", price) if x)
        url = f"{SITE_URL}item/{pid}.html"
        entries.append(f"""    <item>
      <title>{html.escape(display_name(info))}</title>
      <link>{url}</link>
      <guid isPermaLink="false">{pid}-{html.escape(stamp(info)[:10])}</guid>
      <pubDate>{pub.strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate>
      <description>{html.escape(desc)}</description>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{html.escape(SITE_NAME)}</title>
    <link>{SITE_URL}</link>
    <atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>
    <description>{html.escape(SITE_TAGLINE)}。毎日 朝・夕方に更新。</description>
    <language>ja</language>
    <lastBuildDate>{NOW.strftime("%a, %d %b %Y %H:%M:%S %z")}</lastBuildDate>
{chr(10).join(entries)}
  </channel>
</rss>
"""


def ping_indexnow():
    """デプロイ後に、サイトマップのうち今日更新したURLを IndexNow（Bing・Yandexなど）へ通知する"""
    try:
        with open("public/sitemap.xml", encoding="utf-8") as f:
            sitemap = f.read()
    except FileNotFoundError:
        print("IndexNow: sitemap.xml が無いため通知しません。")
        return
    urls = [loc for loc, lastmod in re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", sitemap) if lastmod[:10] == TODAY_DATE]
    if not urls or not SITE_URL.startswith("https://"):
        print("IndexNow: 通知するURLがありません。")
        return
    host = urllib.parse.urlparse(SITE_URL).netloc
    try:
        res = requests.post("https://api.indexnow.org/indexnow", timeout=20, json={
            "host": host, "key": INDEXNOW_KEY, "keyLocation": f"{SITE_URL}{INDEXNOW_KEY}.txt", "urlList": urls[:10000]})
        print(f"IndexNow: {len(urls)}件を通知しました（HTTP {res.status_code}）")
    except Exception as e:
        print(f"IndexNow notice: {safe_status(e)}")


def render_drops_page(drops, groups):
    """値下がり一覧 public/drops.html（直近数日の値下がりを下げ幅の大きい順に）"""
    root = ""
    page_url = f"{SITE_URL}drops.html"
    title = f"【{md_date(NOW)}更新】値下がりしたガジェット・家電一覧｜{SITE_NAME}"
    names = "、".join(display_name(i) for _, i in drops[:2])
    description = (f"これまでに紹介したガジェット・家電の楽天参考価格を毎日チェックし、直近{DROP_PAGE_DAYS}日で値下がりした商品を下げ幅の大きい順にまとめています。"
                   + (f"{names}など{len(drops)}件。" if drops else ""))
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "値下がり一覧", "item": page_url}]},
        {"@type": "ItemList", "name": "値下がりしたガジェット・家電", "itemListElement": [
            {"@type": "ListItem", "position": n, "name": display_name(i), "url": f"{SITE_URL}item/{pid}.html"}
            for n, (pid, i) in enumerate(drops, 1)]},
    ]}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    cards = "".join(drop_card(pid, info, root) for pid, info in drops)
    if not cards:
        cards = '<p class="card p-5 text-ink-soft md:col-span-2">直近で値下がりした商品は見つかりませんでした。毎日 朝・夕方の価格チェックで見つかり次第ここに追加されます。</p>'
    return f"""{head_html(title, description, page_url, root, "website", ld_json, len(drops) < DROP_PAGE_MIN)}
    {simple_header_html(root, "max-w-5xl")}
    <main class="max-w-5xl mx-auto px-4 pt-6 pb-16 space-y-6">
        <nav class="text-sm text-ink-soft" aria-label="パンくずリスト"><a href="index.html" class="hover:text-orange-600 underline-offset-2 hover:underline">ホーム</a> › <span class="text-ink font-bold">値下がり一覧</span></nav>
        <section class="card p-5 md:p-7">
            <h1 class="text-2xl md:text-3xl font-extrabold text-ink leading-snug">値下がりしたガジェット・家電一覧</h1>
            <p class="mt-3 text-ink-soft leading-relaxed">当サイトでこれまでに紹介した商品の楽天参考価格を毎日 朝・夕方にチェックし、直近{DROP_PAGE_DAYS}日で前回の記録より下がった商品を、下げ幅の大きい順に並べています。「記録中の最安」は、当サイトが記録した価格の中で最も安いことを表します。</p>
            <p class="mt-2 text-xs text-ink-soft">{len(drops)}件・最終更新 {TODAY_STR}</p>
        </section>
        <section class="grid gap-5 md:grid-cols-2">{cards}
        </section>
        <section class="card p-5 md:p-7">
            <h2 class="text-lg md:text-xl font-extrabold text-ink">カテゴリから探す</h2>
            <div class="mt-4">{category_links_html(groups, root)}</div>
        </section>
    </main>
{footer_html(root)}"""


def render_x_share_page(deals):
    """運営者用：今日の紹介商品をワンタップでXに投稿するページ（リンクなし・noindex・サイトマップ対象外）"""
    root = "../"
    cards = []
    for deal in [d for d in deals if not d.get("is_sample")][:4]:
        text = urllib.parse.parse_qs(urllib.parse.urlparse(build_tweet_url(deal, SITE_URL)).query)["text"][0]
        cards.append(f"""
        <div class="card p-5">
            <p class="font-extrabold text-ink">{html.escape(deal['product_name'])}</p>
            <pre class="mt-3 whitespace-pre-wrap text-sm text-ink leading-relaxed font-sans">{html.escape(text)}</pre>
            <a href="{html.escape(build_tweet_url(deal, SITE_URL))}" target="_blank" rel="noopener"
               class="mt-4 block text-center bg-black text-white font-bold py-3 rounded-full">𝕏 この内容で投稿する</a>
        </div>""")
    body = "".join(cards) or '<p class="card p-5">今日の紹介商品はまだありません。</p>'
    return f"""{head_html(f"X投稿用（{TODAY_STR}更新）｜{SITE_NAME}", "運営者用のX投稿ページです。", f"{SITE_URL}share/x.html", root, "website", "{}", True)}
    <main class="max-w-xl mx-auto px-4 py-8 space-y-4">
        <h1 class="text-xl font-extrabold text-ink">X投稿用（{TODAY_STR} 更新）</h1>
        <p class="text-sm text-ink-soft">ボタンを押すと、文面とリンクが入った状態でXの投稿画面が開きます。1日1〜2件が目安です。</p>
        {body}
    </main>
</body>
</html>"""


def render_404_page(groups):
    """GitHub Pages が存在しないURLで返す public/404.html（販売終了で削除した商品ページなど）"""
    root = "/"
    return f"""{head_html(f"ページが見つかりません｜{SITE_NAME}", "お探しのページは見つかりませんでした。", SITE_URL, root, "website", "{}", True)}
    {simple_header_html(root)}
    <main class="max-w-3xl mx-auto px-4 pt-6 pb-16 space-y-6">
        <section class="card p-5 md:p-7">
            <h1 class="text-2xl md:text-3xl font-extrabold text-ink leading-snug">ページが見つかりませんでした</h1>
            <p class="mt-3 text-ink-soft leading-relaxed">お探しの商品ページは、販売終了や掲載期間の終了により削除された可能性があります。今日のお買い得や、カテゴリ別のセール情報からお探しください。</p>
            <a href="{root}index.html" class="btn btn-main inline-block mt-5 font-bold px-5 py-3 rounded-full">今日のお買い得を見る →</a>
        </section>
        <section class="card p-5 md:p-7">
            <h2 class="text-lg md:text-xl font-extrabold text-ink">カテゴリから探す</h2>
            <div class="mt-4">{category_links_html(groups, root)}</div>
            <p class="mt-5 font-bold"><a href="{root}drops.html" class="text-orange-600 hover:underline underline-offset-2">値下がりした商品の一覧 ›</a></p>
        </section>
    </main>
{footer_html(root)}"""


def render_sale_page(guide, groups, top_deals):
    root = "../"
    page_url = f"{SITE_URL}sale/{guide['slug']}.html"
    year, name, label = guide["year"], guide["name"], guide_label(guide)
    title = f"{label}はいつから？ガジェットの狙い目と準備｜{SITE_NAME}"
    when = "・".join(f"{k} {v}" for k, v in guide["dates"]) if guide["dates"] else "日程は未発表"
    description = (f"{label}の開催日程（{when}）と、ガジェット・家電の狙い目カテゴリ、ポイントアップのエントリーなど事前準備をまとめました。")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": label, "item": page_url}]},
        {"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in guide["faq"]]},
    ]}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    row = lambda k, v: f'<tr class="border-t border-orange-100"><th class="py-2.5 pr-3 text-left font-bold whitespace-nowrap">{html.escape(k)}</th><td class="py-2.5">{html.escape(v)}</td></tr>'
    date_rows = "".join(row(f"{year}年 {k}", v) for k, v in guide["dates"]) or row(f"{year}年", "未発表（発表され次第更新します）")
    date_rows += "".join(row(k, v) for k, v in guide["past"])
    prep = "".join(f'<li class="card p-4 md:p-5"><p class="font-extrabold text-ink">{n}. {html.escape(t)}</p><p class="text-[15px] text-ink-soft leading-relaxed mt-1.5">{html.escape(b)}</p></li>'
                   for n, (t, b) in enumerate(guide["prep"], 1))
    picks = "".join(
        f'<li><a href="{root}category/{c["slug"]}.html" class="block card card-hover p-4 font-bold text-ink">{html.escape(c["name"])}'
        f'<span class="block text-xs text-ink-soft font-normal mt-1">掲載{len(groups.get(c["slug"], []))}件・価格の記録つき</span></a></li>'
        for c in CATEGORIES if groups.get(c["slug"]))
    faq = "".join(f'<details class="card p-4 md:p-5"><summary class="font-extrabold text-ink cursor-pointer">{html.escape(q)}</summary>'
                  f'<p class="text-[15px] text-ink-soft leading-relaxed mt-2">{html.escape(a)}</p></details>' for q, a in guide["faq"])
    today = "".join(f'<li><a href="{root}index.html#deal-{n}" class="hover:text-orange-600 hover:underline underline-offset-2">{html.escape(d["product_name"])}</a></li>'
                    for n, d in enumerate(top_deals[:4], 1))
    src_name, src_url = guide["source"]
    return f"""{head_html(title, description, page_url, root, "article", ld_json)}
    {simple_header_html(root)}
    <main class="max-w-3xl mx-auto px-4 pt-6 pb-16 space-y-6">
        <nav class="text-sm text-ink-soft" aria-label="パンくずリスト"><a href="{root}index.html" class="hover:text-orange-600 underline-offset-2 hover:underline">ホーム</a> › <span class="text-ink font-bold">{html.escape(label)}</span></nav>
        <section class="card p-5 md:p-7">
            <h1 class="text-2xl md:text-3xl font-extrabold text-ink leading-snug">{html.escape(label)}はいつから？ガジェットの狙い目と準備</h1>
            <p class="mt-3 text-ink-soft leading-relaxed">{html.escape(guide["lead"])}</p>
            <p class="mt-2 text-xs text-ink-soft">最終更新 {TODAY_STR}</p>
        </section>
        <section class="card p-5 md:p-7">
            <h2 class="text-lg md:text-xl font-extrabold text-ink">開催日程</h2>
            <table class="w-full text-[15px] mt-3"><tbody>{date_rows}</tbody></table>
            <p class="text-xs text-ink-soft mt-3">過去の日程の出典: <a href="{html.escape(src_url)}" target="_blank" rel="noopener" class="underline">{html.escape(src_name)}</a></p>
        </section>
        <section>
            <h2 class="text-lg md:text-xl font-extrabold text-ink mb-3">セール前にやっておくこと</h2>
            <ol class="space-y-3">{prep}</ol>
        </section>
        <section>
            <h2 class="text-lg md:text-xl font-extrabold text-ink mb-3">狙い目のカテゴリ</h2>
            <p class="text-[15px] text-ink-soft leading-relaxed mb-3">当サイトが記録している普段の価格と比べながら、セール価格をチェックできます。</p>
            <ul class="grid gap-3 md:grid-cols-2">{picks}</ul>
        </section>
        {f'<section class="card p-5 md:p-7"><h2 class="text-lg md:text-xl font-extrabold text-ink">今日のお買い得</h2><ul class="list-disc pl-5 mt-3 space-y-1 text-[15px] font-bold text-ink">{today}</ul></section>' if today else ""}
        <section>
            <h2 class="text-lg md:text-xl font-extrabold text-ink mb-3">よくある質問</h2>
            <div class="space-y-3">{faq}</div>
        </section>
    </main>
{footer_html(root)}"""


def upgrade_old_archives():
    """以前に生成した日別アーカイブにも noindex とビルド済みCSSを反映する（何度実行しても同じ結果）"""
    for name in os.listdir("public/archive"):
        if not name.endswith(".html"):
            continue
        path = os.path.join("public/archive", name)
        with open(path, encoding="utf-8") as f:
            page = f.read()
        new = re.sub(r'<script src="https://cdn\.tailwindcss\.com"></script>\s*<script>\s*tailwind\.config = .*?</script>',
                     f'<link rel="stylesheet" href="../css/site.css?v={CSS_VERSION}">', page, flags=re.S)
        if 'name="robots"' not in new:
            new = re.sub(r'(<link rel="canonical" href="[^"]*">)', r'\1<meta name="robots" content="noindex, follow">', new, count=1)
        if new != page:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)


def render_about_page():
    """運営者情報・お問い合わせ・プライバシーポリシー"""
    root = ""
    page_url = f"{SITE_URL}about.html"
    title = f"運営者情報・お問い合わせ｜{SITE_NAME}"
    description = f"{SITE_NAME}の運営者情報、お問い合わせ先、掲載内容の選び方、広告とプライバシーポリシーについて。"
    ld = {"@context": "https://schema.org", "@type": "AboutPage", "name": title, "url": page_url,
          "publisher": {"@type": "Person", "name": OPERATOR_NAME, "email": OPERATOR_EMAIL}}
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    section = lambda h, body: (f'<section class="card p-5 md:p-7"><h2 class="text-lg md:text-xl font-extrabold text-ink">{h}</h2>'
                               f'<div class="mt-3 space-y-3 text-[15px] text-ink leading-relaxed">{body}</div></section>')
    mail = html.escape(OPERATOR_EMAIL)
    return f"""{head_html(title, description, page_url, root, "website", ld_json)}
    {simple_header_html(root)}
    <main class="max-w-3xl mx-auto px-4 pt-6 pb-16 space-y-6">
        <nav class="text-sm text-ink-soft" aria-label="パンくずリスト"><a href="index.html" class="hover:text-orange-600 underline-offset-2 hover:underline">ホーム</a> › <span class="text-ink font-bold">運営者情報</span></nav>
        <section class="card p-5 md:p-7">
            <h1 class="text-2xl md:text-3xl font-extrabold text-ink leading-snug">運営者情報・お問い合わせ</h1>
            <table class="w-full text-[15px] mt-4"><tbody>
                <tr class="border-t border-orange-100"><th class="py-2.5 pr-4 text-left font-bold whitespace-nowrap">サイト名</th><td class="py-2.5">{html.escape(SITE_NAME)}</td></tr>
                <tr class="border-t border-orange-100"><th class="py-2.5 pr-4 text-left font-bold whitespace-nowrap">URL</th><td class="py-2.5">{html.escape(SITE_URL)}</td></tr>
                <tr class="border-t border-orange-100"><th class="py-2.5 pr-4 text-left font-bold whitespace-nowrap">運営者</th><td class="py-2.5">{html.escape(OPERATOR_NAME)}</td></tr>
                <tr class="border-t border-orange-100"><th class="py-2.5 pr-4 text-left font-bold whitespace-nowrap">お問い合わせ</th><td class="py-2.5"><a href="mailto:{mail}" class="text-orange-600 underline underline-offset-2 break-all">{mail}</a></td></tr>
            </tbody></table>
            <p class="text-sm text-ink-soft mt-4 leading-relaxed">掲載内容の誤り、商品情報の修正・削除のご依頼などは、上記のメールアドレスまでご連絡ください。</p>
        </section>
        {section("このサイトについて",
                 "<p>ガジェット好きの個人が運営している、セール・値下げ情報のまとめサイトです。Amazon・楽天市場などのセール情報や人気商品の公開情報をもとに、AIが毎日 朝・夕方の2回、注目の商品を選んで紹介しています。</p>"
                 "<p>紹介文と「AIのチェックポイント」はAIが自動で作成しています。楽天参考価格は、楽天市場の商品検索で取得した価格を記録したものです。一度紹介した商品は、その後も1日1回価格をチェックして記録しています。価格・在庫・ポイント倍率は変わるため、購入前に必ず各販売ページでご確認ください。</p>")}
        {section("広告について",
                 f"<p>当サイトは、Amazon.co.jpを宣伝しリンクすることによってサイトが紹介料を獲得できる手段を提供することを目的に設定されたアフィリエイトプログラムである、Amazonアソシエイト・プログラムの参加者です。また、{html.escape(AD_PARTNERS)}を利用しています。</p>"
                 "<p>商品リンクから購入された場合、当サイトが紹介料を受け取ることがあります。紹介料の有無によって、掲載順位や紹介内容を変えることはありません。</p>")}
        {section("プライバシーポリシー",
                 "<p>当サイトはアクセス解析に GoatCounter を使っています。GoatCounter は Cookie を使わず、個人を特定する情報を保存しない解析ツールです。どのリンクやボタンが何回押されたかも、同じ仕組みで数えています。</p>"
                 "<p>リンク先の Amazon・楽天市場などのサイトでは、各社が Cookie を使って紹介元を判別することがあります。取り扱いは各社のプライバシーポリシーをご確認ください。</p>"
                 "<p>お問い合わせでいただいたメールアドレスなどの情報は、返信のためにのみ使います。</p>")}
    </main>
{footer_html(root)}"""


def generate_site(deals):
    """トップページ・日別アーカイブ・sitemap.xml・robots.txt を生成する"""
    os.makedirs("public/archive", exist_ok=True)
    history = update_history(load_history(), deals)
    products = update_products(load_products(), deals)
    events = load_events()
    groups = products_by_category(products)

    # 値下がり欄は、今日のランキングに出ている商品を除いて並べる
    drops = price_drops(products, {product_id(d) for d in deals if not d.get("is_sample")})
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(render_page(deals, history, TODAY_DATE, "", SITE_URL, events, groups, drops))
    archive_url = f"{SITE_URL}archive/{TODAY_DATE}.html"
    with open(f"public/archive/{TODAY_DATE}.html", "w", encoding="utf-8") as f:
        f.write(render_page(deals, history, TODAY_DATE, "../", archive_url, events, groups))

    upgrade_old_archives()
    with open("public/about.html", "w", encoding="utf-8") as f:
        f.write(render_about_page())

    # 商品ページは毎回すべて作り直す（記録が消えた商品のページは削除する）
    os.makedirs("public/item", exist_ok=True)
    for name in os.listdir("public/item"):
        if name.endswith(".html") and name[:-5] not in products:
            os.remove(os.path.join("public/item", name))
    for pid, info in products.items():
        with open(f"public/item/{pid}.html", "w", encoding="utf-8") as f:
            f.write(render_item_page(pid, info))

    top_deals = [d for d in deals if d.get("slot") == "main"]
    os.makedirs("public/category", exist_ok=True)
    for cat in CATEGORIES:
        with open(f"public/category/{cat['slug']}.html", "w", encoding="utf-8") as f:
            f.write(render_category_page(cat, groups[cat["slug"]], groups, top_deals))
    page_drops = price_drops(products, days=DROP_PAGE_DAYS, limit=DROP_PAGE_SHOW)
    with open("public/drops.html", "w", encoding="utf-8") as f:
        f.write(render_drops_page(page_drops, groups))
    os.makedirs("public/share", exist_ok=True)
    with open("public/share/x.html", "w", encoding="utf-8") as f:
        f.write(render_x_share_page(deals))
    with open("public/404.html", "w", encoding="utf-8") as f:
        f.write(render_404_page(groups))
    with open("public/feed.xml", "w", encoding="utf-8") as f:
        f.write(render_feed(products))
    with open(f"public/{INDEXNOW_KEY}.txt", "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)
    os.makedirs("public/sale", exist_ok=True)
    for guide in SALE_GUIDES:
        with open(f"public/sale/{guide['slug']}.html", "w", encoding="utf-8") as f:
            f.write(render_sale_page(guide, groups, top_deals))

    # 日別アーカイブはトップとほぼ同じ内容なので、サイトマップに載せない（ページ側も noindex）
    urls = [f"  <url><loc>{SITE_URL}</loc><lastmod>{TODAY_DATE}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    urls.append(f"  <url><loc>{SITE_URL}about.html</loc><lastmod>{TODAY_DATE}</lastmod><priority>0.3</priority></url>")
    if len(page_drops) >= DROP_PAGE_MIN:
        urls.append(f"  <url><loc>{SITE_URL}drops.html</loc><lastmod>{TODAY_DATE}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>")
    for guide in SALE_GUIDES:
        urls.append(f"  <url><loc>{SITE_URL}sale/{guide['slug']}.html</loc><lastmod>{TODAY_DATE}</lastmod><priority>0.8</priority></url>")
    for cat in CATEGORIES:
        if len(groups[cat["slug"]]) >= CATEGORY_MIN_ITEMS:
            urls.append(f"  <url><loc>{SITE_URL}category/{cat['slug']}.html</loc><lastmod>{groups[cat['slug']][0][1]['last_seen'][:10]}</lastmod><priority>0.8</priority></url>")
    # 記録が少ない商品ページは中身が薄いので、サイトマップに載せない（ページ側も noindex）
    for pid, info in products.items():
        if not item_indexable(info):
            continue
        lastmod = max(str(info.get("last_seen", ""))[:10], str((info.get("records") or [{}])[-1].get("t", ""))[:10])
        urls.append(f"  <url><loc>{SITE_URL}item/{pid}.html</loc><lastmod>{lastmod}</lastmod><priority>0.7</priority></url>")
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

    lines = [f"📢 **【{TODAY_STR} 注目商品・SNS投稿ドラフト】**\n"]
    for deal in deals[:3]:
        amz_url, _ = build_affiliate_urls(deal["product_name"])
        lines.append(f"**■ {deal['product_name']}** (Score: {deal['score']})")
        lines.append(f"```\n{deal['sns_text']}\n👉 {amz_url}\n```")

    lines.append(f"\n👉 Xにワンタップで投稿: {SITE_URL}share/x.html")
    messages = ["\n".join(lines)[-1950:]]
    if NOW.hour >= 12:  # 夕方の更新時だけ、インサイト祭りの参加コメント案を別メッセージで届ける
        comment = matsuri_comment(deals)
        if comment:
            messages += ["🎪 **今日のインサイト祭り用コメント案**（下のメッセージを長押しでコピー→祭り投稿に返信）", comment]
    for content in messages:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
        except Exception as e:
            print(f"Discord通知エラー: {e}")


def alert_discord(message):
    """運営者に気づいてほしい異常をDiscordに知らせる（通知先が未設定なら何もしない）"""
    print(f"警告: {message}")
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": f"⚠️ **【{TODAY_STR} 自動更新の警告】**\n{message}"}, timeout=10)
    except Exception as e:
        print(f"Discord通知エラー: {e}")


def check_health(deals):
    """サンプルデータでの公開や、商品写真が1枚も取れない回を知らせる"""
    if any(d.get("is_sample") for d in deals):
        alert_discord("AI（Gemini・Groq）がどちらも使えず、サンプルデータでサイトを更新しました。"
                      "GitHub Actions のログで「APIエラー」の行を確認してください。")
    elif not any(d.get("image_url") for d in deals):
        alert_discord("商品写真が1枚も取得できませんでした。楽天APIの仕様変更やキーの期限切れの可能性があります。")


MATSURI_TEMPLATES = (
    "インサイト祭り参加させてください🙌\nガジェット・家電のお買い得情報を毎日朝と夕方にまとめて発信してます。\n今日の注目は「{name}」{price}\n一覧はプロフのリンクから見られます👀 フォロー返しします！",
    "祭り参加します✨\nAIで選んだガジェット特価を毎日2回お届けしているアカウントです。\n今日イチ推しは「{name}」{price}\nまとめはプロフのリンクにあります。仲良くしてください🙏 フォロバします！",
    "インサイト祭り失礼します📱\n買って損しないガジェット・家電の特価を毎日チェックしてます。\n今日のおすすめ→「{name}」{price}\n他の特価はプロフのリンクからどうぞ。フォローいただけたら必ずお返しします！",
    "参加させてください🙋\nセール中のガジェットを朝夕2回、AIと一緒に厳選して紹介してます。\n本日の目玉は「{name}」{price}\n全部プロフのリンクにまとめてます。フォロバ100%です、よろしくお願いします！",
)


def matsuri_comment(deals):
    """人が手で返信するための参加コメント案。毎日言い回しを変え、リンクは付けない"""
    deal = pick_sns_deal(deals)
    if not deal:
        return ""
    name = re.sub(r"【[^】]*】", "", deal["product_name"]).strip()
    if len(name) > 24:  # 単語の途中で切れないよう、24文字以内の最後の区切りで止める
        name = name[:24].rsplit(" ", 1)[0]
    price = f"（{deal['price_yen']:,}円）" if isinstance(deal.get("price_yen"), int) and deal["price_yen"] > 0 else ""
    return MATSURI_TEMPLATES[NOW.toordinal() % len(MATSURI_TEMPLATES)].format(name=name, price=price)


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
    """SNSに投稿する1件（目玉枠で、値下がり・最安記録の商品を優先し、その中でおすすめ度が最も高い商品）を選ぶ"""
    main = [d for d in deals if d["slot"] == "main" and not d.get("is_sample")]
    return max(main, key=lambda d: (bool(d.get("price_drop") or d.get("record_low")), d["score"])) if main else None


def sns_price_line(deal):
    """「楽天参考価格 ¥12,800（前回より¥1,200値下がり・当サイト記録で最安）」の1行。価格が無ければ空文字"""
    try:
        price = int(deal.get("price_yen") or 0)
    except (TypeError, ValueError):
        price = 0
    if not price:
        return ""
    notes = []
    if deal.get("price_drop"):
        notes.append(f"前回より¥{int(deal['price_drop']):,}値下がり")
    if deal.get("record_low"):
        notes.append("当サイト記録で最安")
    return f"💰 楽天参考価格 ¥{price:,}" + (f"（{'・'.join(notes)}）" if notes else "")


def deal_page_url(deal):
    """SNSから案内するページ。商品ページ（価格の記録つき）があればそこへ、無ければトップへ"""
    return SITE_URL + deal["item_page"] if deal.get("item_page") else SITE_URL


def sns_body(deal, limit):
    """【PR】と価格の1行を先頭に付けた紹介文。AIの文が無ければ商品名とキャッチコピーで作る"""
    text = deal.get("sns_text") or f"{deal['product_name']}\n{deal.get('catch_copy', '')}\n#ガジェット #セール"
    text = text.replace("【PR】", "").strip()
    line = sns_price_line(deal)
    return ("【PR】" + (line + "\n" if line else "") + text)[:limit]


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
        "text": f"▼価格の推移・現在の価格はこちら（毎日 朝・夕方に自動更新）\n{deal_page_url(deal)}",
        "reply": {"in_reply_to_tweet_id": tweet_id},
    }
    res = requests.post("https://api.x.com/2/tweets", auth=auth, json=reply, timeout=30)
    res.raise_for_status()
    print("Xに投稿しました（画像" + ("あり" if "media" in payload else "なし") + "・返信でURL）。")


def threads_error(e):
    """Metaのエラー本文から code と message だけを取り出す（トークンは含まれない）"""
    try:
        err = e.response.json().get("error", {})
        msg = str(err.get("error_user_msg") or err.get("message", ""))[:160]
        return f"{e.response.status_code} code={err.get('code')} sub={err.get('error_subcode')} {msg}"
    except Exception:
        return str(safe_status(e))


def is_permission_error(e):
    """Metaの権限エラー（code 10 / 200〜299）かどうか"""
    try:
        code = e.response.json().get("error", {}).get("code")
    except Exception:
        return False
    return code == 10 or (isinstance(code, int) and 200 <= code <= 299)


def threads_reply_link():
    """1コメにURLを付ける形で投稿するか。返信の権限が無いと分かった後は False（本文にURLを入れる形に戻す）"""
    try:
        with open(THREADS_STATE_PATH, encoding="utf-8") as f:
            return json.load(f).get("reply_link", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def threads_publish(base, fields):
    """コンテナを作って公開し、公開した投稿のIDを返す"""
    res = requests.post(f"{base}/threads", data={**fields, "access_token": THREADS_ACCESS_TOKEN}, timeout=30)
    res.raise_for_status()
    creation_id = res.json()["id"]
    time.sleep(10)  # コンテナの生成完了を待つ
    res = requests.post(f"{base}/threads_publish", data={"creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN}, timeout=30)
    res.raise_for_status()
    return res.json()["id"]


def post_to_threads(deal):
    """本文（画像付き・リンクなし・トピック1つ）を出し、最初の自己返信（1コメ）でサイトURLへ誘導する。
    本文にリンクがあるとおすすめに載りにくいため。返信の権限が無いと分かったら、次回から本文にURLを入れる形へ自動で戻す"""
    user_id = THREADS_USER_ID
    if not user_id:  # ユーザーID未登録ならトークンから自分のIDを調べる
        res = requests.get("https://graph.threads.net/v1.0/me", params={"fields": "id", "access_token": THREADS_ACCESS_TOKEN}, timeout=15)
        if not res.ok:
            raise RuntimeError("ユーザーID取得失敗 " + threads_error(requests.HTTPError(response=res)))
        user_id = res.json()["id"]
    base = f"https://graph.threads.net/v1.0/{user_id}"
    reply_link = threads_reply_link()
    # ハッシュタグは外す（本文中のタグもトピック扱いになり、1投稿1トピックの指定とぶつかるため）
    text = re.sub(r"(?:\s*[#＃][^\s#＃]+)+\s*$", "", sns_body(deal, 400))  # 末尾のタグはまとめて削除
    text = re.sub(r"[#＃](?=\S)", "", text).strip()  # 文中のタグは # だけ外して言葉は残す
    if not reply_link:
        text += f"\n\n▼価格の推移・現在の価格はこちら\n{deal_page_url(deal)}"
    attempts = []
    if deal.get("image_url"):
        attempts.append({"media_type": "IMAGE", "image_url": deal["image_url"], "topic_tag": THREADS_TOPIC})
    attempts += [{"media_type": "TEXT", "topic_tag": THREADS_TOPIC}, {"media_type": "TEXT"}]  # 最後はトピックも外して再試行
    post_id = ""
    for extra in attempts:
        label = extra["media_type"] + ("" if "topic_tag" in extra else "・トピックなし")
        try:
            post_id = threads_publish(base, {"text": text, **extra})
            print(f"Threadsに投稿しました（{label}）。")
            break
        except requests.HTTPError as e:
            print(f"Threads {label} 投稿エラー（{threads_error(e)}）")
    if not post_id:
        raise RuntimeError("Threads投稿に失敗しました")
    if not reply_link:
        return
    time.sleep(5)  # 公開した投稿に返信できるようになるのを待つ
    reply = f"👇 価格の推移・現在の価格はこちら（毎日 朝・夕方に自動更新）\n{deal_page_url(deal)}"
    try:
        threads_publish(base, {"media_type": "TEXT", "text": reply, "reply_to_id": post_id})
        print("Threadsの1コメにURLを付けました。")
    except requests.HTTPError as e:
        print(f"Threads 1コメ投稿エラー（{threads_error(e)}）")
        if is_permission_error(e):
            with open(THREADS_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump({"reply_link": False, "since": TODAY_STR, "reason": threads_error(e)}, f, ensure_ascii=False, indent=1)
            print(f"返信の権限が無いため、次回からURLを本文に入れる形に戻します（{THREADS_STATE_PATH}）。")


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


if __name__ == "__main__" and "--indexnow" in sys.argv:
    ping_indexnow()
elif __name__ == "__main__":
    print("1. 候補データを取得中...")
    raw_candidates = fetch_candidates()
    print(f"   取得件数: {len(raw_candidates)}件")

    print("2. AIで買い時判定＆テキスト生成中...")
    selected_deals = select_deals(raw_candidates)
    print(f"   掲載件数: {len(selected_deals)}件（ついで買い枠 {sum(d['slot'] == 'impulse' for d in selected_deals)}件、写真付き {sum(bool(d['image_url']) for d in selected_deals)}件）")

    print("3. Webサイト更新＆通知送信中...")
    attach_yahoo_items(selected_deals)
    seed_staples()
    track_prices({product_id(d) for d in selected_deals if not d.get("is_sample")})
    generate_site(selected_deals)
    notify_discord(selected_deals)
    check_health(selected_deals)

    print("4. SNS自動投稿中...")
    post_to_sns(selected_deals)
    print("完了しました！")
