import feedparser
import json
import datetime
import urllib.request
import os
import urllib.parse

SOURCES = [
    {"id": "bahamut", "name": "巴哈姆特 GNN", "color": "#8e44ad", "url": "https://gnn.gamer.com.tw/rss.xml"},
    {"id": "pocketgamer", "name": "Pocket Gamer Biz", "color": "#2980b9", "url": "https://www.pocketgamer.biz/feed/"},
    {"id": "dof", "name": "Deconstructor of Fun", "color": "#27ae60", "url": "https://www.deconstructoroffun.com/blog?format=rss"},
    {"id": "naavik", "name": "Naavik", "color": "#d35400", "url": "https://naavik.co/feed/"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

def strip_tags(text):
    import re
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()

def fetch_feed(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read()
        return feedparser.parse(content)
    except Exception:
        return feedparser.parse(url)

def call_claude(prompt, api_key):
    import json as _json
    data = _json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        result = _json.loads(res.read())
    return result["content"][0]["text"]

# 抓取 RSS
results = []
for source in SOURCES:
    try:
        feed = fetch_feed(source["url"])
        items = []
        for entry in feed.entries[:3]:
            pub = entry.get("published", entry.get("updated", ""))
            desc = strip_tags(entry.get("summary", entry.get("content", [{}])[0].get("value", "")))[:200]
            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "date": pub,
                "desc": desc,
            })
        results.append({"source": source, "items": items, "ok": True})
        print(f"OK  {source['name']}: {len(items)} articles")
    except Exception as e:
        results.append({"source": source, "items": [], "ok": False, "error": str(e)})
        print(f"ERR {source['name']}: {e}")

# 用 Claude 生成今日學習重點
insights = []
api_key = os.environ.get("ANTHROPIC_API_KEY", "")

if api_key:
    all_titles = []
    for r in results:
        if r["ok"]:
            for item in r["items"]:
                if item["title"]:
                    all_titles.append(f"- [{r['source']['name']}] {item['title']}")

    if all_titles:
        titles_text = "\n".join(all_titles)
        prompt = f"""你是一位休閒手遊產品經理助理。以下是今天的休閒遊戲市場新聞標題：

{titles_text}

請根據這些新聞，用繁體中文整理出 4~5 條「今天可以學習到的休閒遊戲市場新知」。
每條用一句話說明重點，要有洞察、實用，幫助產品經理了解市場趨勢。
直接輸出條列內容，每條換行，不需要編號或前綴符號，不需要其他說明文字。"""

        try:
            response = call_claude(prompt, api_key)
            insights = [line.strip() for line in response.strip().split("\n") if line.strip()]
            print(f"AI insights generated: {len(insights)} points")
        except Exception as e:
            print(f"Claude API error: {e}")
            insights = []

output = {
    "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sources": results,
    "insights": insights,
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("data.json saved.")
