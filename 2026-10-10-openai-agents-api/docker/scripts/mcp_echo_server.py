"""
简易 MCP Echo Server（Stdio 模式）
用于测试 Agents SDK 的 MCP 集成
注意：mcp 2.3.0 已移除经典装饰器 API（@app.list_tools/@app.call_tool），
FastMCP 也更名为 MCPServer（mcp.server.mcpserver）。
"""
from mcp.server.mcpserver import MCPServer

app = MCPServer("echo-server")


@app.tool()
def echo(message: str) -> str:
    """回显输入的文字"""
    return f"Echo: {message}"


if __name__ == "__main__":
    app.run()
