"""
测试1：基础 Agent + 工具调用
验证 OpenAI Agents SDK 能否用硅基流动 API 正常跑通基础 Agent + function calling
"""
import os
import json
import time

# 配置（统一从 common 构造模型对象，规避 MultiProvider 前缀解析问题）
from common import BASE_URL, MODEL_NAME, make_model

base_url = BASE_URL
model = MODEL_NAME

print(f"[测试1] 基础 Agent + 工具调用")
print(f"[测试1] 模型: {model}")
print(f"[测试1] Base URL: {base_url}")
print()

try:
    from agents import Agent, function_tool, Runner

    # 定义一个简单的工具函数
    @function_tool
    def get_weather(city: str) -> str:
        """获取指定城市的天气信息。

        Args:
            city: 城市名称，例如 "北京"、"上海"
        """
        # 模拟天气数据
        weather_data = {
            "北京": "晴，22°C，微风",
            "上海": "多云，25°C，东南风3级",
            "深圳": "雷阵雨，28°C，湿度85%",
        }
        return weather_data.get(city, f"{city}的天气数据暂时查不到")

    # 创建 Agent
    agent = Agent(
        name="WeatherAgent",
        instructions="你是一个天气助手。用户问天气时，使用 get_weather 工具查询，然后用自然语言回答。",
        tools=[get_weather],
        model=make_model(),
    )

    # 测试问题
    test_questions = [
        "北京今天天气怎么样？",
        "上海和深圳哪边更热？",
    ]

    results = []
    for i, question in enumerate(test_questions, 1):
        print(f"\n--- 问题 {i}: {question} ---")
        start_time = time.time()

        try:
            result = Runner.run_sync(agent, question)
            elapsed = time.time() - start_time
            answer = result.final_output

            print(f"回答: {answer}")
            print(f"耗时: {elapsed:.2f}s")
            print(f"工具调用次数: {len(result.to_input_list()) - 2}")

            results.append({
                "question": question,
                "answer": answer,
                "elapsed": elapsed,
                "success": True,
            })
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ 失败: {e}")
            results.append({
                "question": question,
                "error": str(e),
                "elapsed": elapsed,
                "success": False,
            })

    # 保存结果
    os.makedirs("output", exist_ok=True)
    with open("output/test1_basic_agent.json", "w", encoding="utf-8") as f:
        json.dump({
            "model": model,
            "base_url": base_url,
            "results": results,
            "success_count": sum(1 for r in results if r["success"]),
            "total_count": len(results),
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[测试1] 完成: {sum(1 for r in results if r['success'])}/{len(results)} 成功")

except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确认 openai-agents 已安装: pip install openai-agents")
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
