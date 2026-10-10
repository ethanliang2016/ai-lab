"""
共享配置：为 OpenAI 兼容端点（硅基流动 SiliconFlow）构造 openai-agents 可用的模型。

背景（openai-agents 0.23.1 实测确认）：
- 0.23.1 通过 MultiProvider 按模型名前缀路由 provider，默认前缀表为
  "openai/"、"litellm/"、"any-llm/"；未知前缀（如 deepseek-ai/）默认抛
  UserError("Unknown prefix: deepseek-ai")。
- 因此不能把 "deepseek-ai/DeepSeek-V3" 直接作为 model 字符串传给 Agent。
- 正确做法：显式构造 OpenAIChatCompletionsModel 并绑定自定义 AsyncOpenAI 客户端，
  完整模型 ID 会原样透传给硅基流动 /chat/completions。
- 同时关闭 tracing（默认会上报 OpenAI，自定义端点场景无意义且可能报错）。
"""
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import set_default_openai_api, set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

load_dotenv()

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
MODEL_NAME = os.environ.get("LLM_MODEL", "deepseek-ai/DeepSeek-V3")

# 自定义端点通常只支持 Chat Completions，不支持 Responses API
set_default_openai_api("chat_completions")
# 关闭 tracing，避免向 OpenAI 上报轨迹
set_tracing_disabled(True)

_client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)


def make_model() -> OpenAIChatCompletionsModel:
    """构造绑定硅基流动端点的 Chat Completions 模型对象。"""
    return OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=_client)
