FROM python:3.12-slim

WORKDIR /app

# 安装基础依赖
RUN pip install --no-cache-dir openai-agents python-dotenv

# （可选）MCP 相关依赖
RUN pip install --no-cache-dir mcp

# 复制脚本
COPY scripts/ /app/scripts/

CMD ["python", "/app/scripts/test_basic_agent.py"]
