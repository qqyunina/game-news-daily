import feedparser
import json
import datetime
import urllib.request

SOURCES = [
    {"id": "gamelook", "name": "GameLook", "color": "#e74c3c", "url": "https://rsshub.app/gamelook/news"},
    {"id": "bahamut", "name": "巴哈姆特 GNN", "color": "#8e44ad", "url": "https://gnn.gamer.com.tw/rss.xml"},
    {"id": "pocketgamer", "name": "Pocket Gamer Biz", "color": "#2980b9", "url": "https://www.pocketgamer.biz/feed/"},
    {"id": "dof", "name": "Deconstructor of Fun", "color": "#27ae60", "url": "https://www.deconstructoroffun.com/blog?format=rss"},
    {"id": "naavik", "name": "Naavik", "color": "#d35400", "url": "https://naavik.co/feed/"},
    {"id": "shouyoux", "name": "手遊那點事", "color": "#16a085", "url": "https://rsshub.app/shouyoux/news"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
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
        feed = feedparser.parse(content)
        return feed
    except Exception:
        return feedparser.parse(url)

results = []

for source in SOURCES:
    try:
        feed = fetch_feed(source["url"])
        items = []
        for entry in feed.entries[:8]:
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

output = {
    "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "sources": results,
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("data.json saved.")
