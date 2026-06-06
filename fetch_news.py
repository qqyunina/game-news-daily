#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================
#  Morning Briefing — 雲端抓取腳本 (GitHub Actions 用)
#  只產生「公開」內容：新聞 + 市場新知 + 優化方向 + 排行榜 + 存檔。
#  不含任何遊戲機密 / 不產生機密建議（那部分只在本機腳本做）。
#  注意：GitHub 伺服器在美國，連不到 GameLook(中國站)，故雲端不含 GameLook。
# =============================================================
import os, re, json, datetime, urllib.request, urllib.error
import xml.etree.ElementTree as ET

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = "claude-sonnet-4-5-20250929"
REPO = os.path.dirname(os.path.abspath(__file__))

# 雲端不含 GameLook（美國 IP 會被擋）
SOURCES = [
    {"id": "bahamut",     "name": "巴哈姆特 GNN",         "color": "#8e44ad", "url": "https://gnn.gamer.com.tw/rss.xml"},
    {"id": "pocketgamer", "name": "Pocket Gamer Biz",     "color": "#2980b9", "url": "https://www.pocketgamer.biz/rss/"},
    {"id": "mobilegamer", "name": "MobileGamer.biz",      "color": "#16a085", "url": "https://mobilegamer.biz/feed/"},
    {"id": "dof",         "name": "Deconstructor of Fun", "color": "#27ae60", "url": "https://www.deconstructoroffun.com/blog?format=rss"},
    {"id": "naavik",      "name": "Naavik",               "color": "#d35400", "url": "https://naavik.co/feed/"},
]
ENGLISH_IDS = {"pocketgamer", "mobilegamer", "dof", "naavik"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}


def strip_html(t):
    if not t:
        return ""
    t = re.sub(r"<[^>]+>", "", t)
    for a, b in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&#8217;", "'"), ("&#8230;", "..."), ("&quot;", '"')]:
        t = t.replace(a, b)
    return t.strip()


def fetch_xml(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        raw = r.read()
    i = raw.find(b"<")
    if i > 0:
        raw = raw[i:]
    return ET.fromstring(raw)   # 以原始 bytes 解析，尊重 XML 編碼宣告（修正中文亂碼）


def call_claude(prompt, max_tokens=1024):
    if not API_KEY:
        raise RuntimeError("no api key")
    body = json.dumps({
        "model": MODEL, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["content"][0]["text"]


def node_text(item, tag):
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else ""


# ---------- 抓 RSS（每來源先抓 4 篇供挑選）----------
results = []
for src in SOURCES:
    try:
        root = fetch_xml(src["url"])
        items = []
        for it in root.iter("item"):
            if len(items) >= 4:
                break
            desc = strip_html(node_text(it, "description"))[:180]
            items.append({"title": node_text(it, "title"), "title_zh": "",
                          "link": node_text(it, "link"), "date": node_text(it, "pubDate"), "desc": desc})
        results.append({"source": src, "items": items, "ok": True})
        print(f"OK  {src['name']}: {len(items)}")
    except Exception as e:
        results.append({"source": src, "items": [], "ok": False, "error": str(e)})
        print(f"ERR {src['name']}: {e}")


# ---------- 去重複：只保留「今天之前沒出現過」的文章（週刊文章不會連日重複）----------
SEEN_PATH = os.path.join(REPO, "archive", "seen.json")
TODAY_ISO = datetime.date.today().isoformat()
seen = {}
try:
    if os.path.exists(SEEN_PATH):
        seen = json.load(open(SEEN_PATH, encoding="utf-8")).get("links", {})
except Exception:
    seen = {}

def is_fresh(it):
    k = it.get("link") or it.get("title")
    if not k:
        return True
    d = seen.get(k)
    return (d is None) or (d == TODAY_ISO)   # 沒看過、或今天才首次看到 → 算新

for r in results:
    if r["ok"]:
        r["items"] = [it for it in r["items"] if is_fresh(it)]


# ---------- 每來源挑最有價值的 2 篇（AI；失敗取前 2）----------
def trim_first_two():
    for r in results:
        if r["ok"] and r["items"]:
            r["items"] = r["items"][:2]

try:
    blocks = []
    for r in results:
        if r["ok"] and r["items"]:
            lines = "\n".join(f"  [{i}] {it['title']}" for i, it in enumerate(r["items"]))
            blocks.append(f"來源 {r['source']['id']}：\n{lines}")
    if blocks and API_KEY:
        sp = ("以下每個來源有數則新聞。請為每個來源挑出對「休閒手遊產品經理」最有價值、最值得讀的 2 則。\n"
              "只輸出 JSON 物件，格式為 {\"來源id\": [索引, 索引], ...}，索引從 0 開始，每個來源剛好 2 個。不要任何其他文字。\n\n"
              + "\n\n".join(blocks))
        m = re.search(r"\{.*\}", call_claude(sp, 600), re.S)
        sel = json.loads(m.group(0)) if m else {}
        for r in results:
            if r["ok"] and r["items"]:
                idxs = sel.get(r["source"]["id"])
                if idxs:
                    keep = [r["items"][i] for i in idxs if 0 <= i < len(r["items"])]
                    r["items"] = (keep or r["items"])[:2]
                else:
                    r["items"] = r["items"][:2]
        print("已挑選每來源 2 篇")
    else:
        trim_first_two()
except Exception as e:
    print(f"挑選失敗，取前 2：{e}")
    trim_first_two()


# ---------- 翻譯英文標題為繁中 ----------
try:
    to_tr = [it for r in results if r["ok"] and r["source"]["id"] in ENGLISH_IDS for it in r["items"] if it["title"]]
    if to_tr and API_KEY:
        lines = "\n".join(f"{i+1}. {it['title']}" for i, it in enumerate(to_tr))
        tp = ("請把以下英文遊戲產業新聞標題翻成自然、精準的繁體中文（台灣用語），保留遊戲名、公司名與數字。\n"
              "每行對應一個編號，輸出格式固定為「編號. 中文標題」，不要其他文字。\n\n" + lines)
        for line in call_claude(tp, 1500).strip().split("\n"):
            mm = re.match(r"^\s*(\d+)[\.\、]\s*(.+)$", line)
            if mm:
                k = int(mm.group(1)) - 1
                if 0 <= k < len(to_tr):
                    to_tr[k]["title_zh"] = mm.group(2).strip()
        print(f"標題翻譯：{len(to_tr)}")
except Exception as e:
    print(f"翻譯失敗：{e}")


titles_text = "\n".join(f"- [{r['source']['name']}] {it['title']}"
                        for r in results if r["ok"] for it in r["items"] if it["title"])

# ---------- (1) 市場新知（精簡、白話、給外行人）----------
insights = []
try:
    p1 = f"""你是一位休閒手遊產品經理助理。以下是今天的休閒遊戲市場新聞標題：

{titles_text}

請根據這些新聞，用繁體中文整理出 4~5 條「今天可以學習到的休閒遊戲市場新知」。
讀者可能對產業完全沒概念，要讓他看完就學到東西。每條：先講具體發生什麼事（含數字/公司/產品名，公司名後可用括號簡介），重點放在啟發性洞察（成功的公司/遊戲有什麼共同特色、為什麼能贏），不要解釋基本玩法。
請精簡：每條只寫一句話，用破折號「——」分隔「事實」與「啟示」，盡量 60 字內。把最重要的放第一行。
直接輸出條列，每條一行，不要編號或符號前綴，不要其他說明文字。"""
    insights = [re.sub(r"^[\-\*\d\.\s]+", "", x).strip() for x in call_claude(p1, 1024).strip().split("\n")]
    insights = [x for x in insights if x]
    print(f"市場新知：{len(insights)}")
except Exception as e:
    print(f"新知失敗：{e}")

# ---------- (2) 優化方向（公開、不含機密、要有例子）----------
opportunities = []
try:
    p3 = f"""你是資深休閒手遊產品顧問。以下是這款遊戲的公開定位，以及今天的市場新聞標題。

【遊戲定位】貓咪造咖：經營類休閒手遊，主力客群 18-44 歲女性，題材為療癒系貓咪咖啡廳。

【今日市場新聞】
{titles_text}

請結合今日市場趨勢，提出 3~4 條「我們可以優化的方向」。這份會公開顯示在網頁上，因此：
- 只談大方向與市場連結，務必不要提到任何內部數值、定價、變現細節、程式架構或系統內部名稱。
- 說明要具體：用「例如：…」帶出 1~2 個明確做法範例。
- 每條格式固定為「標題｜說明（含例如）」，用全形直線「｜」分隔。
- 用繁體中文，直接輸出 3~4 條，每條一行，不要編號前綴，不要其他文字。"""
    for line in call_claude(p3, 1200).strip().split("\n"):
        line = re.sub(r"^[\-\*\d\.\s]+", "", line).strip()
        if not line:
            continue
        parts = line.split("｜", 1)
        if len(parts) == 2:
            opportunities.append({"title": parts[0].strip(), "detail": parts[1].strip()})
        else:
            opportunities.append({"title": line, "detail": ""})
    print(f"優化方向：{len(opportunities)}")
except Exception as e:
    print(f"優化方向失敗：{e}")


# ---------- (3) iOS 台灣 休閒類排行榜 + 貓咪造咖名次 ----------
def get_chart(url, cid, title):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        feed = json.loads(r.read())["feed"]
    items, self_row, rank = [], None, 1
    for e in feed.get("entry", []):
        name = e["im:name"]["label"]
        icon = e.get("im:image", [{}])[-1].get("label", "")
        link = e.get("id", {}).get("label", "")
        artist = e.get("im:artist", {}).get("label", "")
        row = {"rank": rank, "name": name, "artist": artist, "link": link, "icon": icon}
        if rank <= 10:
            items.append(row)
        if "貓咪造咖" in name:
            self_row = {"rank": rank, "name": "貓咪造咖", "artist": artist, "link": link, "icon": icon}
        rank += 1
    return {"id": cid, "title": title, "items": items, "self": self_row}

rankings = []
try:
    rankings = [
        get_chart("https://itunes.apple.com/tw/rss/topgrossingapplications/limit=100/genre=7003/json", "ios_tw_grossing", "iOS 台灣 · 休閒類暢銷榜"),
        get_chart("https://itunes.apple.com/tw/rss/topfreeapplications/limit=100/genre=7003/json", "ios_tw_free", "iOS 台灣 · 休閒類免費榜"),
    ]
    print(f"排行榜：{len(rankings)}")
except Exception as e:
    print(f"排行榜失敗：{e}")


# ---------- 寫出 data.json + 存檔 ----------
output = {
    "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sources": results,
    "insights": insights,
    "opportunities": opportunities,
    "rankings": rankings,
}
js = json.dumps(output, ensure_ascii=False, indent=2)
with open(os.path.join(REPO, "data.json"), "w", encoding="utf-8") as f:
    f.write(js)
print("data.json 已寫入")

arc = os.path.join(REPO, "archive")
os.makedirs(arc, exist_ok=True)

# 記錄今天顯示過的文章（供之後去重）；修剪 120 天前的記錄
for r in results:
    if r["ok"]:
        for it in r["items"]:
            k = it.get("link") or it.get("title")
            if k and k not in seen:
                seen[k] = TODAY_ISO
cutoff = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()
seen = {k: v for k, v in seen.items() if v >= cutoff}
with open(SEEN_PATH, "w", encoding="utf-8") as f:
    json.dump({"links": seen}, f, ensure_ascii=False)
print(f"去重記錄：{len(seen)} 筆")
today = datetime.date.today().isoformat()
with open(os.path.join(arc, f"{today}.json"), "w", encoding="utf-8") as f:
    f.write(js)
idx_path = os.path.join(arc, "index.json")
dates = []
if os.path.exists(idx_path):
    try:
        dates = json.load(open(idx_path, encoding="utf-8")).get("dates", [])
    except Exception:
        dates = []
if today not in dates:
    dates.append(today)
dates = sorted(dates)
with open(idx_path, "w", encoding="utf-8") as f:
    json.dump({"dates": dates}, f, ensure_ascii=False)
print(f"存檔完成：{today}（共 {len(dates)} 天）")
