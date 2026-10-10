# OpenAI Agents SDK 实测（0.23.1）· 硅基流动DeepSeek-V3

> 本篇工程位于统一仓库 [ai-lab](https://github.com/ethanliang/ai-lab) 的 `2026-10-10-openai-agents-api/docker/` 子目录，对应 tag `2026-10-10-openai-agents-api`。

配套《OpenAI 把 Agent 基建做成了 API：MCP 正式入编》一文的最小可复现工程。在 Docker 中跑通 openai-agents 0.23.1 的三组测试：基础 Agent+工具调用、多 Agent Handoffs、本地 MCP Server 接入。

## 环境

- Docker / Docker Compose
- openai-agents 0.23.1
- mcp 2.3.0
- 硅基流动DeepSeek-V3（OpenAI 兼容端点）

## 快速开始

```bash
git clone https://github.com/ethanliang/ai-lab.git
cd ai-lab/2026-10-10-openai-agents-api/docker
cp .env.example .env            # 填入你自己的硅基流动 key
docker compose run --rm agents-test python scripts/test_basic_agent.py
docker compose run --rm agents-test python scripts/test_handoffs.py
docker compose run --rm agents-test python scripts/test_mcp.py
```

## 目录结构

```
docker/
├── docker-compose.yml        # 注入 .env，挂载 scripts/ 与 output/
├── Dockerfile               # python:3.12-slim + openai-agents + mcp
├── scripts/
│   ├── common.py            # 绑定硅基流动端点的模型构造器（坑1解法）
│   ├── test_basic_agent.py  # 基础 Agent + 工具调用
│   ├── test_handoffs.py     # 多 Agent 任务交接
│   ├── test_mcp.py          # MCPServerManager 管理生命周期（坑2解法）
│   └── mcp_echo_server.py   # 示例 MCP Server（mcp 2.3 新 API）
└── output/                  # 三组测试的真实输出 JSON（不含 key）
```

## 四个兼容性坑（实测确认）

1. 模型名前缀：直接传 `deepseek-ai/DeepSeek-V3` 会被 MultiProvider 的 `Unknown prefix` 拦下。解法见 `scripts/common.py`——显式构造 `OpenAIChatCompletionsModel` 并绑定自定义 `AsyncOpenAI` 客户端。
2. MCP 生命周期：0.23.1 不再自动 connect，需 `MCPServerManager` 管理。见 `scripts/test_mcp.py`。
3. mcp 2.3 大改：`@app.list_tools()` 装饰器移除，`FastMCP` 改名 `MCPServer`。见 `scripts/mcp_echo_server.py`。
4. API 改名：`to_input_messages()` → `to_input_list()`。见 `scripts/test_basic_agent.py` 输出统计处。

## 配置（.env）

| 变量 | 说明 | 默认 |
|------|------|------|
| OPENAI_API_KEY | 硅基流动API Key | 无（必填） |
| OPENAI_BASE_URL | OpenAI 兼容端点 | https://api.siliconflow.cn/v1 |
| LLM_MODEL | 模型 ID | deepseek-ai/DeepSeek-V3 |
```
