#!/usr/bin/env python3
"""E2: 模拟 GitHub Actions 日志脱敏机制
GitHub 文档行为：对日志中出现的 secret 值做逐字替换（***）。
本脚本演示：明文 secret 会被遮蔽，base32/base64 编码后原样通过。
"""
import base64
import sys

SECRETS = {
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMIFAKEKEYexample0000000",
    "NPM_TOKEN": "npm_FAKEtoken00000000000000000000000000",
    "DATABASE_URL": "postgres://user:fakepass@db.internal:5432/prod",
    "ANTHROPIC_API_KEY": "sk-ant-fake00000000000000000000000000",
}


def github_mask(log: str, secrets: dict) -> str:
    masked = log
    for value in secrets.values():
        masked = masked.replace(value, "***")
    return masked


def main():
    leak_plain = "\n".join(f"{k}={v}" for k, v in SECRETS.items())
    leak_b32 = base64.b32encode(
        "\n".join(f"{k}={v}" for k, v in SECRETS.items()).encode()
    ).decode()
    leak_b64 = base64.b64encode(leak_plain.encode()).decode()

    for label, payload in [("明文", leak_plain), ("base32", leak_b32), ("base64", leak_b64)]:
        masked = github_mask(payload, SECRETS)
        leaked = sum(1 for v in SECRETS.values() if v in masked)
        print(f"[{label}] 脱敏后仍可见的 secret 明文数: {leaked}/{len(SECRETS)}")
        print(f"  脱敏后前 80 字符: {masked[:80]!r}")

    # 反向验证：base32 团块可无损还原
    recovered = base64.b32decode(leak_b32.encode()).decode()
    assert all(v in recovered for v in SECRETS.values())
    print("[还原] base32 团块解码后包含全部 secret: True")


if __name__ == "__main__":
    sys.exit(main())
