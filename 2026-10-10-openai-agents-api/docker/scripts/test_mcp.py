"""
测试3：本地 MCP Server 接入（Stdio 模式）
验证 Agents SDK 能否通过 Stdio 方式接入本地 MCP Server

注意（openai-agents 0.23.1 实测确认）：
- MCP server 生命周期由用户负责：必须 connect 后才能传给 Agent，
  官方推荐用 MCPServerManager 管理 connect/cleanup，并把
  manager.active_servers 传给 Agent。
- 直接 Agent(mcp_servers=[server]) 而不 connect，会在工具调用时报
  "Server not initialized. Make sure you call `connect()` first."。
"""
import asyncio
import json
import os
import time

from common import MODEL_NAME, make_model

print(f"[测试3] 本地 MCP Server 接入（Stdio 模式）")
print(f"[测试3] 模型: {MODEL_NAME}")
print()


async def run_test():
    from agents import Agent, Runner
    from agents.mcp import MCPServerStdio, MCPServerManager

    # 用 MCPServerManager 管理生命周期（connect / cleanup）
    server = MCPServerStdio(
        name="test-mcp-server",
        params={"command": "python", "args": ["/app/scripts/mcp_echo_server.py"]},
    )

    async with MCPServerManager([server]) as manager:
        # 只有连接成功的 server 才会出现在 active_servers
        agent = Agent(
            name="MCPTestAgent",
            instructions="你是一个测试助手。使用可用的 MCP 工具来回答用户问题。",
            mcp_servers=manager.active_servers,
            model=make_model(),
        )

        test_question = "用 echo 工具说一句 'Hello from MCP'"
        print(f"问题: {test_question}")
        start_time = time.time()

        try:
            result = await Runner.run(agent, test_question)
            elapsed = time.time() - start_time
            answer = result.final_output
            print(f"回答: {answer}")
            print(f"耗时: {elapsed:.2f}s")
            success = True
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ MCP 测试失败: {e}")
            answer = str(e)
            success = False

        return test_question, answer, elapsed, success


def main():
    test_question, answer, elapsed, success = asyncio.run(run_test())

    os.makedirs("output", exist_ok=True)
    with open("output/test3_mcp.json", "w", encoding="utf-8") as f:
        json.dump({
            "model": MODEL_NAME,
            "question": test_question,
            "answer": answer,
            "elapsed": elapsed,
            "success": success,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[测试3] 完成: {'成功' if success else '失败'}")


if __name__ == "__main__":
    main()
