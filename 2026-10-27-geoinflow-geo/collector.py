# collector.py — 拉取 GEOInflow 分析结果
import json, urllib.request, time, os, datetime

BASE = "http://127.0.0.1:3002"
HERE = os.path.dirname(os.path.abspath(__file__))
WID = "72ea879b-bff8-4e6a-a896-d2cf99955850"

def req(method, path, body=None, token=None):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token: r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(r, data=data, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"_error": e.read().decode()[:300]}

s, b = req("POST", "/api/auth/login", {"username": "admin", "password": "liekan"})
token = b["token"]
print("[login]", s)

now = int(time.time() * 1000)
day0 = int(datetime.datetime(2026, 10, 26, 16, 0, 0).timestamp() * 1000)  # UTC=北京27日0点
out = {}

for name, path in [
    ("recognition", f"/api/liekan/websites/{WID}/crawler-recognition"),
    ("analysis", f"/api/liekan/websites/{WID}/crawler-analysis?startAt={day0}&endAt={now}"),
    ("catalog", f"/api/liekan/websites/{WID}/catalog"),
    ("report", f"/api/liekan/websites/{WID}/report?startAt={day0}&endAt={now}"),
    ("analytics", f"/api/liekan/websites/{WID}/analytics?startAt={day0}&endAt={now}"),
]:
    s, b = req("GET", path, token=token)
    out[name] = {"status": s, "body": b}
    print(f"[{name}] {s} len={len(json.dumps(b))}")

with open(os.path.join(HERE, "results", "api_results.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("saved api_results.json")
