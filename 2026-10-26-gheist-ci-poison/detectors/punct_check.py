import re
import sys

path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines()
in_code = False
issues = 0
for i, l in enumerate(lines, 1):
    if l.strip().startswith("```"):
        in_code = not in_code
        continue
    if in_code:
        continue
    t = re.sub(r"https?://\S+", "", l)
    t = re.sub(r"`[^`]+`", "", t)
    t = re.sub(r"\([^()]*[A-Za-z0-9][^()]*\)", "", t)  # 英文括注豁免
    for ch in [",", ";", "?", "!"]:
        if ch in t and re.search(r"[一-鿿]", t):
            print(i, repr(ch), t[:70])
            issues += 1
            break
print("issues:", issues)
