import json, base64, re, subprocess, sys

def api(path):
    out = subprocess.run(['curl.exe','-s','https://api.github.com/'+path,'-H','Accept: application/vnd.github+json'],capture_output=True).stdout
    return json.loads(out)

def show_file(repo, name):
    d = api(f'repos/{repo}/contents/{name}')
    if 'content' not in d: return None, None
    raw = base64.b64decode(d['content'])
    return raw, d['sha']

repos = ['crsr-tools/Cursor-AI-Download','cld-tools/Claude-Desktop-Download','hex-tools/hexstrike-ai-pc']
print('===== index.html 对比 =====')
for r in repos:
    raw, sha = show_file(r,'index.html')
    if raw:
        txt = raw.decode('utf-8','ignore')
        hexes = re.findall(r"\\x([0-9a-fA-F]{2})", txt)
        fcc = re.findall(r"fromCharCode\((\d+)\)", txt)
        decoded = ''.join(chr(int(h,16)) for h in hexes) + ' | fromCharCode: ' + ''.join(chr(int(n)) for n in fcc)
        print(r, '| size', len(raw), '| sha', sha[:12])
        print('  decoded chars:', decoded)

print()
print('===== README 前两仓对比(前 800 字符) =====')
for r in repos[:2]:
    raw, sha = show_file(r, 'README.md')
    if raw:
        print('---', r, '| size', len(raw), '| sha', sha[:12])
        print(raw.decode('utf-8','ignore')[:800])
        print()

print('===== 图片 sha 对比 =====')
for r, img in [(repos[0],'cursor.jpg'),(repos[1],'claude-desktop-uitgelegd-og.jpg')]:
    raw, sha = show_file(r, img)
    print(r, img, '| size', len(raw) if raw else None, '| blob sha', sha)

print()
print('===== stargazers 抽样(crsr-tools, 前 20) =====')
sg = api('repos/crsr-tools/Cursor-AI-Download/stargazers?per_page=20')
for u in sg:
    ud = api('users/'+u['login'])
    print(u['login'], '| created:', ud.get('created_at','?')[:10], '| followers:', ud.get('followers'), '| repos:', ud.get('public_repos'))
