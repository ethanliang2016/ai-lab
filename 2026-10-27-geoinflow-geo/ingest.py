# ingest.py — 部署后注入：登录 → 建站 → 导入内容清单 → 导入合成日志 → 发送 AI 引荐事件
import json, urllib.request, time, sys, os

BASE = "http://127.0.0.1:3002"
HERE = os.path.dirname(os.path.abspath(__file__))
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def req(method, path, body=None, token=None, ua=None, raw=False):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("User-Agent", ua or BROWSER_UA)
    if token: r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(r, data=data, timeout=30) as resp:
            txt = resp.read().decode()
            return resp.status, (txt if raw else json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]

def wait_up():
    for i in range(60):
        try:
            with urllib.request.urlopen(BASE + "/api/heartbeat", timeout=5) as r:
                if r.status == 200: print("[ok] heartbeat"); return
        except Exception: pass
        time.sleep(5)
    sys.exit("[fail] app not up")

wait_up()
s, b = req("POST", "/api/auth/login", {"username": "admin", "password": "liekan"})
print("[login]", s, str(b)[:120])
token = b.get("token") if isinstance(b, dict) else None
if not token: sys.exit("login failed")

s, b = req("POST", "/api/websites", {"name": "GEO实测站", "domain": "geo-test.example"}, token)
print("[website]", s, str(b)[:200])
wid = b.get("id") or b.get("websiteId")
if not wid: sys.exit("website create failed")
print("[website id]", wid)

catalog = open(os.path.join(HERE, "catalog.csv"), encoding="utf-8").read()
s, b = req("PUT", f"/api/liekan/websites/{wid}/catalog", {"format": "csv", "content": catalog}, token)
print("[catalog]", s, str(b)[:200])

log = open(os.path.join(HERE, "access.log"), encoding="utf-8").read()
s, b = req("POST", f"/api/liekan/websites/{wid}/logs/import", {"format": "combined", "content": log}, token)
print("[log import]", s, str(b)[:300])

events = json.load(open(os.path.join(HERE, "events.json"), encoding="utf-8"))
ok = 0
for ev in events:
    s, b = req("POST", "/api/send", {"type": "event", "payload": {
        "website": wid, "hostname": "geo-test.example", "language": "zh-CN",
        "referrer": ev["referrer"], "url": ev["url"], "screen": "1920x1080",
        "title": "GEO Test Page"}}, ua=BROWSER_UA)
    ok += (s == 200)
    print(f"[event] {ev['label']}: {s}")
print(f"[events] {ok}/{len(events)} accepted")
print("WID=" + wid)
