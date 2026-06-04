import feedparser
import json
import datetime

SOURCES = [
    {"id": "gamelook", "name": "GameLook", "color": "#e74c3c", "url": "https://www.gamelook.com.cn/feed"},
    {"id": "bahamut", "name": "巴哈姆特 GNN", "color": "#8e44ad", "url": "https://gnn.gamer.com.tw/rss.xml"},
    {"id": "pocketgamer", "name": "Pocket Gamer Biz", "color": "#2980b9", "url": "https://www.pocketgamer.biz/feed/"},
    {"id": "dof", "name": "Deconstructor of Fun", "color": "#27ae60", "url": "https://www.deconstructoroffun.com/blog?format=rss"},
    {"id": "naavik", "name": "Naavik", "color": "#d35400", "url": "https://naavik.co/feed/"},
    {"id": "shouyoux", "name": "手遊那點事", "color": "#16a085", "url": "http://www.shouyoux.com/feed"},
]

def strip_tags(text):
    import re
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text).strip()

results = []

for source in SOURCES:
    try:
        feed = feedparser.parse(source["url"])
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
