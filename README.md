# AI实测代码仓库（ai-lab）

集中存放各篇AI情报/实测文章的配套脚本与复现工程，按篇归档、按篇打tag，方便管理与回溯。

## tag约定

每篇文章一个独立tag，格式：`YYYY-MM-DD-<slug>`，例如本文：

- `2026-10-10-openai-agents-api`

切到某篇实测：`git checkout <tag>` 或 `git clone --branch <tag> <repo>`。

## 篇目索引

| 日期 | 文章 | 目录 | tag |
|------|------|------|-----|
| 2026-10-10 | OpenAI 把 Agent 基建做成了 API：MCP 正式入编 | `2026-10-10-openai-agents-api/docker/` | `2026-10-10-openai-agents-api` |

## 目录结构

```
ai-lab/
├── README.md                       # 本文件
├── .gitignore                      # 排除 **/.env
└── <YYYY-MM-DD-slug>/
    └── <工程目录>/                  # 每篇实测的具体工程
```

## 配置说明

每篇工程的key均通过`.env`注入（由`.env.example`复制），`.env`已被.gitignore排除，绝不入库。
