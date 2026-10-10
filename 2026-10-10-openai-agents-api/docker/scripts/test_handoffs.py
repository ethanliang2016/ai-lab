"""
测试2：多 Agent Handoffs
验证多个 Agent 之间的 handoff（任务交接）是否正常工作
"""
import os
import json
import time

# 配置（统一从 common 构造模型对象，规避 MultiProvider 前缀解析问题）
from common import BASE_URL, MODEL_NAME, make_model

base_url = BASE_URL
model = MODEL_NAME

print(f"[测试2] 多 Agent Handoffs")
print(f"[测试2] 模型: {model}")
print()

try:
    from agents import Agent, Runner, handoff

    # 三个 Agent：客服 → 技术 → 售后
    customer_service_agent = Agent(
        name="客服Agent",
        instructions="你是客服人员。负责处理用户的一般性咨询和问题分类。"
                     "如果是技术问题，请转交给技术Agent；"
                     "如果是售后问题（退换货、投诉），请转交给售后Agent；"
                     "其他问题你自己回答。",
        handoffs=[],  # 后面动态加
        model=make_model(),
    )

    tech_agent = Agent(
        name="技术Agent",
        instructions="你是技术支持人员。负责解答产品使用相关的技术问题。"
                     "回答要简洁、专业、有操作性。",
        model=make_model(),
    )

    support_agent = Agent(
        name="售后Agent",
        instructions="你是售后客服。负责处理退换货、投诉等售后问题。"
                     "态度要友好，先道歉再给出解决方案。",
        model=make_model(),
    )

    # 给客服 agent 添加 handoff
    customer_service_agent.handoffs = [
        handoff(tech_agent, tool_name_override="transfer_to_tech"),
        handoff(support_agent, tool_name_override="transfer_to_support"),
    ]

    # 测试问题
    test_cases = [
        {"q": "你们的产品怎么连接 WiFi？", "expected": "技术"},
        {"q": "我收到的商品有破损，想退货", "expected": "售后"},
        {"q": "你们几点下班？", "expected": "客服"},
    ]

    results = []
    for i, case in enumerate(test_cases, 1):
        question = case["q"]
        expected = case["expected"]
        print(f"\n--- 问题 {i}: {question} (预期: {expected}) ---")
        start_time = time.time()

        try:
            result = Runner.run_sync(customer_service_agent, question)
            elapsed = time.time() - start_time
            answer = result.final_output

            # 直接取最终回答的 Agent（0.23.1 RunResult.last_agent）
            last_agent_name = result.last_agent.name if result.last_agent else "未知"

            print(f"回答: {answer[:100]}..." if len(answer) > 100 else f"回答: {answer}")
            print(f"耗时: {elapsed:.2f}s")
            print(f"最终 Agent: {last_agent_name}")

            # 依据最终 Agent 判定实际处理人
            actual = "客服"
            if last_agent_name == "技术Agent":
                actual = "技术"
            elif last_agent_name == "售后Agent":
                actual = "售后"

            results.append({
                "question": question,
                "expected": expected,
                "actual": actual,
                "answer": answer,
                "elapsed": elapsed,
                "success": True,
            })
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ 失败: {e}")
            results.append({
                "question": question,
                "expected": expected,
                "error": str(e),
                "elapsed": elapsed,
                "success": False,
            })

    # 保存结果
    os.makedirs("output", exist_ok=True)
    with open("output/test2_handoffs.json", "w", encoding="utf-8") as f:
        json.dump({
            "model": model,
            "results": results,
            "success_count": sum(1 for r in results if r["success"]),
            "total_count": len(results),
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[测试2] 完成: {sum(1 for r in results if r['success'])}/{len(results)} 成功")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
